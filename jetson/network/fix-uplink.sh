#!/usr/bin/env bash
# Internet for the Jetson (and the DensityAI Wi-Fi) through a Mac over the USB-C cable.
#
# The Jetson's USB-C port shows up on the Mac as a network called "Linux for Tegra". With macOS
# Internet Sharing on (share from Wi-Fi to Linux for Tegra), the Mac is the gateway 192.168.2.1 on
# that cable. This gives the Jetson the fixed address 192.168.2.200 there and a default route
# through the Mac. Then the Mac opens the dashboard at http://192.168.2.200:8000 and keeps its own
# internet, and the Tapo app on a phone joined to DensityAI can reach the internet to pair.
#
#   sudo jetson/network/fix-uplink.sh             # fix it now, e.g. after the cable blipped
#   sudo jetson/network/fix-uplink.sh --install   # also install the mac-uplink service (jetson-wifi.sh does)
#   sudo jetson/network/fix-uplink.sh --watch     # what the service runs: re-check every 10 s
#   sudo jetson/network/fix-uplink.sh --remove    # remove the service and the route
#
# Without a Mac sharing its internet, it changes nothing: the dashboard and camera don't need it.
# The Mac's Wi-Fi must be a network macOS can share: ncsu or home Wi-Fi, not eduroam.
set -uo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run this with sudo."; exit 1; }
BRIDGE=${USB_BRIDGE:-l4tbr0}   # USB device-mode bridge; the Jetson is 192.168.55.1 on it
ADDR=192.168.2.200
GATEWAY=192.168.2.1
UNIT=/etc/systemd/system/mac-uplink.service
SELF=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")

# Returns 0 when the Jetson has internet through the Mac.
apply() {
  ip link show "$BRIDGE" >/dev/null 2>&1 || return 1
  ip -4 addr show dev "$BRIDGE" | grep -q "inet $ADDR/" || ip addr add "$ADDR/24" dev "$BRIDGE" 2>/dev/null
  if ping -c 1 -W 1 "$GATEWAY" >/dev/null 2>&1; then
    ip route replace default via "$GATEWAY" dev "$BRIDGE" metric 50
    resolvectl dns "$BRIDGE" "$GATEWAY" >/dev/null 2>&1
    resolvectl domain "$BRIDGE" '~.' >/dev/null 2>&1
    return 0
  fi
  # No Mac sharing right now: drop the route so it doesn't hide another uplink.
  ip route del default via "$GATEWAY" dev "$BRIDGE" 2>/dev/null
  return 1
}

case "${1:-}" in
  --watch)
    while true; do apply; sleep 10; done
    ;;
  --remove)
    systemctl disable --now mac-uplink >/dev/null 2>&1
    rm -f "$UNIT"
    systemctl daemon-reload
    ip route del default via "$GATEWAY" dev "$BRIDGE" 2>/dev/null
    ip addr del "$ADDR/24" dev "$BRIDGE" 2>/dev/null
    echo "Removed the mac-uplink service."
    exit 0
    ;;
  --install)
    cat > "$UNIT" <<EOF
[Unit]
Description=DensityAI: internet through a Mac over USB-C (Internet Sharing)
After=network.target

[Service]
ExecStart=$SELF --watch
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now mac-uplink
    ;;
esac

if apply && curl -sI -m 5 https://www.google.com >/dev/null; then
  echo "Jetson internet is back (through the Mac). Mac dashboard: http://$ADDR:8000"
else
  echo "No internet through the USB-C cable. Check that the cable is in and that the Mac has"
  echo "Internet Sharing on: share from Wi-Fi (ncsu or home, not eduroam) to Linux for Tegra."
fi
