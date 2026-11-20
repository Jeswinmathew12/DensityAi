"""PostgreSQL storage: one simple events table, plus the sites, zones and cameras it refers to.

Both the collector (writes) and the web service (reads) use this module. Everything the
dashboard shows is computed from `events`, so the two programs only share the database.

Event kinds (one row each):
  occupancy  value = people in the zone (a camera's 1 Hz count, or a per-minute average)
  entry      value = people who walked in during that moment
  exit       value = people who walked out
  dwell      value = seconds one person spent in the zone (written when they leave)
  alert      value = people in the zone when it crossed its alert level; detail.text says why

If the TimescaleDB extension is installed, `events` becomes a hypertable (a time-series table
that stays fast as it grows). Without it, `events` is a plain table and everything still works.
"""
import json
import logging
import os
from datetime import datetime, timezone

import psycopg

DEFAULT_URL = "postgresql:///densityai"  # local socket, the Linux user's own role, no password
log = logging.getLogger("uvicorn.error")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
  id    text PRIMARY KEY,
  name  text NOT NULL,
  kind  text NOT NULL DEFAULT 'live',   -- 'live' (real cameras) or 'sample' (generated demo data)
  tz    text NOT NULL DEFAULT 'America/New_York'
);
CREATE TABLE IF NOT EXISTS zones (
  site_id   text NOT NULL REFERENCES sites (id) ON DELETE CASCADE,
  id        text NOT NULL,
  name      text NOT NULL,
  capacity  integer NOT NULL,
  fusion    text NOT NULL DEFAULT 'sum',
  role      text,                       -- optional: entrance, checkout, promo
  alert_at  integer,                    -- optional: alert when this many people are in the zone
  sort      integer NOT NULL DEFAULT 0,
  PRIMARY KEY (site_id, id)
);
CREATE TABLE IF NOT EXISTS cameras (
  id       text PRIMARY KEY,
  site_id  text NOT NULL REFERENCES sites (id) ON DELETE CASCADE,
  zone_id  text NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id         bigserial,
  time       timestamptz NOT NULL,
  site_id    text NOT NULL,
  zone_id    text NOT NULL,
  camera_id  text,
  kind       text NOT NULL,
  value      double precision NOT NULL DEFAULT 1,
  detail     jsonb
);
CREATE INDEX IF NOT EXISTS events_site_kind_time ON events (site_id, kind, time);
CREATE INDEX IF NOT EXISTS events_id ON events (id);
"""


def database_url(url=None):
    return url or os.environ.get("DATABASE_URL") or DEFAULT_URL


def connect(url=None):
    """Open a connection and make sure the database and its tables exist."""
    url = database_url(url)
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.OperationalError as e:
        if "does not exist" not in str(e):
            raise
        create_database(url)
        conn = psycopg.connect(url, autocommit=True)
    conn.execute(SCHEMA)
    _try_timescale(conn)
    return conn


def create_database(url):
    """Create the database named in `url` (e.g. densityai_sim the first time the simulator runs)."""
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    name = conninfo_to_dict(url).get("dbname")
    with psycopg.connect(make_conninfo(url, dbname="postgres"), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    log.warning("Created database %s", name)


def _try_timescale(conn):
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
    except psycopg.Error:
        return  # not installed: plain table
    try:
        conn.execute(
            "SELECT create_hypertable('events', 'time', if_not_exists => TRUE, migrate_data => TRUE)"
        )
    except psycopg.Error as e:
        log.warning("TimescaleDB is installed but events could not become a hypertable: %s", e)


def has_timescale(conn):
    row = conn.execute(
        "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"
    ).fetchone()
    return row is not None


def database_name(conn):
    return conn.info.dbname


def sync_site(conn, site, zones, cameras=()):
    """Write a site's config (from zones.json or the sample-store generator) into the database."""
    with conn.transaction():
        conn.execute(
            """INSERT INTO sites (id, name, kind, tz) VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, kind = EXCLUDED.kind, tz = EXCLUDED.tz""",
            (site["id"], site["name"], site.get("kind", "live"), site.get("tz", "America/New_York")),
        )
        conn.execute("DELETE FROM zones WHERE site_id = %s", (site["id"],))
        for i, z in enumerate(zones):
            conn.execute(
                """INSERT INTO zones (site_id, id, name, capacity, fusion, role, alert_at, sort)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (site["id"], z["id"], z["name"], z["capacity"], z.get("fusion", "sum"),
                 z.get("role"), z.get("alertAt"), i),
            )
        conn.execute("DELETE FROM cameras WHERE site_id = %s", (site["id"],))
        for c in cameras:
            conn.execute(
                """INSERT INTO cameras (id, site_id, zone_id) VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET site_id = EXCLUDED.site_id, zone_id = EXCLUDED.zone_id""",
                (c["id"], site["id"], c["zoneId"]),
            )


def sync_config(conn, config):
    """zones.json -> database. Returns the site id."""
    site = {"kind": "live", **config.get("site", {"id": "live", "name": "Live site"})}
    sync_site(conn, site, config["zones"], config["cameras"])
    return site["id"]


def sites(conn):
    rows = conn.execute("SELECT id, name, kind, tz FROM sites ORDER BY kind, id").fetchall()
    return [{"id": r[0], "name": r[1], "kind": r[2], "tz": r[3]} for r in rows]


def site(conn, site_id):
    return next((s for s in sites(conn) if s["id"] == site_id), None)


def site_config(conn, site_id):
    """Same shape as zones.json, read back from the database."""
    zones = conn.execute(
        """SELECT id, name, capacity, fusion, role, alert_at FROM zones
           WHERE site_id = %s ORDER BY sort, id""",
        (site_id,),
    ).fetchall()
    cams = conn.execute(
        "SELECT id, zone_id FROM cameras WHERE site_id = %s ORDER BY id", (site_id,)
    ).fetchall()
    return {
        "zones": [
            {"id": z[0], "name": z[1], "capacity": z[2], "fusion": z[3], "role": z[4], "alertAt": z[5]}
            for z in zones
        ],
        "cameras": [{"id": c[0], "zoneId": c[1]} for c in cams],
    }


def live_site_id(conn):
    row = conn.execute("SELECT id FROM sites WHERE kind = 'live' ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else None


def insert_events(conn, rows):
    """rows: (epoch_seconds, site_id, zone_id, camera_id, kind, value, detail_dict_or_None)."""
    if not rows:
        return
    with conn.cursor() as cur, cur.copy(
        "COPY events (time, site_id, zone_id, camera_id, kind, value, detail) FROM STDIN"
    ) as copy:
        for ts, site_id, zone_id, cam, kind, value, detail in rows:
            copy.write_row((
                _ts(ts), site_id, zone_id, cam, kind, value,
                None if detail is None else json.dumps(detail),
            ))


def _ts(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc)


def delete_site_events(conn, site_id):
    conn.execute("DELETE FROM events WHERE site_id = %s", (site_id,))


def new_occupancy(conn, site_id, after_id):
    """Occupancy events written since `after_id`, oldest first: (id, epoch, camera_id, value, fps)."""
    return conn.execute(
        """SELECT id, extract(epoch FROM time)::float8, camera_id, value, (detail->>'fps')::float8
           FROM events WHERE id > %s AND site_id = %s AND kind = 'occupancy' ORDER BY id""",
        (after_id, site_id),
    ).fetchall()


def max_event_id(conn):
    return conn.execute("SELECT coalesce(max(id), 0) FROM events").fetchone()[0]


def events(conn, site_id, kind=None, zone_id=None, since=None, until=None, limit=500):
    """Raw events for the REST API, newest first."""
    where, args = ["site_id = %s"], [site_id]
    if kind:
        where.append("kind = %s")
        args.append(kind)
    if zone_id:
        where.append("zone_id = %s")
        args.append(zone_id)
    if since is not None:
        where.append("time >= to_timestamp(%s)")
        args.append(since)
    if until is not None:
        where.append("time <= to_timestamp(%s)")
        args.append(until)
    args.append(limit)
    rows = conn.execute(
        f"""SELECT id, time, zone_id, camera_id, kind, value, detail FROM events
            WHERE {' AND '.join(where)} ORDER BY time DESC, id DESC LIMIT %s""",
        args,
    ).fetchall()
    return [
        {"id": r[0], "time": r[1].isoformat(), "zoneId": r[2], "cameraId": r[3],
         "kind": r[4], "value": r[5], "detail": r[6]}
        for r in rows
    ]

