#!/usr/bin/env bash
# Installs PostgreSQL (Ubuntu / Jetson) and gives your Linux account its own database role, so
# DensityAI connects over the local socket with no password. Safe to run again.
#
#   npm run db:setup                    # PostgreSQL only (enough for everything)
#   npm run db:setup -- --timescale     # also TimescaleDB, the time-series extension
#
# On a Mac: brew install postgresql@16 && brew services start postgresql@16
set -euo pipefail
cd "$(dirname "$0")/.."
log() { echo "[db:setup] $*"; }

if [ "$(uname)" = Darwin ]; then
  command -v psql >/dev/null || {
    log "Install PostgreSQL first: brew install postgresql@16 && brew services start postgresql@16"
    exit 1
  }
else
  if ! command -v psql >/dev/null; then
    log "Installing PostgreSQL..."
    sudo apt-get update
    sudo apt-get install -y postgresql
  fi
  sudo systemctl enable --now postgresql
  # A superuser role named after you: it can create the densityai databases and extensions.
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$USER'" | grep -q 1; then
    sudo -u postgres createuser --superuser "$USER"
    log "Created database role $USER"
  fi
fi

if [ "${1:-}" = "--timescale" ] && [ "$(uname)" != Darwin ]; then
  PGV=$(psql -V | grep -oE '[0-9]+' | head -1)
  if ! dpkg -s "timescaledb-2-postgresql-$PGV" >/dev/null 2>&1; then
    log "Installing TimescaleDB for PostgreSQL $PGV..."
    sudo apt-get install -y gnupg curl lsb-release
    echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -cs) main" |
      sudo tee /etc/apt/sources.list.d/timescaledb.list >/dev/null
    curl -fsSL https://packagecloud.io/timescale/timescaledb/gpgkey |
      sudo gpg --dearmor --yes -o /etc/apt/trusted.gpg.d/timescaledb.gpg
    sudo apt-get update
    sudo apt-get install -y "timescaledb-2-postgresql-$PGV"
    # The Jetson shares its 8 GB with the camera pipeline, so tune for 1 GB, not the whole board.
    sudo timescaledb-tune --quiet --yes --memory=1GB
    sudo systemctl restart postgresql
  fi
fi

createdb densityai 2>/dev/null && log "Created database densityai" || log "Database densityai already exists"

if [ -x backend/.venv/bin/pip ]; then
  backend/.venv/bin/pip install -q -r backend/requirements-dev.txt
else
  log "Next: npm run backend:setup"
fi
log "Done. Check it with: psql densityai -c 'select 1'"
