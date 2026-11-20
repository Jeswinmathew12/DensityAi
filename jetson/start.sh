#!/usr/bin/env bash
# One command for demo day. Builds the dashboard if the code changed, starts the collector
# (port 8001, takes the camera's counts and writes them to PostgreSQL) and the web service
# (port 8000, reads PostgreSQL and serves the dashboard and REST API to other devices), prints
# the addresses, then runs the camera pipeline and restarts it whenever it stops, e.g. after the
# camera is unplugged and plugged back in. Ctrl+C stops all.
#
#   camera -> pipeline -> collector -> PostgreSQL -> web service -> dashboard
#
#   npm run serve                   # from the repo root
#   jetson/start.sh --tracker       # extra flags go to occupancy_pipeline.py
#
# Env (all optional): CAMERA_URI (a Wi-Fi camera's rtsp:// address; without it the USB camera
# is used), CAMERA_DEVICE, DENSITY_PORT (default 8000), ADMIN_PASSWORD (turns on the Admin page's
# live camera view; frames stay in RAM on the Jetson), plus INGEST_TOKEN, DATABASE_URL (default
# postgresql:///densityai) and DENSITY_TZ, which the backend and pipeline read themselves. REACT_APP_API_URL is
# ignored: the built dashboard always talks to the address it was opened at.
# Put them in /etc/densityai.env (one NAME=value per line, outside git because the camera
# password is in CAMERA_URI). The boot service reads that file, and so does this script.
# jetson/install-service.sh runs this at boot.
set -u
cd "$(dirname "$0")/.."

