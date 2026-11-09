"""DensityAI backend: takes counts from the Jetson (or simulator) and serves live zone data.

Run from the repo root (or use `npm run backend`):
    uvicorn backend.app.main:create_app --factory --reload --reload-dir backend --port 8000
"""
import asyncio
import hmac
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional, Union
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db, history
from .processing import STALE_AFTER_S, LiveState, correct_ts

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Where jetson/occupancy_pipeline.py --preview-dir keeps each camera's newest frame (in RAM).
DEFAULT_PREVIEW_DIR = "/dev/shm/densityai"
# A preview frame older than this means the pipeline is not running (or has no preview).
PREVIEW_FRESH_S = 5
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


def create_app(db_path=None, zones_path=None, ingest_token=None, tz=None,
               admin_password=None, preview_dir=None):
    db_path = db_path or os.environ.get("DENSITY_DB") or BACKEND_DIR / "density.db"
    zones_path = zones_path or BACKEND_DIR / "zones.json"
    ingest_token = ingest_token or os.environ.get("INGEST_TOKEN")
    # Admin pages (camera preview) are off unless a password is set.
    admin_password = admin_password or os.environ.get("ADMIN_PASSWORD")
    preview_dir = Path(preview_dir or os.environ.get("DENSITY_PREVIEW_DIR") or DEFAULT_PREVIEW_DIR)
    # History is grouped into the room's local hours, not UTC.
    tz = ZoneInfo(tz or os.environ.get("DENSITY_TZ") or "America/New_York")

    config = json.loads(Path(zones_path).read_text())
    state = LiveState(config)
    conn = db.connect(str(db_path))
    clients = set()

    async def broadcast_loop():
        """Once a second, push zones to every open dashboard if anything changed.

        Running on a timer (not per sample) also catches cameras going stale
        when no samples arrive at all.
        """
        last = None
        while True:
            await asyncio.sleep(1)
            zones = state.zones_snapshot(time.time())
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
        if not ingest_token:
            log.warning("INGEST_TOKEN is not set, so /api/ingest accepts posts from anyone")
        task = asyncio.create_task(broadcast_loop())
        yield
        task.cancel()
        conn.close()

    app = FastAPI(title="DensityAI", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Handlers are async so they share the event-loop thread with broadcast_loop and
    # never touch `state` concurrently.

    @app.post("/api/ingest", status_code=204)
    async def ingest(
        body: Union[List[Sample], Sample],
        x_ingest_token: Optional[str] = Header(None),
    ):
        if ingest_token and x_ingest_token != ingest_token:
            raise HTTPException(401, "Bad or missing X-Ingest-Token")
        samples = body if isinstance(body, list) else [body]
        unknown = {s.cameraId for s in samples} - state.camera_zone.keys()
        if unknown:
            raise HTTPException(404, f"Unknown camera(s) {sorted(unknown)}. Add them to backend/zones.json.")

        now = time.time()
        rows = []
        for s in samples:
            ts = correct_ts(s.ts, s.sentAt, now)
            rows.append((ts, s.cameraId, state.camera_zone[s.cameraId], s.occupancy, s.entriesCum, s.exitsCum, s.fps))
            # Only fresh samples feed the live view; replayed or backfilled ones just go to history.
            if now - ts <= STALE_AFTER_S:
                state.add(s.cameraId, s.occupancy, now, s.fps)
        db.insert_samples(conn, rows)
        return Response(status_code=204)

    @app.get("/api/zones")
    async def zones():
        return state.zones_snapshot(time.time())

    @app.get("/api/history")
    async def get_history():
        return history.build(conn, config, time.time(), tz)

    @app.get("/api/health")
    async def health():
        return {
            "cameras": state.cameras_snapshot(time.time()),
            "dashboards": len(clients),
            # Lets the simulator and reset script see which history this backend is writing.
            "database": Path(db_path).name,
        }

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
            for cam_id, zone_id in state.camera_zone.items()
        ]

    @app.get("/api/admin/preview/{camera_id}")
    async def admin_preview(camera_id: str, x_admin_password: Optional[str] = Header(None)):
        require_admin(x_admin_password)
        # Only known camera ids, so the name can't point outside preview_dir.
        if camera_id not in state.camera_zone:
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
    async def live(ws: WebSocket):
        await ws.accept()
        clients.add(ws)
        try:
            await ws.send_json({"type": "zones", "zones": state.zones_snapshot(time.time())})
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
