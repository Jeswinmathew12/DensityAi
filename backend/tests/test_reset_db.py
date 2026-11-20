from backend.app import db
from backend.reset_db import reset


def test_reset_moves_one_sites_events_to_a_backup_table(conn):
    db.insert_events(conn, [(1e9, "live", "zone-a", "cam-1", "occupancy", 3, None),
                            (1e9, "sample-store", "produce", None, "occupancy", 5, None)])
    table, moved = reset(conn, "live", "20261008_120000")
    assert (table, moved) == ("events_backup_20261008_120000", 1)
    assert conn.execute("SELECT site_id FROM events").fetchall() == [("sample-store",)]
    assert conn.execute(f"SELECT site_id, value FROM {table}").fetchall() == [("live", 3)]
    conn.execute(f"DROP TABLE {table}")


def test_reset_with_nothing_to_move(conn):
    table, moved = reset(conn, "live", "20261008_120001")
    assert moved == 0
    conn.execute(f"DROP TABLE {table}")
