#!/usr/bin/env bash
# Points DensityAI at a camera, restarts it, and keeps it starting at boot.
#
#   sudo jetson/network/set-camera.sh --find        # list devices on DensityAI that stream video
#   sudo jetson/network/set-camera.sh 10.42.0.108   # use the Wi-Fi (Tapo) camera at that address
#   sudo jetson/network/set-camera.sh usb           # back to the USB webcam
#
# Writes CAMERA_URI=rtsp://USER:PASS@IP:554/stream1 into /etc/densityai.env (outside git, because
# it holds the camera password). It keeps the camera account from the CAMERA_URI already there,
# or asks for it once: that's the Camera Account set in the Tapo app, not your Tapo login.
# When the camera is on the DensityAI Wi-Fi, it also reserves that address for the camera, so
# it gets the same one after every reboot.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run this with sudo."; exit 1; }
ENV=/etc/densityai.env
RESERVE=/etc/NetworkManager/dnsmasq-shared.d/densityai-camera.conf
TARGET=${1:-}

rtsp_open() { timeout 2 bash -c "exec 3<>/dev/tcp/$1/554" 2>/dev/null; }

if [ "$TARGET" = "--find" ]; then
  # DensityAI hands out 10.42.0.x. Ping them all once so the neighbour table is complete.
  for i in $(seq 2 254); do ping -c 1 -W 1 "10.42.0.$i" >/dev/null 2>&1 & done
  wait
  found=
  while read -r ip _ _ _ mac _; do
    [[ $ip == 10.42.0.* ]] || continue
    if rtsp_open "$ip"; then echo "$ip  $mac  <- streams video (RTSP), likely the camera"; found=1
    else echo "$ip  $mac"; fi
  done < <(ip neigh show | grep lladdr)
  [ -n "$found" ] || echo "No camera found. Is it powered and joined to DensityAI in the Tapo app?"
  exit 0
fi

[ -n "$TARGET" ] || { sed -n '2,12p' "$0"; exit 1; }

# Create the settings file readable by the service and by `npm run serve`, not by everyone.
if [ ! -e "$ENV" ]; then
  install -m 640 -o root -g "$(id -gn "${SUDO_USER:-root}")" /dev/null "$ENV"
fi
current=$(grep -E '^CAMERA_URI=' "$ENV" | tail -1 | cut -d= -f2- || true)

if [ "$TARGET" = "usb" ]; then
  line=
else
  [[ $TARGET =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Not an IP address: $TARGET"; exit 1; }
  rtsp_open "$TARGET" || echo "Warning: nothing answers on $TARGET port 554 yet. Saving it anyway."
  creds=
  if [[ $current == rtsp://*@* ]]; then
    creds=${current#rtsp://}
    creds=${creds%@*}
  fi
  if [ -z "$creds" ]; then
    echo "Camera Account from the Tapo app (letters and numbers only; the username is case-sensitive)."
    read -r -p "Camera username: " user
    read -r -s -p "Camera password: " pass
    echo
    creds="$user:$pass"
  fi
  line="CAMERA_URI=rtsp://$creds@$TARGET:554/stream1"

  # Reserve the address on DensityAI (NetworkManager's DHCP reads this at its next start).
  mac=$(ip neigh show "$TARGET" 2>/dev/null | awk '/lladdr/ {print $5; exit}' || true)
  if [[ $TARGET == 10.42.0.* ]] && [ -n "$mac" ]; then
    mkdir -p "$(dirname "$RESERVE")"
    echo "dhcp-host=$mac,$TARGET" > "$RESERVE"
  fi
fi

# Rewrite in place so the file keeps its owner and permissions.
others=$(grep -vE '^CAMERA_URI=' "$ENV" || true)
{ [ -z "$others" ] || printf '%s\n' "$others"; [ -z "$line" ] || printf '%s\n' "$line"; } > "$ENV"

if ! systemctl cat densityai >/dev/null 2>&1; then
  echo "Saved. The densityai service isn't installed yet: run sudo jetson/install-service.sh"
  exit 0
fi
systemctl enable densityai >/dev/null 2>&1
systemctl restart densityai
sleep 2
systemctl is-active densityai || true
echo "DensityAI restarted using: ${TARGET}"
