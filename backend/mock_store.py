"""Fills the database with weeks of realistic sample data for a fictional neighborhood market.

    npm run mock-store                         # 6 weeks ending now
    npm run mock-store -- --weeks 10 --seed 3  # longer history, different random days

This is demo data for the Store insights page: it shows what DensityAI tells a store manager
once cameras have been running for a while (busiest hours and days, where shoppers go, how long
they stay, crowding alerts). It goes into its own site ("sample-store", marked as sample data on
the dashboard), so it never mixes with the live camera's counts. Running it again replaces the
previous sample data.

Each simulated shopper walks in, visits a few zones in a random order, waits at checkout (longer
when the store is busy) and leaves. The script writes the same kinds of events the collector
writes from a real camera: per-minute occupancy for each zone, entries and exits at the door,
one dwell event per zone visit, and an alert when checkout gets crowded.
"""
import argparse
import math
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app import db  # noqa: E402

SITE = {"id": "sample-store", "name": "Maple Street Market (sample data)", "kind": "sample",
        "tz": "America/New_York"}
ZONES = [
    {"id": "entrance", "name": "Entrance", "capacity": 20, "role": "entrance"},
    {"id": "produce", "name": "Fresh produce", "capacity": 30},
    {"id": "snacks", "name": "Snacks and drinks", "capacity": 20},
    {"id": "endcap", "name": "Seasonal end-cap", "capacity": 8, "role": "promo"},
    {"id": "pharmacy", "name": "Pharmacy counter", "capacity": 12},
    {"id": "checkout", "name": "Checkout lanes", "capacity": 20, "role": "checkout", "alertAt": 16},
]
# Opening hours per weekday (Mon=0): (open, close) in local hours.
HOURS = {0: (7, 22), 1: (7, 22), 2: (7, 22), 3: (7, 22), 4: (7, 22), 5: (7, 22), 6: (8, 20)}
DAILY_VISITORS = 1100
WEEKDAY_FACTOR = [0.82, 0.78, 0.9, 0.97, 1.15, 1.38, 1.12]
GROWTH_PER_WEEK = 0.01
CHECKOUT_ALERT_COOLDOWN_MIN = 30


def poisson(lam, rng):
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def bump(h, center, width, height):
    return height * math.exp(-((h - center) / width) ** 2)


def shoppers_curve(hour, weekend):
    """Relative arrival rate by hour of day: commute, lunch and after-work peaks on weekdays,
    one broad midday hump on weekends."""
    if weekend:
        return 0.15 + bump(hour, 13, 2.6, 1.15) + bump(hour, 17.5, 1.5, 0.3)
    return 0.22 + bump(hour, 8.2, 0.9, 0.22) + bump(hour, 12.4, 1.0, 0.6) + bump(hour, 17.6, 1.4, 0.8)


def lognormal(rng, median, spread=0.5):
    return median * math.exp(rng.gauss(0, spread))


