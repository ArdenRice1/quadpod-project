#!/usr/bin/env bash
set -euo pipefail

MDNS_NAME="${1:-quadpod}"
CONFIG="/etc/avahi/avahi-daemon.conf"

if [ "$EUID" -ne 0 ]; then
  echo "Run with sudo."
  exit 1
fi

if ! command -v avahi-daemon >/dev/null 2>&1; then
  echo "avahi-daemon is not installed."
  exit 1
fi

cp "$CONFIG" "${CONFIG}.quadpod-backup"
if grep -q '^host-name=' "$CONFIG"; then
  sed -i "s/^host-name=.*/host-name=${MDNS_NAME}/" "$CONFIG"
else
  sed -i "/^\[server\]/a host-name=${MDNS_NAME}" "$CONFIG"
fi

systemctl restart avahi-daemon
echo "Quadpod mDNS address configured: http://${MDNS_NAME}.local"
