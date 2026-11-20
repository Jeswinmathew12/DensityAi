"""Store analytics for one site over the last N days, built from the events table.

This is what turns raw counts into business answers: when the store is busiest, which days
bring the most shoppers, where they go, how long they stay, when a zone got crowded, and what
to do about it. The shape matches generateStoreAnalytics() in src/utils/fakeDataGenerator.js.

None means "no data" (shown as a gap or a dash), never 0.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
# A zone visit this long counts as "engaged" (stopped to look), not just walking past.
ENGAGED_S = 30
DWELL_BUCKETS = [(0, 30, "Under 30 s"), (30, 120, "30 s to 2 min"), (120, 300, "2 to 5 min"),
                 (300, None, "Over 5 min")]

OCCUPANCY_SQL = """
WITH per AS (
  SELECT date_trunc('hour', time AT TIME ZONE %(tz)s) AS hr, zone_id, coalesce(camera_id, '') AS cam,
         avg(value) AS v
  FROM events
  WHERE site_id = %(site)s AND kind = 'occupancy' AND time >= %(start)s AND time <= %(end)s
  GROUP BY 1, 2, 3
)
SELECT hr, zone_id, sum(v) FROM per GROUP BY 1, 2
"""
TRAFFIC_SQL = """
SELECT date_trunc('hour', time AT TIME ZONE %(tz)s) AS hr, zone_id,
       sum(value) FILTER (WHERE kind = 'entry'), sum(value) FILTER (WHERE kind = 'exit')
FROM events
WHERE site_id = %(site)s AND kind IN ('entry', 'exit') AND time >= %(start)s AND time <= %(end)s
GROUP BY 1, 2
"""
DWELL_SQL = """
SELECT zone_id, count(*), avg(value), percentile_cont(0.5) WITHIN GROUP (ORDER BY value),
       count(*) FILTER (WHERE value >= %(engaged)s),
       count(*) FILTER (WHERE value < 30),
       count(*) FILTER (WHERE value >= 30 AND value < 120),
       count(*) FILTER (WHERE value >= 120 AND value < 300),
       count(*) FILTER (WHERE value >= 300)
