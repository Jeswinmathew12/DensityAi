import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from backend.app import db, history
from backend.app.main import create_app

NY = ZoneInfo("America/New_York")
# Thursday 3:30 PM in New York. The 24 hourly buckets run 4 PM yesterday .. 3 PM today,
# so the last bucket (index 23) is the current hour and 9 AM today is index 17.
NOW = datetime(2026, 10, 8, 15, 30, tzinfo=NY).timestamp()
CONFIG = {
    "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum"}],
    "cameras": [{"id": "cam-1", "zoneId": "zone-a"}],
}


def at(hour, minute=0, day=8):
    return datetime(2026, 10, day, hour, minute, tzinfo=NY).timestamp()


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    yield c
    c.close()


def add(conn, ts, occ, cam="cam-1", zone="zone-a", ins=0, outs=0):
    db.insert_samples(conn, [(ts, cam, zone, occ, ins, outs, 28.0)])


def test_empty_database_has_no_data_rather_than_zeros(conn):
    h = history.build(conn, CONFIG, NOW, NY)
    trend = h["trends"]["zone-a"]
    assert len(trend) == 24 and len(h["traffic"]) == 24
    assert [p["hour"] for p in trend[-3:]] == [13, 14, 15]
    assert all(p["occupancy"] is None for p in trend)
    assert all(t["entries"] is None and t["exits"] is None for t in h["traffic"])
    assert h["stats"] == {"peakHour": None, "avgOccupancy": None, "totalVisitors": None}
    assert h["insights"] == []


def test_hours_without_data_are_gaps_not_zero(conn):
    add(conn, at(12, 10), 10)
    add(conn, at(12, 40), 14)
    add(conn, at(14, 5), 6)
    trend = history.build(conn, CONFIG, NOW, NY)["trends"]["zone-a"]
    assert [p["occupancy"] for p in trend[-4:]] == [12, None, 6, None]


def test_counter_reset_is_not_negative_traffic(conn):
    # The pipeline restarts between 12 and 0, so its cumulative counter starts again.
    for minute, cum in enumerate([10, 12, 0, 3]):
        add(conn, at(14, minute), 5, ins=cum, outs=cum)
    t = history.build(conn, CONFIG, NOW, NY)["traffic"][-2]
    assert (t["hour"], t["entries"], t["exits"]) == (14, 5, 5)


def test_sum_zone_needs_every_camera(conn):
    config = {
        "zones": [{"id": "zone-a", "name": "Zone A", "capacity": 40, "fusion": "sum"}],
        "cameras": [{"id": "cam-1", "zoneId": "zone-a"}, {"id": "cam-2", "zoneId": "zone-a"}],
    }
    add(conn, at(13, 0), 4)  # cam-2 silent: the total would be wrong, so no data
    add(conn, at(14, 0), 4)
    add(conn, at(14, 0), 6, cam="cam-2")
    trend = history.build(conn, config, NOW, NY)["trends"]["zone-a"]
    assert [p["occupancy"] for p in trend[-3:-1]] == [None, 10]


def test_stats_cover_today_only(conn):
    add(conn, at(22, day=7), 40)  # yesterday evening: in the trend, not in today's stats
    add(conn, at(9), 4, ins=0)
    add(conn, at(9, 1), 6, ins=3)
    add(conn, at(14), 20, ins=3)
    h = history.build(conn, CONFIG, NOW, NY)
    assert h["stats"] == {"peakHour": "2:00 PM", "avgOccupancy": 10, "totalVisitors": 3}
    assert h["trends"]["zone-a"][6]["occupancy"] == 40


def test_visitors_is_none_when_line_crossing_is_off(conn):
    add(conn, at(14), 8)
    assert history.build(conn, CONFIG, NOW, NY)["stats"]["totalVisitors"] is None


def test_insights_for_busiest_hour_and_offline_gap(conn):
    for minute in range(60):
        add(conn, at(13, minute), 5)
    for minute in range(20, 30):
        add(conn, at(15, minute), 12)
    texts = [i["text"] for i in history.build(conn, CONFIG, NOW, NY)["insights"]]
    assert texts == [
        "Zone A has been busiest at 3:00 PM today (avg 12 people).",
        "Zone A was offline 2:00 PM to 3:20 PM.",
    ]


def test_insight_for_camera_that_is_still_offline(conn):
    add(conn, at(15, 0), 5)
    texts = [i["text"] for i in history.build(conn, CONFIG, NOW, NY)["insights"]]
    assert texts == ["Zone A has had no camera data since 3:01 PM."]


def test_history_survives_backend_restart(tmp_path):
    zones = tmp_path / "zones.json"
    zones.write_text(json.dumps(CONFIG))
    db_path = tmp_path / "test.db"
    now = time.time()
    with TestClient(create_app(db_path=db_path, zones_path=zones)) as c:
        c.post("/api/ingest", json={"cameraId": "cam-1", "occupancy": 12, "ts": now, "sentAt": now})

    with TestClient(create_app(db_path=db_path, zones_path=zones)) as c:
        h = c.get("/api/history").json()
        [zone] = c.get("/api/zones").json()
    # The live view waits for the camera to post again instead of showing an old count.
    assert zone["stale"] is True and zone["lastUpdated"] is None
    assert set(h) == {"trends", "traffic", "stats", "insights"}
    assert h["trends"]["zone-a"][-1]["occupancy"] == 12
    assert h["stats"]["avgOccupancy"] == 12
