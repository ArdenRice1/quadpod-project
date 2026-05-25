#!/usr/bin/env bash
set -euo pipefail

SSID="${1:-Quadpod-0001}"
PASSWORD="${2:-quadpod-field-setup}"
IFACE="${3:-wlan0}"
IP_CIDR="${4:-10.42.0.1/24}"

if [ "$EUID" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if [ "${#PASSWORD}" -lt 8 ]; then
  echo "WPA password must be at least 8 characters."
  exit 1
fi

nmcli connection delete quadpod-hotspot >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name quadpod-hotspot autoconnect yes ssid "$SSID"
nmcli connection modify quadpod-hotspot 802-11-wireless.mode ap 802-11-wireless.band bg
nmcli connection modify quadpod-hotspot ipv4.method shared ipv4.addresses "$IP_CIDR" ipv6.method disabled
nmcli connection modify quadpod-hotspot wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD"
nmcli connection up quadpod-hotspot

echo "Quadpod hotspot configured:"
echo "  SSID: $SSID"
echo "  IP:   $IP_CIDR"
