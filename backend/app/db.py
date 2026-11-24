"""SQLite storage. Raw 1 Hz samples for now; Phase 2 adds minute rollups for the charts."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS samples (
  ts          REAL    NOT NULL,  -- UTC epoch seconds, already corrected to the backend clock
  camera_id   TEXT    NOT NULL,
  zone_id     TEXT    NOT NULL,  -- zone at write time, so history survives moving a camera
  occupancy   INTEGER NOT NULL,  -- raw ROI count (smoothing only affects the live view)
  entries_cum INTEGER NOT NULL,
  exits_cum   INTEGER NOT NULL,
  fps         REAL
);
CREATE INDEX IF NOT EXISTS samples_zone_ts ON samples (zone_id, ts);
"""


def connect(path):
    # FastAPI runs our async handlers on one event-loop thread, but it may not be the thread
    # that opened the connection.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn


def next_rowid(conn):
    """Rowid the next inserted sample will get (rows are only appended, never deleted)."""
    return conn.execute("SELECT COALESCE(MAX(rowid), 0) + 1 FROM samples").fetchone()[0]


def shift_since(conn, first_rowid, delta):
    """Move samples from `first_rowid` on by `delta` seconds. Returns how many moved."""
    with conn:
        return conn.execute(
            "UPDATE samples SET ts = ts + ? WHERE rowid >= ?", (delta, first_rowid)
        ).rowcount


def insert_samples(conn, rows):
    """rows: (ts, camera_id, zone_id, occupancy, entries_cum, exits_cum, fps) tuples."""
    with conn:
        conn.executemany("INSERT INTO samples VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
