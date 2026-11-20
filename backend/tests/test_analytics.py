from datetime import datetime
from zoneinfo import ZoneInfo

from backend import mock_store
from backend.app import analytics, db

NY = ZoneInfo("America/New_York")
NOW = datetime(2026, 11, 20, 15, 30, tzinfo=NY).timestamp()
# Keys generateStoreAnalytics() returns in src/utils/fakeDataGenerator.js: the data contract.
KEYS = {"site", "range", "kpis", "daily", "byWeekday", "byHour", "heatmap", "zones", "zoneShare",
        "dwellBuckets", "alerts", "recommendations"}
KPI_KEYS = {"visitors", "visitorsPerDay", "visitorsChangePct", "avgDwellSec", "conversionPct",
            "busiest", "alerts"}


def build(conn, days=14):
    site = db.site(conn, mock_store.SITE["id"])
    return analytics.build(conn, site, db.site_config(conn, site["id"]), NOW, NY, days)


def test_sample_store_analytics(conn):
    db.sync_site(conn, mock_store.SITE, mock_store.ZONES)
    db.insert_events(conn, mock_store.generate(2, 7, NOW, NY))
    a = build(conn)
    assert set(a) == KEYS and set(a["kpis"]) == KPI_KEYS
    assert a["range"] == {"from": "2026-11-07", "to": "2026-11-20", "days": 14, "daysWithData": 14}
    k = a["kpis"]
    assert 700 < k["visitorsPerDay"] < 1600
    assert 75 < k["conversionPct"] < 95
    # Weekends are the busiest days, and the store is closed overnight.
    by_day = {d["day"]: d["visitors"] for d in a["byWeekday"]}
    assert by_day["Sat"] > by_day["Tue"]
    assert a["byHour"][0]["hour"] == 7 and a["byHour"][-1]["hour"] == 21
    assert len(a["heatmap"]) == 7 and all(len(r["cells"]) == 15 for r in a["heatmap"])
    shares = a["zoneShare"]
    assert "entrance" not in {s["zoneId"] for s in shares}
    assert 98 <= sum(s["sharePct"] for s in shares) <= 102
    assert sum(b["count"] for b in a["dwellBuckets"]) > 0
    kinds = {r["kind"] for r in a["recommendations"]}
    assert {"staffing", "layout"} <= kinds
    assert len(a["daily"]) == 14 and a["daily"][-1]["date"] == "2026-11-20"


def test_site_without_data_has_no_numbers(conn):
    db.sync_site(conn, mock_store.SITE, mock_store.ZONES)
    a = build(conn)
    assert set(a["kpis"].values()) <= {None, 0}
    assert a["heatmap"][0]["cells"] == [] and a["zoneShare"] == [] and a["dwellBuckets"] == []
    assert all(d["visitors"] is None for d in a["daily"])
    assert a["recommendations"] == []