def generate(weeks, seed, now, tz):
    rng = random.Random(seed)
    zone_ids = [z["id"] for z in ZONES]
    zi = {z: i for i, z in enumerate(zone_ids)}
    end = datetime.fromtimestamp(now, tz)
    first = (end - timedelta(weeks=weeks)).date()
    t0 = datetime(first.year, first.month, first.day, tzinfo=tz).timestamp()
    n_min = int((now - t0) // 60) + 1
    presence = [[0.0] * (n_min + 60) for _ in zone_ids]  # person-seconds per zone per minute
    entries = [0] * (n_min + 60)
    exits = [0] * (n_min + 60)
    open_minutes = set()
    rows = []

    def present(zone, start, stop):
        a = start
        while a < stop:
            m = int((a - t0) // 60)
            b = min(stop, t0 + (m + 1) * 60)
            if 0 <= m < len(presence[zone]):
                presence[zone][m] += b - a
            a = b

    # Busiest arrival rate across the whole period, so checkout waits scale with how busy it is.
    peak_rate = DAILY_VISITORS * max(WEEKDAY_FACTOR) * (1 + GROWTH_PER_WEEK * weeks) / 9.0 / 60

    day = first
    while day <= end.date():
        wd = day.weekday()
        open_h, close_h = HOURS[wd]
        weekend = wd >= 5
        weeks_ago = (end.date() - day).days / 7
        total = DAILY_VISITORS * WEEKDAY_FACTOR[wd] * (1 - GROWTH_PER_WEEK * weeks_ago) * rng.uniform(0.9, 1.1)
        mins = [(h * 60 + m) for h in range(open_h, close_h) for m in range(60)]
        weights = [shoppers_curve((m + 0.5) / 60, weekend) for m in mins]
        scale = total / sum(weights)
        day_start = datetime(day.year, day.month, day.day, tzinfo=tz).timestamp()
        for m, w in zip(mins, weights):
            minute_start = day_start + m * 60
            if minute_start > now:
                break
            open_minutes.add(int((minute_start - t0) // 60))
            rate = w * scale
            load = rate / peak_rate
            hour = m / 60
            for _ in range(poisson(rate, rng)):
                t = minute_start + rng.random() * 60
                entries[int((t - t0) // 60)] += 1
                stay = rng.uniform(4, 15)
                present(zi["entrance"], t, t + stay)
                t += stay
                stops = []
                if rng.random() < (0.65 if hour >= 16 else 0.5):
                    stops.append(("produce", lognormal(rng, 150)))
                if rng.random() < 0.5:
                    stops.append(("snacks", lognormal(rng, 70)))
                pharmacy_p = 0.3 if (not weekend and (9 <= hour < 11 or 16 <= hour < 18)) else 0.16
                if rng.random() < pharmacy_p:
                    stops.append(("pharmacy", lognormal(rng, 200 + 160 * load, 0.4)))
                if rng.random() < 0.7:  # on the main aisle, so most shoppers pass it
                    engaged = rng.random() < 0.42
                    stops.append(("endcap", lognormal(rng, 50, 0.45) if engaged else rng.uniform(4, 20)))
                rng.shuffle(stops)
                if rng.random() < 0.86:
                    stops.append(("checkout", rng.uniform(60, 120) + 130 * load ** 3 * rng.uniform(0.6, 1.4)))
                for zone, dwell in stops:
                    t += rng.uniform(10, 40)
                    present(zi[zone], t, t + dwell)
                    t += dwell
                    rows.append((t, SITE["id"], zone, None, "dwell", round(dwell, 1), None))
                t += rng.uniform(5, 20)
                if t <= now:
                    exits[int((t - t0) // 60)] += 1
        day += timedelta(days=1)

    now_m = int((now - t0) // 60)
    alerted_at = -10 ** 9
    for m in range(min(n_min, now_m)):
        ts = t0 + m * 60 + 30
        if m in open_minutes:
            for z, zone in enumerate(zone_ids):
                rows.append((ts, SITE["id"], zone, None, "occupancy", round(presence[z][m] / 60, 2), None))
        if entries[m]:
            rows.append((ts, SITE["id"], "entrance", None, "entry", entries[m], None))
        if exits[m]:
            rows.append((ts, SITE["id"], "entrance", None, "exit", exits[m], None))
        # Checkout alert: a 5-minute average at or over its alert level.
        co = zi["checkout"]
        if m >= 5:
            avg5 = sum(presence[co][m - 4:m + 1]) / 300
            limit = ZONES[co]["alertAt"]
            if avg5 >= limit and m - alerted_at >= CHECKOUT_ALERT_COOLDOWN_MIN:
                alerted_at = m
                n = round(avg5)
                text = (f"Checkout lanes reached {n} people ({round(100 * n / ZONES[co]['capacity'])}% of "
                        "capacity). Open another lane.")
                rows.append((ts, SITE["id"], "checkout", None, "alert", n, {"text": text}))
    rows = [r for r in rows if r[0] <= now]
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weeks", type=int, default=6)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--database-url", help="default: $DATABASE_URL or " + db.DEFAULT_URL)
    args = parser.parse_args()

    tz = ZoneInfo(SITE["tz"])
    started = time.time()
    print(f"Simulating {args.weeks} weeks of shoppers at {SITE['name']}...")
    rows = generate(args.weeks, args.seed, time.time(), tz)
    conn = db.connect(args.database_url)
    db.sync_site(conn, SITE, ZONES)
    db.delete_site_events(conn, SITE["id"])
    db.insert_events(conn, rows)
    kinds = {}
    for r in rows:
        kinds[r[4]] = kinds.get(r[4], 0) + 1
    summary = ", ".join(f"{n:,} {k}" for k, n in sorted(kinds.items()))
    print(f"Wrote {len(rows):,} events ({summary}) to {db.database_name(conn)} "
          f"in {time.time() - started:.0f} s.")
    print("Open the dashboard's Store insights page to see them.")
    conn.close()


if __name__ == "__main__":
    main()
