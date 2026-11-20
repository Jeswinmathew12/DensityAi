#!/usr/bin/env bash
# Development: runs the collector (port 8001) and the web service (port 8000) together, both
# reloading when backend code changes. Ctrl+C stops both.
#   npm run backend        # database densityai (real history)
#   npm run backend:sim    # database densityai_sim (for npm run simulate)
set -u
cd "$(dirname "$0")/.."
UVICORN=backend/.venv/bin/uvicorn
[ -x "$UVICORN" ] || { echo "Run npm run backend:setup first."; exit 1; }
echo "[dev] database: ${DATABASE_URL:-postgresql:///densityai}"

$UVICORN backend.app.collector:create_collector --factory --reload --reload-dir backend --port 8001 \
  > >(sed -u 's/^/[collector] /') 2>&1 &
COLLECTOR=$!
# The collector creates the tables and writes zones.json first; then start the web service.
for _ in $(seq 20); do
  curl -s -m 1 http://localhost:8001/api/health >/dev/null && break
  kill -0 $COLLECTOR 2>/dev/null || { echo "[dev] Collector failed to start (is PostgreSQL running? npm run db:setup)"; exit 1; }
  sleep 1
done
$UVICORN backend.app.main:create_app --factory --reload --reload-dir backend --port 8000 \
  > >(sed -u 's/^/[web] /') 2>&1 &
WEB=$!
echo "[dev] Web service and dashboard API: http://localhost:8000 (API docs at /docs). Collector: http://localhost:8001"

trap 'kill $COLLECTOR $WEB 2>/dev/null' INT TERM
wait -n $COLLECTOR $WEB
kill $COLLECTOR $WEB 2>/dev/null
wait
