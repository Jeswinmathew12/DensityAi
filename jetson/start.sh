#!/usr/bin/env bash
# One command for demo day. Builds the dashboard if the code changed, starts the backend on
# port 8000 (reachable from other devices), then runs the camera pipeline and restarts it
# whenever it stops, e.g. after the camera is unplugged and plugged back in. Ctrl+C stops all.
#
#   npm run serve                   # from the repo root
#   jetson/start.sh --tracker       # extra flags go to occupancy_pipeline.py
#
# Env (all optional): CAMERA_DEVICE, DENSITY_PORT (default 8000), plus INGEST_TOKEN,
# DENSITY_DB and DENSITY_TZ, which the backend and pipeline read themselves.
# jetson/install-service.sh runs this at boot.
set -u
cd "$(dirname "$0")/.."

PORT=${DENSITY_PORT:-8000}
export DENSITY_API_URL="http://localhost:$PORT"
log() { echo "[start] $*"; }

# The /dev/v4l/by-id name stays the same when the camera is replugged; /dev/videoN may not.
camera() {
  if [ -n "${CAMERA_DEVICE:-}" ]; then echo "$CAMERA_DEVICE"; return; fi
  ls /dev/v4l/by-id/*-video-index0 2>/dev/null | head -1
}

# No window without a desktop session (SSH, or the boot service).
PIPELINE_FLAGS=()
[ -n "${DISPLAY:-}" ] || PIPELINE_FLAGS+=(--no-display)

if curl -s -m 2 "$DENSITY_API_URL/api/health" >/dev/null; then
  log "Something is already running on port $PORT. Stop it first (if it's the boot service:"
  log "sudo systemctl stop densityai)."
  exit 1
fi

# No RTC battery: after a power loss the clock reads 1970 until it syncs (docs/jetson-setup.md,
# known issue 4). Counts stamped 1970 would never show up in the history, so wait for a real date.
if [ "$(date +%Y)" -lt 2025 ]; then
  log "Waiting for the clock to sync (it says $(date +%F))..."
  until [ "$(date +%Y)" -ge 2025 ]; do sleep 5; done
fi

# Rebuild when the frontend changed since the last live build. The marker file also catches a
# plain `npm run build`, which would serve mock data: that build wipes build/ and the marker.
MARKER=build/.live-build
if [ ! -f "$MARKER" ] || [ -n "$(find src public package.json -newer "$MARKER" -print -quit)" ]; then
  log "Building the dashboard (npm run build:live)..."
  npm run build:live || { log "Dashboard build failed"; exit 1; }
  touch "$MARKER"
fi

backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port "$PORT" \
  > >(sed -u 's/^/[backend] /') 2>&1 &
BACKEND=$!
for _ in $(seq 30); do
  curl -s -m 1 "$DENSITY_API_URL/api/health" >/dev/null && break
  kill -0 "$BACKEND" 2>/dev/null || { log "Backend failed to start"; exit 1; }
  sleep 1
done
IP=$(hostname -I | awk '{print $1}')
log "Dashboard: http://${IP:-localhost}:$PORT"

STOPPING=
FAILED=0
PIPELINE=
stop() {
  STOPPING=1
  [ -n "$PIPELINE" ] && kill -TERM "$PIPELINE" 2>/dev/null
}
trap 'log "Stopping..."; stop' INT TERM
trap 'log "Backend exited, stopping"; FAILED=1; stop' USR1
# If the backend dies, stop everything so systemd (or you) can start fresh.
(while kill -0 "$BACKEND" 2>/dev/null; do sleep 2; done; kill -USR1 $$ 2>/dev/null) &
WATCHER=$!

waiting=
while [ -z "$STOPPING" ]; do
  dev=$(camera)
  if [ -z "$dev" ] || [ ! -e "$dev" ]; then
    [ -n "$waiting" ] || log "Waiting for a USB camera..."
    waiting=1
    sleep 2
    continue
  fi
  waiting=
  # System python3: that's where pyds and gi are installed, not backend/.venv.
  python3 -u jetson/occupancy_pipeline.py --device "$dev" "${PIPELINE_FLAGS[@]}" "$@" \
    > >(sed -u 's/^/[pipeline] /') 2>&1 &
  PIPELINE=$!
  wait "$PIPELINE"
  # A signal interrupts `wait` before the pipeline has finished shutting down; wait again.
  wait "$PIPELINE" 2>/dev/null
  PIPELINE=
  [ -n "$STOPPING" ] && break
  log "Pipeline stopped. Restarting in 3 s..."
  sleep 3
done

kill "$WATCHER" 2>/dev/null
kill -TERM "$BACKEND" 2>/dev/null
wait "$BACKEND" 2>/dev/null
exit "$FAILED"
