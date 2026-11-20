import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "jetson"))
from probe_client import DwellTracker  # noqa: E402


def test_dwell_ends_after_person_is_gone_for_a_while():
    d = DwellTracker(gone_after=2)
    assert d.update({1, 2}, 0) == []
    assert d.update({1, 2}, 4) == []
    assert d.update({1}, 10) == [4.0]   # 2 last seen at 4, stayed 4 s
    assert d.update(set(), 11) == []    # 1 just missed a frame
    assert d.update({1}, 11.5) == []    # back again: same visit
    assert d.update(set(), 14) == [11.5]
    assert d.first == {} and d.last == {}


def test_brief_detections_are_not_visits():
    d = DwellTracker(gone_after=2, min_dwell=1)
    d.update({7}, 0)
    d.update({7}, 0.5)
    assert d.update(set(), 5) == []
