"""The collector (writes events) and the web service (reads them) against a real database."""
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.collector import create_collector
from backend.app.main import create_app

# Keys generateZones() returns in src/utils/fakeDataGenerator.js: the data contract.
ZONE_KEYS = {"id", "name", "capacity", "cameras", "occupancy", "lastUpdated", "stale"}
TOKEN = "test-token"
AUTH = {"X-Ingest-Token": TOKEN}
CONFIG = {
    "site": {"id": "booth", "name": "Booth"},
    "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum", "alertAt": 30}],
    "cameras": [{"id": "cam-1", "zoneId": "zone-a"}],
}


@pytest.fixture
def zones_file(tmp_path):
    path = tmp_path / "zones.json"
    path.write_text(json.dumps(CONFIG))
    return path


@pytest.fixture
def collector(db_url, zones_file):
    with TestClient(create_collector(database_url=db_url, zones_path=zones_file, ingest_token=TOKEN)) as c:
        yield c


@pytest.fixture
def client(db_url, zones_file, collector):
    """The web service, started after the collector like on the Jetson."""
    with TestClient(create_app(database_url=db_url, zones_path=zones_file)) as c:
        yield c


def sample(**overrides):
    return {"cameraId": "cam-1", "occupancy": 12, "entriesCum": 30, "exitsCum": 18, "fps": 28.0, **overrides}


def ingest(collector, client, body):
    """Post to the collector, then let the web service read the new events."""
    r = collector.post("/api/ingest", json=body, headers=AUTH)
    client.app.state.poll()
    return r


def kinds(conn):
    return conn.execute("SELECT kind, value FROM events ORDER BY id").fetchall()


def test_zones_match_contract_before_any_data(client):
    [zone] = client.get("/api/zones").json()
    assert set(zone) == ZONE_KEYS
    assert zone["stale"] is True and zone["lastUpdated"] is None


def test_count_goes_collector_to_database_to_web_service(collector, client, conn):
    now = time.time()
    assert ingest(collector, client, sample(ts=now, sentAt=now)).status_code == 204
    [zone] = client.get("/api/zones").json()
    assert (zone["occupancy"], zone["stale"]) == (12, False)
    row = conn.execute("SELECT site_id, zone_id, camera_id, kind, value, detail FROM events").fetchone()
    assert row[:5] == ("booth", "zone-a", "cam-1", "occupancy", 12)
    assert row[5]["fps"] == 28.0


def test_web_service_has_no_ingest_endpoint(client):
    assert client.post("/api/ingest", json=sample(), headers=AUTH).status_code in (404, 405)


def test_batches_are_stored_but_old_samples_stay_out_of_live_view(collector, client, conn):
    now = time.time()
    batch = [sample(ts=now - 120, sentAt=now, occupancy=30), sample(ts=now, sentAt=now, occupancy=5)]
    assert ingest(collector, client, batch).status_code == 204
    assert client.get("/api/zones").json()[0]["occupancy"] == 5
    assert conn.execute("SELECT count(*) FROM events WHERE kind = 'occupancy'").fetchone() == (2,)


def test_cumulative_counters_become_entry_and_exit_events(collector, client, conn):
    # The pipeline restarts between 12 and 0, so its counter starts again: never negative traffic.
    for cum in [10, 12, 0, 3]:
        ingest(collector, client, sample(entriesCum=cum, exitsCum=cum))
    rows = kinds(conn)
    assert [r for r in rows if r[0] == "entry"] == [("entry", 2), ("entry", 3)]
    assert [r for r in rows if r[0] == "exit"] == [("exit", 2), ("exit", 3)]


def test_dwell_times_are_stored(collector, client, conn):
    ingest(collector, client, sample(dwell=[42.5, 7]))
    assert [r for r in kinds(conn) if r[0] == "dwell"] == [("dwell", 42.5), ("dwell", 7)]


def test_crowded_zone_alerts_once(collector, client, conn):
    now = time.time()
    for i in range(3):
        ingest(collector, client, sample(occupancy=35, ts=now + i, sentAt=now + i))
    alerts = conn.execute("SELECT value, detail->>'text' FROM events WHERE kind = 'alert'").fetchall()
    assert alerts == [(35, "Zone A reached 35 people (88% of capacity).")]


