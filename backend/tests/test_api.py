import json
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


# The dashboard served by `npm run serve` is opened under whatever address the network gives the
# Jetson (Wi-Fi IP, USB, hostname.local, Tailscale), so same-origin must work for any of them.
ORIGINS = ["http://10.20.30.40:8000", "http://jetson.local:8000", "http://jetson.tail1234.ts.net:8000"]


@pytest.mark.parametrize("origin", ORIGINS)
def test_same_origin_dashboard_works_under_any_address(client, origin):
    headers = {"Host": origin.split("//")[1], "Origin": origin}
    assert client.get("/api/history", headers=headers).status_code == 200
    with client.websocket_connect("/ws/live", headers=headers) as ws:
        assert ws.receive_json()["type"] == "zones"


def test_cors_stays_closed_to_other_sites(client):
    res = client.get("/api/zones", headers={"Origin": "http://example.com"})
    assert "access-control-allow-origin" not in res.headers
    res = client.get("/api/zones", headers={"Origin": "http://localhost:3000"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_serves_built_dashboard_under_any_hostname(tmp_path, db_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<title>DensityAI</title>")
    monkeypatch.setenv("DENSITY_STATIC", str(build))
    with TestClient(create_app(db_path=db_path)) as c:
        for origin in ORIGINS:
            res = c.get("/", headers={"Host": origin.split("//")[1]})
            assert res.status_code == 200 and "DensityAI" in res.text
