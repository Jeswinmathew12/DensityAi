from backend.app.processing import LiveState, correct_ts, fuse, smooth, zone_is_stale

CONFIG = {
    "zones": [
        {"id": "a", "name": "A", "capacity": 40, "fusion": "sum"},
        {"id": "b", "name": "B", "capacity": 25, "fusion": "max"},
    ],
    "cameras": [
        {"id": "a1", "zoneId": "a"},
        {"id": "a2", "zoneId": "a"},
        {"id": "b1", "zoneId": "b"},
        {"id": "b2", "zoneId": "b"},
    ],
}


def test_smooth_ignores_single_frame_flicker():
    assert smooth([12, 12, 3, 12, 13]) == 12
    assert smooth([]) == 0


def test_fuse_modes():
    assert fuse([4, 6], "sum") == 10
    assert fuse([4, 6], "max") == 6
    assert fuse([], "sum") == 0


def test_zone_stale_rules():
    # "sum" needs every camera; "max" needs any camera.
    assert zone_is_stale([False, True], "sum")
    assert not zone_is_stale([False, True], "max")
    assert zone_is_stale([True, True], "max")
    assert zone_is_stale([], "sum")  # a zone with no cameras never has data


def test_correct_ts_undoes_jetson_clock_error():
    # Jetson clock is 100 s slow; a sample counted 3 s before sending.
    assert correct_ts(ts=897, sent_at=900, received_at=1000) == 997
    assert correct_ts(ts=None, sent_at=None, received_at=1000) == 1000
    assert correct_ts(ts=990, sent_at=None, received_at=1000) == 990


def test_snapshot_fuses_smooths_and_flags_stale():
    s = LiveState(CONFIG)
    for n in (10, 10, 2, 10, 11):  # 2 is an occlusion dip
        s.add("a1", n, received_at=100)
        s.add("a2", 5, received_at=100)
    s.add("b1", 7, received_at=100)
    s.add("b2", 9, received_at=80)  # silent for 20 s

    a, b = s.zones_snapshot(now=101)
    assert (a["occupancy"], a["stale"], a["cameras"]) == (15, False, 2)
    # b2 is stale, so "max" ignores it and uses b1 alone; the zone is still live.
    assert (b["occupancy"], b["stale"]) == (7, False)
    assert a["lastUpdated"].endswith("Z")


def test_zone_goes_stale_after_ten_seconds():
    s = LiveState(CONFIG)
    s.add("a1", 3, received_at=100)
    s.add("a2", 3, received_at=100)
    assert not s.zones_snapshot(now=110)[0]["stale"]
    assert s.zones_snapshot(now=111)[0]["stale"]


def test_camera_back_from_outage_does_not_reuse_old_counts():
    s = LiveState(CONFIG)
    for _ in range(5):
        s.add("a1", 20, received_at=100)
        s.add("a2", 0, received_at=100)
    # Both cameras were off for over a minute; the room emptied out meanwhile.
    s.add("a1", 3, received_at=200)
    s.add("a2", 0, received_at=200)
    assert s.zones_snapshot(now=200)[0]["occupancy"] == 3
