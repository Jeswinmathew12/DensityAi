"""Starts the live camera's history over: copies its events into a backup table
(events_backup_<date>) and then removes them from `events`, so the dashboard begins empty.
Nothing is lost; drop old backup tables by hand. Sample-store data is left alone.

    npm run backend:reset                    # the live site in $DATABASE_URL (default densityai)
    npm run backend:reset -- --site sample-store
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.app import db  # noqa: E402


def reset(conn, site_id, stamp):
    """Move the site's events into a backup table. Returns (table name, rows moved)."""
    table = f"events_backup_{stamp}"
    with conn.transaction():
        conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (LIKE events)").format(sql.Identifier(table)))
        moved = conn.execute(
            sql.SQL("INSERT INTO {} SELECT * FROM events WHERE site_id = %s").format(sql.Identifier(table)),
            (site_id,),
        ).rowcount
        conn.execute("DELETE FROM events WHERE site_id = %s", (site_id,))
    return table, moved


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", help="site id (default: the live camera site)")
    parser.add_argument("--database-url", help="default: $DATABASE_URL or " + db.DEFAULT_URL)
    args = parser.parse_args()
    conn = db.connect(args.database_url)
    site_id = args.site or db.live_site_id(conn)
    if not site_id:
        raise SystemExit("No live site in the database yet, so there is nothing to reset.")
    table, moved = reset(conn, site_id, datetime.now().strftime("%Y%m%d_%H%M%S"))
    print(f"Moved {moved:,} events of site {site_id!r} into table {table}. History starts empty now.")


if __name__ == "__main__":
    main()
