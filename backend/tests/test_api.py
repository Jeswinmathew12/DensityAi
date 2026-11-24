import json
import os
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app

# Keys generateZones() returns in src/utils/fakeDataGenerator.js: the data contract.
ZONE_KEYS = {"id", "name", "capacity", "cameras", "occupancy", "lastUpdated", "stale"}
TOKEN = "test-token"
AUTH = {"X-Ingest-Token": TOKEN}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def client(tmp_path, db_path):
    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({
        "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum"}],
        "cameras": [{"id": "cam-1", "zoneId": "zone-a"}],
    }))
    with TestClient(create_app(db_path=db_path, zones_path=zones, ingest_token=TOKEN)) as c:
        yield c


def sample(**overrides):
    return {"cameraId": "cam-1", "occupancy": 12, "entriesCum": 30, "exitsCum": 18, "fps": 28.0, **overrides}


def test_zones_match_contract_before_any_data(client):
    [zone] = client.get("/api/zones").json()
    assert set(zone) == ZONE_KEYS
    assert zone["stale"] is True and zone["lastUpdated"] is None


def test_ingest_updates_live_zone_and_stores_sample(client, db_path):
    now = time.time()
    r = client.post("/api/ingest", json=sample(ts=now, sentAt=now), headers=AUTH)
    assert r.status_code == 204

    [zone] = client.get("/api/zones").json()
    assert (zone["occupancy"], zone["stale"]) == (12, False)
    rows = sqlite3.connect(db_path).execute("SELECT camera_id, zone_id, occupancy FROM samples").fetchall()
    assert rows == [("cam-1", "zone-a", 12)]


def test_ingest_accepts_batches_and_keeps_old_samples_out_of_live_view(client, db_path):
    now = time.time()
    batch = [sample(ts=now - 120, sentAt=now, occupancy=30), sample(ts=now, sentAt=now, occupancy=5)]
    assert client.post("/api/ingest", json=batch, headers=AUTH).status_code == 204

    assert client.get("/api/zones").json()[0]["occupancy"] == 5
    assert sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM samples").fetchone() == (2,)


def test_ingest_requires_token(client):
    assert client.post("/api/ingest", json=sample()).status_code == 401
    assert client.post("/api/ingest", json=sample(), headers={"X-Ingest-Token": "nope"}).status_code == 401


def test_ingest_rejects_unknown_camera(client):
    r = client.post("/api/ingest", json=sample(cameraId="cam-9"), headers=AUTH)
    assert r.status_code == 404 and "zones.json" in r.json()["detail"]


def test_ingest_rejects_negative_counts(client):
    assert client.post("/api/ingest", json=sample(occupancy=-1), headers=AUTH).status_code == 422


def test_websocket_sends_zones_on_connect(client):
    client.post("/api/ingest", json=sample(), headers=AUTH)
    with client.websocket_connect("/ws/live") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "zones"
    assert set(msg["zones"][0]) == ZONE_KEYS
    assert msg["zones"][0]["occupancy"] == 12


def test_health_lists_cameras(client):
    client.post("/api/ingest", json=sample(), headers=AUTH)
    [cam] = client.get("/api/health").json()["cameras"]
    assert (cam["id"], cam["zoneId"], cam["fps"], cam["stale"]) == ("cam-1", "zone-a", 28.0, False)


def test_health_names_the_database(client):
    assert client.get("/api/health").json()["database"] == "test.db"


ADMIN = {"X-Admin-Password": "admin-pass"}


@pytest.fixture
def preview_dir(tmp_path):
    d = tmp_path / "preview"
    d.mkdir()
    return d


@pytest.fixture
def admin_client(tmp_path, db_path, preview_dir):
    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({
        "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum"}],
        "cameras": [{"id": "cam-1", "zoneId": "zone-a"}],
    }))
    app = create_app(db_path=db_path, zones_path=zones, ingest_token=TOKEN,
                     admin_password="admin-pass", preview_dir=preview_dir)
    with TestClient(app) as c:
        yield c


def test_admin_is_off_without_a_password(client):
    assert client.get("/api/admin/cameras", headers=ADMIN).status_code == 404
    assert client.get("/api/admin/preview/cam-1", headers=ADMIN).status_code == 404


def test_admin_rejects_a_wrong_or_missing_password(admin_client):
    assert admin_client.get("/api/admin/cameras").status_code == 401
    assert admin_client.get("/api/admin/cameras", headers={"X-Admin-Password": "nope"}).status_code == 401
    assert admin_client.get("/api/admin/preview/cam-1").status_code == 401


def test_admin_serves_a_fresh_preview(admin_client, preview_dir):
    assert admin_client.get("/api/admin/cameras", headers=ADMIN).json() == [
        {"id": "cam-1", "zoneId": "zone-a", "preview": False}]
    assert admin_client.get("/api/admin/preview/cam-1", headers=ADMIN).status_code == 404

    (preview_dir / "cam-1.jpg").write_bytes(b"\xff\xd8jpeg")
    assert admin_client.get("/api/admin/cameras", headers=ADMIN).json()[0]["preview"] is True
    r = admin_client.get("/api/admin/preview/cam-1", headers=ADMIN)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg" and r.headers["cache-control"] == "no-store"
    assert r.content == b"\xff\xd8jpeg"


def test_admin_ignores_stale_previews_and_unknown_cameras(admin_client, preview_dir):
    frame = preview_dir / "cam-1.jpg"
    frame.write_bytes(b"\xff\xd8jpeg")
    old = time.time() - 60
    os.utime(frame, (old, old))
    assert admin_client.get("/api/admin/preview/cam-1", headers=ADMIN).status_code == 404
    assert admin_client.get("/api/admin/preview/..%2Fsecret", headers=ADMIN).status_code == 404
    assert admin_client.get("/api/admin/preview/cam-9", headers=ADMIN).status_code == 404


def test_clock_step_moves_this_runs_samples_only(tmp_path, monkeypatch):
    """Boot with a stale clock, then NTP sync: history written before the sync is moved."""
    from types import SimpleNamespace
    import backend.app.main as main

    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps({
        "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum"}],
        "cameras": [{"id": "cam-1", "zoneId": "zone-a"}],
    }))
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    main.db.connect(str(db_path))  # create the table
    conn.execute("INSERT INTO samples VALUES (500, 'cam-1', 'zone-a', 1, 0, 0, NULL)")  # earlier run
    conn.commit()

    clock = {"wall": 1000.0, "mono": 10.0}
    monkeypatch.setattr(main, "time", SimpleNamespace(
        time=lambda: clock["wall"], monotonic=lambda: clock["mono"]))
    with TestClient(main.create_app(db_path=db_path, zones_path=zones)) as c:
        c.post("/api/ingest", json=sample(ts=1000, sentAt=1000))
        clock.update(wall=1001 + 86400, mono=11)  # NTP: the real date is a day later
        c.post("/api/ingest", json=sample(ts=1001 + 86400, sentAt=1001 + 86400))
        [zone] = c.get("/api/zones").json()

    rows = conn.execute("SELECT ts FROM samples ORDER BY rowid").fetchall()
    assert rows == [(500,), (1000 + 86400,), (1001 + 86400,)]
    assert zone["stale"] is False