# Settings already in the environment win, e.g. `CAMERA_URI= npm run serve` for the USB camera.
# Read as plain NAME=value lines, not run as shell code, so passwords need no quoting.
if [ -r /etc/densityai.env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    name=${BASH_REMATCH[1]}
    [ -n "${!name+set}" ] || export "$name=${BASH_REMATCH[2]}"
  done < /etc/densityai.env
fi

PORT=${DENSITY_PORT:-8000}
COLLECTOR_PORT=${DENSITY_COLLECTOR_PORT:-8001}
export DENSITY_API_URL="http://localhost:$PORT"
export DENSITY_COLLECTOR_URL="http://localhost:$COLLECTOR_PORT"
log() { echo "[start] $*"; }

# The /dev/v4l/by-id name stays the same when the camera is replugged; /dev/videoN may not.
camera() {
  if [ -n "${CAMERA_DEVICE:-}" ]; then echo "$CAMERA_DEVICE"; return; fi
  ls /dev/v4l/by-id/*-video-index0 2>/dev/null | head -1
}

# No window without a desktop session (SSH, or the boot service).
PIPELINE_FLAGS=()
[ -n "${DISPLAY:-}" ] || PIPELINE_FLAGS+=(--no-display)
# Admin preview: the pipeline keeps its newest annotated frame in RAM, where the backend reads it.
if [ -n "${ADMIN_PASSWORD:-}" ]; then
  export DENSITY_PREVIEW_DIR=${DENSITY_PREVIEW_DIR:-/dev/shm/densityai}
  PIPELINE_FLAGS+=(--preview-dir "$DENSITY_PREVIEW_DIR")
fi

if curl -s -m 2 "$DENSITY_API_URL/api/health" >/dev/null ||
  curl -s -m 2 "$DENSITY_COLLECTOR_URL/api/health" >/dev/null; then
  log "Something is already running on port $PORT or $COLLECTOR_PORT. Stop it first (if it's the boot service:"
  log "sudo systemctl stop densityai)."
  exit 1
fi

# No RTC battery: after a power loss the clock reads 1970 until it syncs (docs/jetson-setup.md,
# known issue 4). Counts stamped 1970 would never show up in the history, so wait for a real date.
if [ "$(date +%Y)" -lt 2025 ]; then
  log "Waiting for the clock to sync (it says $(date +%F))..."
  until [ "$(date +%Y)" -ge 2025 ]; do sleep 5; done
fi

# The dashboard must work on any network (home Wi-Fi, campus, hotspot, USB, Tailscale), so the
# build never gets a fixed backend address: with REACT_APP_API_URL empty, the page talks to
# whatever address it was opened at. An address from .env once got baked in and broke on campus.
ENV_FILES=()
for f in .env*; do [ -f "$f" ] && ENV_FILES+=("$f"); done
for f in "${ENV_FILES[@]}"; do
  grep -qE '^[[:space:]]*(export[[:space:]]+)?REACT_APP_API_URL=' "$f" &&
    log "Warning: $f sets REACT_APP_API_URL. npm run serve ignores it (it's only for the dev server)."
done
[ -n "${REACT_APP_API_URL:-}" ] &&
  log "Warning: REACT_APP_API_URL is set in the environment. npm run serve ignores it."

# Rebuild when the frontend, a .env file or this script changed since the last live build. The
# marker file also catches a plain `npm run build`, which would serve mock data: that build wipes
# build/ and the marker.
MARKER=build/.live-build
if [ ! -f "$MARKER" ] ||
  [ -n "$(find src public package.json jetson/start.sh "${ENV_FILES[@]}" -newer "$MARKER" -print -quit)" ]; then
  log "Building the dashboard (npm run build:live)..."
  REACT_APP_API_URL= npm run build:live || { log "Dashboard build failed"; exit 1; }
  touch "$MARKER"
fi

# PostgreSQL runs as its own system service (npm run db:setup installs it). After a reboot it
# may still be starting, so give it a moment.
for i in $(seq 30); do
  pg_isready -q 2>/dev/null && break
  [ "$i" = 1 ] && log "Waiting for PostgreSQL..."
  [ "$i" = 30 ] && { log "PostgreSQL is not running. Install it once with: npm run db:setup"; exit 1; }
  sleep 1
done

# wait_up NAME PID URL: wait until a server answers /api/health, or give up if it exits.
wait_up() {
  for _ in $(seq 30); do
    curl -s -m 1 "$3/api/health" >/dev/null && return 0
    kill -0 "$2" 2>/dev/null || { log "$1 failed to start"; return 1; }
    sleep 1
  done
  log "$1 did not answer within 30 s"
  return 1
}

# The collector starts first: it creates the tables and writes the zones from zones.json.
# It listens on all addresses: in a store, cameras on other Jetsons would post to it.
backend/.venv/bin/uvicorn backend.app.collector:create_collector --factory --host 0.0.0.0 \
  --port "$COLLECTOR_PORT" > >(sed -u 's/^/[collector] /') 2>&1 &
COLLECTOR=$!
wait_up Collector "$COLLECTOR" "$DENSITY_COLLECTOR_URL" || { kill "$COLLECTOR" 2>/dev/null; exit 1; }
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port "$PORT" \
  > >(sed -u 's/^/[web] /') 2>&1 &
BACKEND=$!
wait_up "Web service" "$BACKEND" "$DENSITY_API_URL" || { kill "$COLLECTOR" "$BACKEND" 2>/dev/null; exit 1; }

# Every address the dashboard can be opened at. Which one works depends on the network the viewer
# shares with the Jetson. Always http: the backend doesn't serve https.
log "Dashboard is up. Open whichever address the viewer's device can reach:"
log "  http://localhost:$PORT  (on this device)"
for ip in $(hostname -I); do
  iface=$(ip -o addr show 2>/dev/null | awk -v a="$ip" '{split($4, p, "/")} p[1] == a {print $2; exit}')
  case $ip in *:*) url="http://[$ip]:$PORT" ;; *) url="http://$ip:$PORT" ;; esac
  log "  $url${iface:+  ($iface)}"
done
log "  http://$(hostname).local:$PORT"
if command -v tailscale >/dev/null; then
  ts=$(tailscale status --json 2>/dev/null | python3 -c '
import json, sys
s = json.load(sys.stdin)
if s.get("BackendState") == "Running":
    me = s.get("Self") or {}
    print(" ".join([me.get("DNSName", "").rstrip(".")] + me.get("TailscaleIPs", [])[:1]))
' 2>/dev/null)
  for t in $ts; do log "  http://$t:$PORT  (Tailscale)"; done
fi

STOPPING=
FAILED=0
PIPELINE=
stop() {
  STOPPING=1
  [ -n "$PIPELINE" ] && kill -TERM "$PIPELINE" 2>/dev/null
}
trap 'log "Stopping..."; stop' INT TERM
trap 'log "Collector or web service exited, stopping"; FAILED=1; stop' USR1
# If either server dies, stop everything so systemd (or you) can start fresh.
(while kill -0 "$BACKEND" 2>/dev/null && kill -0 "$COLLECTOR" 2>/dev/null; do sleep 2; done
 kill -USR1 $$ 2>/dev/null) &
WATCHER=$!

if [ -n "${CAMERA_URI:-}" ]; then
  log "Using the Wi-Fi camera at ${CAMERA_URI##*@}"
fi

waiting=
while [ -z "$STOPPING" ]; do
  if [ -n "${CAMERA_URI:-}" ]; then
    SOURCE=(--uri "$CAMERA_URI")
  else
    dev=$(camera)
    if [ -z "$dev" ] || [ ! -e "$dev" ]; then
      [ -n "$waiting" ] || log "Waiting for a USB camera..."
      waiting=1
      sleep 2
      continue
    fi
    waiting=
    SOURCE=(--device "$dev")
  fi
  # System python3: that's where pyds and gi are installed, not backend/.venv.
  python3 -u jetson/occupancy_pipeline.py "${SOURCE[@]}" "${PIPELINE_FLAGS[@]}" "$@" \
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
kill -TERM "$BACKEND" "$COLLECTOR" 2>/dev/null
wait "$BACKEND" "$COLLECTOR" 2>/dev/null
exit "$FAILED"
