"""DensityAI collector: the only program the Jetson talks to.

It receives counts from the camera pipeline (or the simulator), turns them into rows in the
`events` table in PostgreSQL, and does nothing else. The web service (main.py) reads those rows;
the dashboard only talks to the web service. In a real deployment the Jetson sits in the store
and the collector, database and web service run on a server.

Run from the repo root (or use `npm run collector`):
    uvicorn backend.app.collector:create_collector --factory --port 8001
"""
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Union

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

from . import db
from .processing import STALE_AFTER_S, LiveState, correct_ts

BACKEND_DIR = Path(__file__).resolve().parent.parent
# After an alert, a zone has to drop below its alert level and stay quiet this long before it
# can alert again, so a crowd hovering at the limit doesn't fill the list.
ALERT_COOLDOWN_S = 600
log = logging.getLogger("uvicorn.error")


class Sample(BaseModel):
    """One count from one camera. Field names match the JSON the probe sends."""

    cameraId: str
    occupancy: int = Field(ge=0)
    entriesCum: int = Field(0, ge=0)
    exitsCum: int = Field(0, ge=0)
    ts: Optional[float] = None  # when it was counted (Jetson clock, epoch seconds)
    sentAt: Optional[float] = None  # when the request went out (Jetson clock)
    fps: Optional[float] = None
    # Seconds each person who just left the zone spent in it (needs the pipeline's --tracker).
    dwell: List[float] = Field(default_factory=list)


class Event(BaseModel):
    """A ready-made event, for sensors other than the camera pipeline."""

    zoneId: str
    kind: str = Field(pattern="^(occupancy|entry|exit|dwell|alert)$")
    value: float = 1
    ts: Optional[float] = None
    cameraId: Optional[str] = None
    detail: Optional[dict] = None


def delta(cum, last):
    """New crossings since the previous sample. A counter that drops means the pipeline
    restarted and began again from 0, so the new value is the count since the restart."""
    if last is None:
        return 0
    return cum - last if cum >= last else cum


class Collector:
    """Turns samples into event rows. No I/O, so it's easy to test."""

    def __init__(self, site_id, config):
        self.site_id = site_id
        self.config = config
        self.camera_zone = {c["id"]: c["zoneId"] for c in config["cameras"]}
        self.zones = {z["id"]: z for z in config["zones"]}
        self.live = LiveState(config)
        self.last_cum = {}  # camera_id -> (entries_cum, exits_cum)
        self.alerted = {}  # zone_id -> time of the last alert
        self.above = set()  # zones currently at or over their alert level

    def rows_for(self, s: Sample, now):
        ts = correct_ts(s.ts, s.sentAt, now)
        zone = self.camera_zone[s.cameraId]
        rows = [(ts, self.site_id, zone, s.cameraId, "occupancy", s.occupancy,
                 {"fps": s.fps, "entriesCum": s.entriesCum, "exitsCum": s.exitsCum})]
        last_in, last_out = self.last_cum.get(s.cameraId, (None, None))
        ins, outs = delta(s.entriesCum, last_in), delta(s.exitsCum, last_out)
        self.last_cum[s.cameraId] = (s.entriesCum, s.exitsCum)
        if ins:
            rows.append((ts, self.site_id, zone, s.cameraId, "entry", ins, None))
        if outs:
            rows.append((ts, self.site_id, zone, s.cameraId, "exit", outs, None))
        for seconds in s.dwell:
            if seconds > 0:
                rows.append((ts, self.site_id, zone, s.cameraId, "dwell", round(seconds, 1), None))
        if now - ts <= STALE_AFTER_S:
            self.live.add(s.cameraId, s.occupancy, now)
        return rows

    def alerts(self, now):
        """Alert rows for zones that just reached their alertAt level (from zones.json)."""
        rows = []
        for z in self.live.zones_snapshot(now):
            limit = self.zones[z["id"]].get("alertAt")
            if not limit or z["stale"]:
                continue
            if z["occupancy"] < limit:
                self.above.discard(z["id"])
                continue
            if z["id"] in self.above or now - self.alerted.get(z["id"], -1e12) < ALERT_COOLDOWN_S:
                continue
            self.above.add(z["id"])
            self.alerted[z["id"]] = now
            pct = round(100 * z["occupancy"] / z["capacity"])
            text = f"{z['name']} reached {z['occupancy']} people ({pct}% of capacity)."
            rows.append((now, self.site_id, z["id"], None, "alert", z["occupancy"], {"text": text}))
        return rows


def create_collector(database_url=None, zones_path=None, ingest_token=None):
    zones_path = zones_path or BACKEND_DIR / "zones.json"
    ingest_token = ingest_token or os.environ.get("INGEST_TOKEN")
    config = json.loads(Path(zones_path).read_text())
    conn = db.connect(database_url)
    site_id = db.sync_config(conn, config)
    collector = Collector(site_id, config)
    stats = {"events": 0, "lastWrite": None}

    @asynccontextmanager
    async def lifespan(app):
        if not ingest_token:
            log.warning("INGEST_TOKEN is not set, so /api/ingest accepts posts from anyone")
        log.info("Collector writing site %r to database %r", site_id, db.database_name(conn))
        yield
        conn.close()

    app = FastAPI(title="DensityAI collector", lifespan=lifespan)

    def check_token(token):
        if ingest_token and token != ingest_token:
            raise HTTPException(401, "Bad or missing X-Ingest-Token")

    def write(rows, now):
        db.insert_events(conn, rows)
        stats["events"] += len(rows)
        stats["lastWrite"] = now

    @app.post("/api/ingest", status_code=204)
    async def ingest(body: Union[List[Sample], Sample], x_ingest_token: Optional[str] = Header(None)):
        """Counts from the Jetson: one sample per camera per second, or a batch of them."""
        check_token(x_ingest_token)
        samples = body if isinstance(body, list) else [body]
        unknown = {s.cameraId for s in samples} - collector.camera_zone.keys()
        if unknown:
            raise HTTPException(404, f"Unknown camera(s) {sorted(unknown)}. Add them to backend/zones.json.")
        now = time.time()
        rows = [r for s in samples for r in collector.rows_for(s, now)]
        rows += collector.alerts(now)
        write(rows, now)
        return Response(status_code=204)

    @app.post("/api/events", status_code=204)
    async def add_events(body: List[Event], x_ingest_token: Optional[str] = Header(None)):
        """Ready-made events (any kind) for this site, e.g. from another kind of sensor."""
        check_token(x_ingest_token)
        unknown = {e.zoneId for e in body} - collector.zones.keys()
        if unknown:
            raise HTTPException(404, f"Unknown zone(s) {sorted(unknown)}")
        now = time.time()
        write([(e.ts or now, site_id, e.zoneId, e.cameraId, e.kind, e.value, e.detail) for e in body], now)
        return Response(status_code=204)

    @app.get("/api/health")
    async def health():
        return {
            "role": "collector",
            "site": site_id,
            "database": db.database_name(conn),
            "eventsWritten": stats["events"],
            "lastWrite": stats["lastWrite"],
            "cameras": collector.live.cameras_snapshot(time.time()),
        }

    return app
