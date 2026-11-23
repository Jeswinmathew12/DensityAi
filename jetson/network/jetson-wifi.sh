#!/usr/bin/env bash
# Turns the Jetson's Wi-Fi into its own network, "DensityAI", that the Wi-Fi camera and viewers
# join. Campus Wi-Fi (ncsu, eduroam) blocks devices from talking to each other, so the camera
# can't stream to the Jetson there. On DensityAI nothing is in the way, it works with no internet,
# the Jetson is always 10.42.0.1, and the dashboard is http://10.42.0.1:8000.
#
#   sudo jetson/network/jetson-wifi.sh            # asks you to choose the Wi-Fi password
#   sudo jetson/network/jetson-wifi.sh --remove   # back to a normal Wi-Fi client (e.g. home Wi-Fi)
#
# Optional env: WIFI_NAME (default DensityAI), WIFI_IFACE (default: the first Wi-Fi interface,
# wlP1p1s0 on our Orin Nano). Pass them through sudo: sudo WIFI_NAME=MyNet jetson/network/...
#
# The radio can't be a client and an access point at once, so while DensityAI is on, the Jetson
# has no Wi-Fi internet. It also installs the mac-uplink service (fix-uplink.sh), so a Mac with
# Internet Sharing over the USB-C cable gives the Jetson, and everything on DensityAI, internet.
# Only the Tapo app needs that, to pair the camera. The password is kept by NetworkManager, never
# in this repo.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run this with sudo."; exit 1; }
HERE=$(cd "$(dirname "$0")" && pwd)
SSID=${WIFI_NAME:-DensityAI}
CON=densityai-ap
IFACE=${WIFI_IFACE:-$(nmcli -t -f DEVICE,TYPE device | awk -F: '$2 == "wifi" {print $1; exit}')}
[ -n "$IFACE" ] || { echo "No Wi-Fi interface found (nmcli device)."; exit 1; }

if [ "${1:-}" = "--remove" ]; then
  nmcli connection delete "$CON" >/dev/null 2>&1 || true
  "$HERE/fix-uplink.sh" --remove
  echo "Removed the $SSID Wi-Fi. Join a normal network with: sudo nmcli --ask device wifi connect <name>"
  exit 0
fi

read -r -p "Choose a password for the $SSID Wi-Fi (8+ characters, shown as you type): " PSK
[ "${#PSK}" -ge 8 ] || { echo "The password needs at least 8 characters."; exit 1; }

# 2.4 GHz (band bg), because Tapo cameras can't see 5 GHz networks. "shared" makes
# NetworkManager run DHCP and DNS for the network (10.42.0.x) and share any internet the Jetson
# has. The high autoconnect priority makes it win over saved client networks at every boot.
nmcli connection delete "$CON" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name "$CON" ssid "$SSID" \
  802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
  802-11-wireless.powersave 2 \
  wifi-sec.key-mgmt wpa-psk wifi-sec.proto rsn wifi-sec.pairwise ccmp wifi-sec.group ccmp \
  wifi-sec.psk "$PSK" \
  ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
  connection.autoconnect yes connection.autoconnect-priority 100 >/dev/null
nmcli connection up "$CON"

"$HERE/fix-uplink.sh" --install

echo
echo "Done. Wi-Fi name: $SSID   password: $PSK"
echo "Dashboard for anyone on $SSID: http://10.42.0.1:8000"
