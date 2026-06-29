#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi

systemctl enable --now tailscaled

# This prints a login URL unless an auth key is supplied through TS_AUTHKEY.
if [[ -n "${TS_AUTHKEY:-}" ]]; then
  tailscale up --ssh --hostname quadpod-3 --authkey "${TS_AUTHKEY}"
else
  tailscale up --ssh --hostname quadpod-3
fi

tailscale status
