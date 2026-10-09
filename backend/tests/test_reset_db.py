from backend.reset_db import reset


def test_reset_moves_database_to_backups(tmp_path):
    db = tmp_path / "density.db"
    db.write_bytes(b"history")
    dest = reset(db, tmp_path / "backups", "20261008-120000")
    assert dest == tmp_path / "backups" / "density-20261008-120000.db"
    assert dest.read_bytes() == b"history" and not db.exists()


def test_reset_without_database_does_nothing(tmp_path):
    assert reset(tmp_path / "density.db", tmp_path / "backups", "x") is None
    assert not (tmp_path / "backups").exists()