def test_ingest_requires_token(collector):
    assert collector.post("/api/ingest", json=sample()).status_code == 401
    assert collector.post("/api/ingest", json=sample(), headers={"X-Ingest-Token": "nope"}).status_code == 401


def test_ingest_rejects_unknown_camera(collector):
    r = collector.post("/api/ingest", json=sample(cameraId="cam-9"), headers=AUTH)
    assert r.status_code == 404 and "zones.json" in r.json()["detail"]


def test_ingest_rejects_negative_counts(collector):
    assert collector.post("/api/ingest", json=sample(occupancy=-1), headers=AUTH).status_code == 422


def test_generic_events_endpoint(collector, conn):
    r = collector.post("/api/events", headers=AUTH, json=[{"zoneId": "zone-a", "kind": "dwell", "value": 30}])
    assert r.status_code == 204
    assert kinds(conn) == [("dwell", 30)]
    bad = collector.post("/api/events", headers=AUTH, json=[{"zoneId": "zone-a", "kind": "selfie"}])
    assert bad.status_code == 422


def test_websocket_sends_zones_on_connect(collector, client):
    ingest(collector, client, sample())
    with client.websocket_connect("/ws/live") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "zones"
    assert set(msg["zones"][0]) == ZONE_KEYS
    assert msg["zones"][0]["occupancy"] == 12


def test_health_lists_cameras(collector, client):
    ingest(collector, client, sample())
    [cam] = client.get("/api/health").json()["cameras"]
    assert (cam["id"], cam["zoneId"], cam["fps"], cam["stale"]) == ("cam-1", "zone-a", 28.0, False)


def test_health_names_the_database(collector, client, db_url):
    assert client.get("/api/health").json()["database"] == "densityai_test"
    assert collector.get("/api/health").json()["database"] == "densityai_test"


def test_web_service_starts_without_the_collector(db_url, zones_file):
    with TestClient(create_app(database_url=db_url, zones_path=zones_file)) as c:
        assert c.get("/api/zones").json()[0]["id"] == "zone-a"


def test_sites_events_and_system(collector, client):
    ingest(collector, client, sample(entriesCum=1))
    ingest(collector, client, sample(entriesCum=4))
    [site] = client.get("/api/sites").json()
    assert (site["id"], site["kind"], site["live"]) == ("booth", "live", True)
    assert site["zones"][0]["alertAt"] == 30
    events = client.get("/api/sites/booth/events", params={"kind": "entry"}).json()
    assert [(e["kind"], e["value"], e["zoneId"]) for e in events] == [("entry", 3, "zone-a")]
    assert client.get("/api/sites/nope/events").status_code == 404
    system = client.get("/api/system").json()
    assert system["collector"]["eventsLastMinute"] == 3
    assert system["database"]["name"] == "densityai_test"


def test_analytics_endpoint_with_live_data(collector, client):
    now = time.time()
    for i in range(5):
        ingest(collector, client, sample(ts=now + i, sentAt=now + i, entriesCum=i, dwell=[40]))
    a = client.get("/api/sites/booth/analytics", params={"days": 7}).json()
    assert a["site"]["id"] == "booth" and a["range"]["days"] == 7
    assert a["kpis"]["visitors"] == 4
    assert a["zones"][0]["avgDwellSec"] == 40 and a["zones"][0]["engagedPct"] == 100
    assert a["dwellBuckets"][1] == {"label": "30 s to 2 min", "count": 5}


ADMIN = {"X-Admin-Password": "admin-pass"}


@pytest.fixture
def preview_dir(tmp_path):
    d = tmp_path / "preview"
    d.mkdir()
    return d


@pytest.fixture
def admin_client(db_url, zones_file, preview_dir):
    app = create_app(database_url=db_url, zones_path=zones_file,
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


def test_serves_built_dashboard_under_any_hostname(tmp_path, db_url, zones_file, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    (build / "index.html").write_text("<title>DensityAI</title>")
    monkeypatch.setenv("DENSITY_STATIC", str(build))
    with TestClient(create_app(database_url=db_url, zones_path=zones_file)) as c:
        for origin in ORIGINS:
            res = c.get("/", headers={"Host": origin.split("//")[1]})
            assert res.status_code == 200 and "DensityAI" in res.text
