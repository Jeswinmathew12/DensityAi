"""Builds the dashboard's history (trends, traffic, stats, insights) from stored samples.

Returns the same shapes as the mock generators in src/utils/fakeDataGenerator.js. None means
"no data": charts draw a gap and stats show a dash, so a camera that was off is never shown as
an empty room.
"""
from collections import defaultdict
from datetime import datetime
from statistics import mean

from .processing import fuse

HOURS = 24
# Minutes of data a zone needs today before the "busiest hour" insight appears.
BUSIEST_INSIGHT_MIN = 60
# A gap in a zone's data longer than this (minutes) becomes an "offline" insight.
OFFLINE_INSIGHT_MIN = 5

# One row per camera per minute: average count plus entries/exits in that minute, taken from
# the cumulative counters. A counter that drops means the pipeline restarted and began again
# from 0, so the new value is the count since the restart.
MINUTES_SQL = """
WITH d AS (
  SELECT camera_id, zone_id, ts, occupancy, entries_cum, exits_cum,
         entries_cum - LAG(entries_cum) OVER w AS d_in,
         exits_cum - LAG(exits_cum) OVER w AS d_out
  FROM samples WHERE ts >= ? AND ts <= ?
  WINDOW w AS (PARTITION BY camera_id ORDER BY ts)
)
SELECT camera_id, zone_id, CAST(ts / 60 AS INTEGER), AVG(occupancy),
       SUM(CASE WHEN d_in IS NULL THEN 0 WHEN d_in >= 0 THEN d_in ELSE entries_cum END),
       SUM(CASE WHEN d_out IS NULL THEN 0 WHEN d_out >= 0 THEN d_out ELSE exits_cum END)
FROM d GROUP BY camera_id, zone_id, CAST(ts / 60 AS INTEGER)
"""


def clock(ts, tz):
    """Epoch seconds to a local time like "2:05 PM"."""
    t = datetime.fromtimestamp(ts, tz)
    return f"{t.hour % 12 or 12}:{t.minute:02d} {'AM' if t.hour < 12 else 'PM'}"


def build(conn, config, now, tz):
    """History for the 24 local hours ending with the current one, and stats for today."""
    now_local = datetime.fromtimestamp(now, tz)
    hour0 = now_local.replace(minute=0, second=0, microsecond=0).timestamp()
    start = hour0 - (HOURS - 1) * 3600
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    hour_starts = [start + i * 3600 for i in range(HOURS)]
    labels = [datetime.fromtimestamp(t, tz).hour for t in hour_starts]

    def bucket(minute):
        return int((minute * 60 - start) // 3600)

    zones = config["zones"]
    zone_cams = defaultdict(set)
    for c in config["cameras"]:
        zone_cams[c["zoneId"]].add(c["id"])

    cams_by_minute = defaultdict(dict)  # (zone_id, minute) -> {camera_id: avg count}
    entries, exits = [None] * HOURS, [None] * HOURS
    visitors_today = 0
    for cam, zone_id, minute, occ, d_in, d_out in conn.execute(MINUTES_SQL, (start, now)):
        cams_by_minute[(zone_id, minute)][cam] = occ
        i = bucket(minute)
        entries[i] = (entries[i] or 0) + d_in
        exits[i] = (exits[i] or 0) + d_out
        if minute * 60 >= midnight:
            visitors_today += d_in

    # Per zone, the fused count for each minute it has data. Same rule as the live view:
    # "sum" needs every camera in the zone, "max" needs any one.
    zone_minutes = {z["id"]: {} for z in zones}
    for (zone_id, minute), cams in cams_by_minute.items():
        zone = next((z for z in zones if z["id"] == zone_id), None)
        if zone is None:
            continue
        mode = zone.get("fusion", "sum")
        if mode == "sum" and not zone_cams[zone_id] <= cams.keys():
            continue
        zone_minutes[zone_id][minute] = fuse(list(cams.values()), mode)

    def hourly(minutes):
        """{minute: value} -> 24 hourly averages, None where there is no data."""
        per_hour = defaultdict(list)
        for minute, value in minutes.items():
            per_hour[bucket(minute)].append(value)
        return [round(mean(per_hour[i])) if per_hour[i] else None for i in range(HOURS)]

    trends = {
        z["id"]: [
            {"hour": h, "label": f"{h}:00", "occupancy": v}
            for h, v in zip(labels, hourly(zone_minutes[z["id"]]))
        ]
        for z in zones
    }
    traffic = [
        {"hour": h, "label": f"{h}:00", "entries": e, "exits": x}
        for h, e, x in zip(labels, entries, exits)
    ]

    # Building-wide total for minutes where every zone has data.
    shared = set.intersection(*(set(m) for m in zone_minutes.values())) if zones else set()
    totals_today = {
        m: sum(zone_minutes[z["id"]][m] for z in zones) for m in shared if m * 60 >= midnight
    }
    peak = max(
        ((v, i) for i, v in enumerate(hourly(totals_today)) if v is not None),
        default=None,
    )
    stats = {
        "peakHour": clock(hour_starts[peak[1]], tz) if peak else None,
        "avgOccupancy": round(mean(totals_today.values())) if totals_today else None,
        # No entries looks the same as line crossing being off (Demo 1), so show a dash, not 0.
        "totalVisitors": visitors_today or None,
    }

    return {
        "trends": trends,
        "traffic": traffic,
        "stats": stats,
        "insights": insights(zones, zone_minutes, now, midnight, hour_starts, hourly, tz),
    }


def insights(zones, zone_minutes, now, midnight, hour_starts, hourly, tz):
    out = []
    now_minute = int(now // 60)
    for z in zones:
        today = sorted(m for m in zone_minutes[z["id"]] if m * 60 >= midnight)
        if not today:
            continue
        values = {m: zone_minutes[z["id"]][m] for m in today}

        if len(today) >= BUSIEST_INSIGHT_MIN:
            avg, i = max((v, i) for i, v in enumerate(hourly(values)) if v is not None)
            out.append(f"{z['name']} has been busiest at {clock(hour_starts[i], tz)} today (avg {avg} people).")

        # Most recent gap today, including one that is still going on.
        if now_minute - today[-1] > OFFLINE_INSIGHT_MIN:
            out.append(f"{z['name']} has had no camera data since {clock((today[-1] + 1) * 60, tz)}.")
        else:
            gaps = [(a, b) for a, b in zip(today, today[1:]) if b - a > OFFLINE_INSIGHT_MIN]
            if gaps:
                a, b = gaps[-1]
                out.append(f"{z['name']} was offline {clock((a + 1) * 60, tz)} to {clock(b * 60, tz)}.")
    return [{"id": i + 1, "text": text} for i, text in enumerate(out)]
