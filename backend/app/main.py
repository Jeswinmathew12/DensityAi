"""DensityAI web service: the REST API (and live WebSocket) the dashboard talks to.

It only reads the PostgreSQL database that the collector (collector.py) fills. It never talks to
the Jetson, so in a real deployment it can run on any server that can reach the database.

Run from the repo root (or use `npm run backend`):
    uvicorn backend.app.main:create_app --factory --reload --reload-dir backend --port 8000

API docs (try the endpoints in a browser): http://localhost:8000/docs
"""
import asyncio
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import analytics, db, history
from .processing import STALE_AFTER_S, LiveState

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Where jetson/occupancy_pipeline.py --preview-dir keeps each camera's newest frame (in RAM).
DEFAULT_PREVIEW_DIR = "/dev/shm/densityai"
# A preview frame older than this means the pipeline is not running (or has no preview).
PREVIEW_FRESH_S = 5
# Store analytics scan weeks of events, so each answer is reused for this long.
ANALYTICS_CACHE_S = 60
# How often the web service re-reads the live site's zones and cameras from the database.
CONFIG_REFRESH_S = 10
log = logging.getLogger("uvicorn.error")


def create_app(database_url=None, zones_path=None, tz=None, admin_password=None, preview_dir=None):
    zones_path = zones_path or BACKEND_DIR / "zones.json"
    # Admin pages (camera preview) are off unless a password is set.
    admin_password = admin_password or os.environ.get("ADMIN_PASSWORD")
    preview_dir = Path(preview_dir or os.environ.get("DENSITY_PREVIEW_DIR") or DEFAULT_PREVIEW_DIR)
    # History is grouped into the store's local hours, not UTC.
    tz = ZoneInfo(tz or os.environ.get("DENSITY_TZ") or "America/New_York")

    conn = db.connect(database_url)
    # The collector normally writes the live site's config. If it hasn't run yet, use zones.json
    # so the dashboard still shows the zones (as offline).
    site_id = db.live_site_id(conn) or db.sync_config(conn, json.loads(Path(zones_path).read_text()))
    live = {"config": db.site_config(conn, site_id)}
    live["state"] = LiveState(live["config"])
    clients = set()
    cache = {}
    status = {"lastPoll": None, "lastEventId": db.max_event_id(conn)}

    def poll():
        """Feed occupancy events the collector wrote since the last poll into the live view."""
        now = time.time()
        config = db.site_config(conn, site_id) if now - status.get("configAt", 0) > CONFIG_REFRESH_S else None
        if config is not None:
            status["configAt"] = now
            if config != live["config"]:
                live["config"], live["state"] = config, LiveState(config)
        for event_id, ts, cam, value, fps in db.new_occupancy(conn, site_id, status["lastEventId"]):
            status["lastEventId"] = event_id
            # Only fresh counts feed the live view; replayed or backfilled ones are history only.
            if now - ts <= STALE_AFTER_S and cam in live["state"].camera_zone:
                live["state"].add(cam, round(value), now, fps)
        status["lastPoll"] = now

    async def broadcast_loop():
        """Once a second, read new counts and push zones to every open dashboard if anything changed.

        Running on a timer also catches cameras going stale when no counts arrive at all.
        """
        last = None
        while True:
            await asyncio.sleep(1)
            try:
                poll()
            except Exception as e:  # database restarting: keep the last state, try again next second
                log.warning("Reading new events failed: %s", e)
                continue
            zones = live["state"].zones_snapshot(time.time())
            if zones == last:
                continue
            last = zones
            for ws in list(clients):
                try:
                    await ws.send_json({"type": "zones", "zones": zones})
                except Exception:
                    clients.discard(ws)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(broadcast_loop())
        yield
        task.cancel()
        conn.close()

    app = FastAPI(
        title="DensityAI web service",
        description="Occupancy, traffic and store analytics, read from the DensityAI events database.",
        lifespan=lifespan,
    )
    # Only the dev server (port 3000) is cross-origin. The built dashboard is served from this
    # same port, so it's same-origin under any hostname or IP and needs no CORS entry; /ws/live
    # doesn't check Origin either. Keep it that way so `npm run serve` works on any network.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.poll = poll  # lets tests read new events without waiting for the timer

    # Handlers are async so they share the event-loop thread with broadcast_loop and
    # never touch the connection or live state concurrently.

    @app.get("/api/zones")
    async def zones():
        """Live zones of the camera site, same shape as generateZones() in the dashboard."""
        return live["state"].zones_snapshot(time.time())

    @app.get("/api/history")
    async def get_history():
        """The camera site's last 24 hours: trends, traffic, today's stats and insights."""
        return history.build(conn, site_id, live["config"], time.time(), tz)

    @app.get("/api/health")
    async def health():
        return {
            "role": "web",
            "cameras": live["state"].cameras_snapshot(time.time()),
            "dashboards": len(clients),
            # Lets the simulator and reset script see which history this backend is reading.
            "database": db.database_name(conn),
        }

    @app.get("/api/system")
    async def system():
        """Each hop from camera to dashboard and whether it's working, for the System page."""
        now = time.time()
        row = conn.execute(
            """SELECT count(*), extract(epoch FROM max(time))::float8 FROM events
               WHERE site_id = %s AND time > now() - interval '1 minute'""",
            (site_id,),
        ).fetchone()
        total = conn.execute("SELECT count(*) FROM events").fetchone()[0]
        cams = live["state"].cameras_snapshot(now)
        return {
            "site": db.site(conn, site_id),
            "cameras": cams,
            "collector": {"eventsLastMinute": row[0], "lastEventAt": row[1]},
            "database": {
                "name": db.database_name(conn),
                "timescale": db.has_timescale(conn),
                "events": total,
            },
            "web": {"lastPoll": status["lastPoll"], "dashboards": len(clients)},
        }

    def get_site(sid):
        s = db.site(conn, sid)
        if s is None:
            raise HTTPException(404, f"Unknown site {sid!r}")
        return s

    @app.get("/api/sites")
    async def sites():
        """Every site in the database: the live camera site and any sample stores."""
        return [{**s, "live": s["id"] == site_id, **db.site_config(conn, s["id"])} for s in db.sites(conn)]

    @app.get("/api/sites/{sid}/analytics")
    async def site_analytics(sid: str, days: int = Query(28, ge=1, le=120)):
        """Busiest hours and days, zone reach, dwell time, alerts and recommendations."""
        s = get_site(sid)
        key = (sid, days)
        hit = cache.get(key)
        if hit and time.time() - hit[0] < ANALYTICS_CACHE_S:
            return hit[1]
        result = analytics.build(conn, s, db.site_config(conn, sid), time.time(), ZoneInfo(s["tz"]), days)
        cache[key] = (time.time(), result)
        return result

    @app.get("/api/sites/{sid}/events")
    async def site_events(
        sid: str,
        kind: Optional[str] = Query(None, pattern="^(occupancy|entry|exit|dwell|alert)$"),
        zone: Optional[str] = None,
        since: Optional[float] = Query(None, description="epoch seconds"),
        until: Optional[float] = Query(None, description="epoch seconds"),
        limit: int = Query(100, ge=1, le=5000),
    ):
        """Raw events, newest first."""
        get_site(sid)
        return db.events(conn, sid, kind, zone, since, until, limit)

    def require_admin(password):
        if not admin_password:
            raise HTTPException(404, "Admin is off. Set ADMIN_PASSWORD in /etc/densityai.env.")
        if not password or not hmac.compare_digest(password.encode(), admin_password.encode()):
            raise HTTPException(401, "Wrong admin password")

    def fresh_preview(camera_id):
        """Path of the camera's newest preview frame, or None if there is no recent one."""
        path = preview_dir / f"{camera_id}.jpg"
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return None
        return path if age <= PREVIEW_FRESH_S else None

    @app.get("/api/admin/cameras")
    async def admin_cameras(x_admin_password: Optional[str] = Header(None)):
        """Cameras from zones.json, and whether each has a live preview. Doubles as the login check."""
        require_admin(x_admin_password)
        return [
            {"id": cam_id, "zoneId": zone_id, "preview": fresh_preview(cam_id) is not None}
            for cam_id, zone_id in live["state"].camera_zone.items()
        ]

    @app.get("/api/admin/preview/{camera_id}")
    async def admin_preview(camera_id: str, x_admin_password: Optional[str] = Header(None)):
        require_admin(x_admin_password)
        # Only known camera ids, so the name can't point outside preview_dir.
        if camera_id not in live["state"].camera_zone:
            raise HTTPException(404, "Unknown camera")
        path = fresh_preview(camera_id)
        if path is None:
            raise HTTPException(404, "No live preview for this camera")
        try:
            data = path.read_bytes()
        except OSError:
            raise HTTPException(404, "No live preview for this camera")
        return Response(data, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.websocket("/ws/live")
    async def live_socket(ws: WebSocket):
        await ws.accept()
        clients.add(ws)
        try:
            await ws.send_json({"type": "zones", "zones": live["state"].zones_snapshot(time.time())})
            while True:
                await ws.receive_text()  # dashboards don't send anything; this just waits for close
        except WebSocketDisconnect:
            pass
        finally:
            clients.discard(ws)

    # Serve the built dashboard (`npm run build:live`) from the same port, so any device that
    # can reach the backend can open it. Mounted last so /api and /ws take priority.
    build_dir = Path(os.environ.get("DENSITY_STATIC") or BACKEND_DIR.parent / "build")
    if build_dir.is_dir():
        app.mount("/", StaticFiles(directory=build_dir, html=True), name="dashboard")

    return app