FROM events
WHERE site_id = %(site)s AND kind = 'dwell' AND time >= %(start)s AND time <= %(end)s
GROUP BY 1
"""
ALERTS_SQL = """
SELECT time, zone_id, value, detail->>'text'
FROM events
WHERE site_id = %(site)s AND kind = 'alert' AND time >= %(start)s AND time <= %(end)s
ORDER BY time DESC
"""


def hour_label(h):
    return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"


def people(n):
    n = round(n)
    return f"{n} shopper{'' if n == 1 else 's'}"


def pct(a, b):
    return round(100 * a / b) if b else None


def build(conn, site, config, now, tz, days=28):
    now_local = datetime.fromtimestamp(now, tz)
    first_day = (now_local - timedelta(days=days - 1)).date()
    start = datetime(first_day.year, first_day.month, first_day.day, tzinfo=tz)
    params = {"site": site["id"], "tz": str(tz), "start": start, "end": now_local, "engaged": ENGAGED_S}
    zones = config["zones"]
    zone_by_id = {z["id"]: z for z in zones}
    dates = [first_day + timedelta(days=i) for i in range(days)]

    # Store-wide people per local hour, and per zone.
    store_hour = defaultdict(float)
    zone_hours = defaultdict(list)
    for hr, zone_id, v in conn.execute(OCCUPANCY_SQL, params):
        store_hour[hr] += v
        zone_hours[zone_id].append(v)

    entries_hour = defaultdict(float)
    entries_zone = defaultdict(float)
    for hr, zone_id, ins, _outs in conn.execute(TRAFFIC_SQL, params):
        entries_hour[hr] += ins or 0
        entries_zone[zone_id] += ins or 0

    dwell = {}
    buckets = [0, 0, 0, 0]
    for zone_id, n, avg_s, med_s, engaged, *b in conn.execute(DWELL_SQL, params):
        dwell[zone_id] = {"visits": n, "avg": avg_s, "median": med_s, "engaged": engaged}
        if zone_by_id.get(zone_id, {}).get("role") != "entrance":
            buckets = [x + y for x, y in zip(buckets, b)]

    alerts = [
        {"time": t.isoformat(), "zoneId": z, "zone": zone_by_id.get(z, {}).get("name", z),
         "people": round(v), "text": text}
        for t, z, v, text in conn.execute(ALERTS_SQL, params)
    ]

    data_dates = sorted({hr.date() for hr in list(store_hour) + list(entries_hour)})
    # Averages leave out today, which is still under way and would drag them down.
    full_dates = [d for d in data_dates if d != now_local.date()] or data_dates

    # Visitors per day (the line chart) and per weekday (bar chart): averages over days with data.
    per_date = defaultdict(float)
    for hr, n in entries_hour.items():
        per_date[hr.date()] += n
    has_traffic = bool(entries_hour)
    daily = [
        {"date": d.isoformat(), "label": f"{d.strftime('%b')} {d.day}", "weekday": DAYS[d.weekday()],
         "visitors": round(per_date[d]) if d in data_dates and has_traffic else None}
        for d in dates
    ]
    by_weekday = []
    for i, name in enumerate(DAYS):
        vals = [per_date[d] for d in full_dates if d.weekday() == i]
        by_weekday.append({"day": name, "visitors": round(mean(vals)) if vals and has_traffic else None})

    hours_seen = sorted({hr.hour for hr in (store_hour or entries_hour)})
    open_hours = list(range(hours_seen[0], hours_seen[-1] + 1)) if hours_seen else []
    by_hour = []
    for h in open_hours:
        vals = [n for hr, n in entries_hour.items() if hr.hour == h and hr.date() in full_dates]
        avg = sum(vals) / len(full_dates) if vals else None
        by_hour.append({"hour": h, "label": hour_label(h), "visitors": round(avg, 1) if avg is not None else None})

    # Busiest-times heatmap: average people in the store, weekday x hour.
    cell_vals = defaultdict(list)
    for hr, v in store_hour.items():
        cell_vals[(hr.weekday(), hr.hour)].append(v)
    heatmap = [
        {"day": DAYS[d], "cells": [
            {"hour": h, "label": hour_label(h),
             "value": round(mean(cell_vals[(d, h)]), 1) if cell_vals.get((d, h)) else None}
            for h in open_hours
        ]}
        for d in range(7)
    ]
    cells = [(mean(v), d, h) for (d, h), v in cell_vals.items()]
    busiest = max(cells, default=None)
    quietest = min(cells, default=None)

    # Per zone: reach, dwell, crowding.
    total_visitors = sum(per_date.values()) if has_traffic else None
    zone_rows = []
    for z in zones:
        dw = dwell.get(z["id"])
        hours = zone_hours.get(z["id"], [])
        visits = dw["visits"] if dw else (round(entries_zone[z["id"]]) if entries_zone.get(z["id"]) else None)
        zone_rows.append({
            "id": z["id"], "name": z["name"], "role": z.get("role"), "capacity": z["capacity"],
            "visits": visits,
            "reachPct": pct(visits, total_visitors) if visits and total_visitors else None,
            "avgDwellSec": round(dw["avg"]) if dw else None,
            "medianDwellSec": round(dw["median"]) if dw else None,
            "engagedPct": pct(dw["engaged"], dw["visits"]) if dw else None,
            "avgOccupancy": round(mean(hours), 1) if hours else None,
            "peakOccupancy": round(max(hours)) if hours else None,
            "peakUtilPct": pct(max(hours), z["capacity"]) if hours else None,
            "alerts": sum(1 for a in alerts if a["zoneId"] == z["id"]),
        })
    shoppable = [z for z in zone_rows if z["role"] != "entrance"] or zone_rows
    share_total = sum(z["visits"] or 0 for z in shoppable)
    zone_share = [
        {"zoneId": z["id"], "name": z["name"], "visits": z["visits"], "sharePct": pct(z["visits"], share_total)}
        for z in shoppable if z["visits"]
    ]
    dwell_buckets = [{"label": label, "count": n} for (_, _, label), n in zip(DWELL_BUCKETS, buckets)]
    if not any(buckets):
        dwell_buckets = []

    dwell_rows = [dwell[z["id"]] for z in shoppable if z["id"] in dwell]
    all_visits = sum(d["visits"] for d in dwell_rows)
    avg_dwell = sum(d["avg"] * d["visits"] for d in dwell_rows) / all_visits if all_visits else None
    checkout = next((z for z in zone_rows if z["role"] == "checkout"), None)

    complete = dates[:-1]  # every day but today
    last7 = [per_date[d] for d in complete[-7:] if d in data_dates]
    prev7 = [per_date[d] for d in complete[-14:-7] if d in data_dates]
    change = None
    if has_traffic and len(last7) >= 3 and len(prev7) >= 3 and mean(prev7):
        change = round(100 * (mean(last7) - mean(prev7)) / mean(prev7))

    kpis = {
        "visitors": round(total_visitors) if total_visitors else None,
        "visitorsPerDay": (round(sum(per_date[d] for d in full_dates) / len(full_dates))
                           if total_visitors and full_dates else None),
        "visitorsChangePct": change,
        "avgDwellSec": round(avg_dwell) if avg_dwell is not None else None,
        "conversionPct": checkout["reachPct"] if checkout else None,
        "busiest": f"{DAYS[busiest[1]]} {hour_label(busiest[2])}" if busiest else None,
        "alerts": len(alerts),
    }

    return {
        "site": {"id": site["id"], "name": site["name"], "kind": site["kind"]},
        "range": {"from": first_day.isoformat(), "to": now_local.date().isoformat(), "days": days,
                  "daysWithData": len(data_dates)},
        "kpis": kpis,
        "daily": daily,
        "byWeekday": by_weekday,
        "byHour": by_hour,
        "heatmap": heatmap,
        "zones": zone_rows,
        "zoneShare": zone_share,
        "dwellBuckets": dwell_buckets,
        "alerts": alerts[:12],
        "recommendations": recommendations(
            busiest, quietest, by_weekday, shoppable, checkout, change, alerts),
    }


def recommendations(busiest, quietest, by_weekday, zones, checkout, change, alerts):
    """Plain-language actions a store manager could take, from the numbers above."""
    out = []

    def add(kind, title, text):
        out.append({"id": len(out) + 1, "kind": kind, "title": title, "text": text})

    if busiest:
        v, d, h = busiest
        text = (f"{DAY_NAMES[d]}s at {hour_label(h)} are the busiest hour, with {people(v)} in the "
                f"store on average.")
        if checkout and checkout["alerts"]:
            text += (f" Checkout reached its crowding alert {checkout['alerts']} times in this period, "
                     "so schedule an extra cashier for that window.")
        else:
            text += " Schedule your strongest staffing for that window."
        add("staffing", f"Staff up for {DAYS[d]} {hour_label(h)}", text)

    if quietest and busiest and quietest != busiest:
        v, d, h = quietest
        add("operations", f"Restock on {DAYS[d]} {hour_label(h)}",
            f"{DAY_NAMES[d]} at {hour_label(h)} is the quietest open hour ({people(v)} on average). "
            "Use it for restocking, cleaning and planogram changes so they don't get in shoppers' way.")

    days = [d for d in by_weekday if d["visitors"]]
    if len(days) >= 2:
        hi = max(days, key=lambda d: d["visitors"])
        lo = min(days, key=lambda d: d["visitors"])
        if lo["visitors"] and hi["visitors"] / lo["visitors"] >= 1.2:
            hi_name, lo_name = DAY_NAMES[DAYS.index(hi["day"])], DAY_NAMES[DAYS.index(lo["day"])]
            add("marketing", f"Fill the slow {lo_name}",
                f"{hi_name} brings {hi['visitors'] / lo['visitors']:.1f}x the shoppers of {lo_name}. "
                f"A {lo_name}-only promotion could move some of that demand to the slow day.")

    promo = next((z for z in zones if z["role"] == "promo" and z["engagedPct"] is not None), None)
    if promo:
        add("layout", f"Make {promo['name']} work harder",
            f"{promo['reachPct'] or '?'}% of shoppers walk past {promo['name']}, but only {promo['engagedPct']}% "
            f"of them stop for 30 seconds or more. Try a new display or price callout for two weeks and "
            "compare this number before and after.")

    reach = [z for z in zones if z["reachPct"] is not None and z["role"] not in ("checkout",)]
    if len(reach) >= 2:
        low = min(reach, key=lambda z: z["reachPct"])
        add("layout", f"Bring more shoppers to {low['name']}",
            f"Only {low['reachPct']}% of visitors reach {low['name']}. Signage near the entrance or moving a "
            "popular item next to it would raise that.")

    if change is not None and abs(change) >= 5:
        word = "up" if change > 0 else "down"
        add("marketing", f"Traffic is {word} {abs(change)}% this week",
            f"Visitors over the last 7 days are {word} {abs(change)}% from the week before. "
            + ("Check that staffing and stock keep up." if change > 0
               else "Worth checking for a cause (weather, a competitor's sale, a closed entrance)."))

    if alerts and not (checkout and checkout["alerts"]):
        a = alerts[0]
        add("operations", f"Watch {a['zone']}", f"Latest crowding alert: {a['text']}")
    return out
