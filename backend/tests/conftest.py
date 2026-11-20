"""Tests run against a real PostgreSQL database, which they empty first.

Default: postgresql:///densityai_test (created if missing). Override with TEST_DATABASE_URL.
Without a reachable PostgreSQL server the database tests are skipped, not failed.
"""
import os

import psycopg
import pytest

from backend.app import db

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql:///densityai_test")


@pytest.fixture
def db_url():
    try:
        conn = db.connect(TEST_URL)
    except psycopg.OperationalError as e:
        pytest.skip(f"PostgreSQL not reachable at {TEST_URL}: {e}")
    conn.execute("DROP TABLE IF EXISTS events, cameras, zones, sites CASCADE")
    conn.close()
    return TEST_URL


@pytest.fixture
def conn(db_url):
    c = db.connect(db_url)
    yield c
    c.close()
