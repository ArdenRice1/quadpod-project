#!/usr/bin/env bash
set -euo pipefail

SSID="${1:-${QUADPOD_HOTSPOT_SSID:-Quadpod-0001}}"
PASSWORD="${2:-${QUADPOD_HOTSPOT_PASSWORD:-quadpod-field-setup}}"
IFACE="${3:-wlan0}"
IP_CIDR="${4:-10.42.0.1/24}"
PROFILE="quadpod-hotspot"

if [ "$EUID" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if [ "${#PASSWORD}" -lt 8 ]; then
  echo "WPA password must be at least 8 characters."
  exit 1
fi

nmcli connection delete QUADPOD_WAP >/dev/null 2>&1 || true
nmcli connection delete "$PROFILE" >/dev/null 2>&1 || true
nmcli connection add type wifi ifname "$IFACE" con-name "$PROFILE" autoconnect yes ssid "$SSID"
nmcli connection modify "$PROFILE" connection.autoconnect-priority 200
nmcli connection modify "$PROFILE" 802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.powersave 2
nmcli connection modify "$PROFILE" ipv4.method shared ipv4.addresses "$IP_CIDR" ipv6.method disabled
nmcli connection modify "$PROFILE" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$PASSWORD"
iw dev "$IFACE" set power_save off >/dev/null 2>&1 || true
nmcli connection up "$PROFILE"
iw dev "$IFACE" set power_save off >/dev/null 2>&1 || true

echo "Quadpod hotspot configured:"
echo "  SSID: $SSID"
echo "  IP:   $IP_CIDR"
