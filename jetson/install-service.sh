#!/usr/bin/env bash
# Runs jetson/start.sh at boot as a systemd service, and restarts it if it ever exits.
#
#   sudo jetson/install-service.sh            # install, enable at boot, start now
#   sudo jetson/install-service.sh --remove   # stop and uninstall
#
# Logs: journalctl -u densityai -f      Stop for now: sudo systemctl stop densityai
# Optional settings (INGEST_TOKEN=..., CAMERA_DEVICE=..., one per line) go in /etc/densityai.env,
# outside the repo so secrets stay out of git.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run this with sudo."; exit 1; }
RUN_AS=${SUDO_USER:?Run this with sudo from your normal account, not as root.}
REPO=$(cd "$(dirname "$0")/.." && pwd)
UNIT=/etc/systemd/system/densityai.service

if [ "${1:-}" = "--remove" ]; then
  systemctl disable --now densityai 2>/dev/null || true
  rm -f "$UNIT"
  systemctl daemon-reload
  echo "Removed the densityai service."
  exit 0
fi

cat > "$UNIT" <<EOF
[Unit]
Description=DensityAI backend and camera pipeline
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_AS
WorkingDirectory=$REPO
EnvironmentFile=-/etc/densityai.env
ExecStart=$REPO/jetson/start.sh
Restart=always
RestartSec=5
# start.sh forwards SIGTERM so the pipeline and backend shut down cleanly.
KillMode=mixed
TimeoutStopSec=20

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now densityai
echo "Installed. DensityAI now starts at boot. Follow the logs with: journalctl -u densityai -f"
