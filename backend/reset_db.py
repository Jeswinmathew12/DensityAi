"""Starts history over: moves the backend's database into a backups/ folder next to it
(backend/backups/ by default), so the next backend start begins empty. Nothing is deleted;
remove old backups by hand.

    npm run backend:reset                     # backend/density.db (or $DENSITY_DB)
    npm run backend:reset -- backend/sim.db   # a different database

Stop the backend that uses the database first.
"""
import argparse
import json
import os
import urllib.request
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


def backend_database(url):
    """Name of the database the backend at `url` is using, or None if nothing answers."""
    try:
        with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
            return json.load(r).get("database")
    except OSError:
        return None


def reset(db, backups, stamp):
    """Move `db` into `backups`. Returns the new path, or None if there was nothing to move."""
    if not db.exists():
        return None
    backups.mkdir(exist_ok=True)
    dest = backups / f"{db.stem}-{stamp}{db.suffix}"
    db.rename(dest)
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db", nargs="?", type=Path,
                        default=Path(os.environ.get("DENSITY_DB") or BACKEND_DIR / "density.db"))
    parser.add_argument("--url", default="http://localhost:8000", help="backend to check is stopped")
    args = parser.parse_args()

    if backend_database(args.url) == args.db.name:
        raise SystemExit(f"The backend at {args.url} is using {args.db.name}. Stop it first, then run this again.")
    dest = reset(args.db, args.db.parent / "backups", datetime.now().strftime("%Y%m%d-%H%M%S"))
    if dest:
        print(f"Moved {args.db} to {dest}. The next backend start begins with empty history.")
    else:
        print(f"{args.db} doesn't exist, so history is already empty.")


if __name__ == "__main__":
    main()
