#!/usr/bin/env python3
import argparse
import subprocess
import sys
import time


HOTSPOT_PROFILES = ["quadpod-hotspot", "QUADPOD_WAP"]
WIFI_CONNECT_ATTEMPTS = 3


def run(command, check=True):
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        timeout=35,
    )


def connection_names():
    result = run(["nmcli", "-t", "-f", "NAME", "connection", "show"], check=False)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def hotspot_profile():
    names = connection_names()
    for name in HOTSPOT_PROFILES:
        if name in names:
            return name
    raise RuntimeError("No Quadpod hotspot profile exists")


def disable_duplicate_hotspots(selected):
    names = connection_names()
    for name in HOTSPOT_PROFILES:
        if name in names and name != selected:
            run(["nmcli", "connection", "modify", name, "connection.autoconnect", "no"], check=False)
            run(["nmcli", "connection", "down", name], check=False)


def restart_discovery():
    run(["systemctl", "restart", "avahi-daemon"], check=False)


def disable_wifi_powersave(profile):
    run(["nmcli", "connection", "modify", profile, "802-11-wireless.powersave", "2"], check=False)


def set_radio_powersave_off():
    run(["iw", "dev", "wlan0", "set", "power_save", "off"], check=False)


def wifi_connect_command(ssid, password):
    command = ["nmcli", "device", "wifi", "connect", ssid, "ifname", "wlan0", "name", ssid]
    if password:
        command.extend(["password", password])
    return command


def bring_up_wifi_profile(ssid):
    last_error = None
    for attempt in range(1, WIFI_CONNECT_ATTEMPTS + 1):
        try:
            run(["nmcli", "connection", "up", ssid, "ifname", "wlan0"])
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            last_error = exc
            run(["nmcli", "radio", "wifi", "on"], check=False)
            set_radio_powersave_off()
            time.sleep(min(1.5 * attempt, 4.0))
    if last_error:
        raise last_error


def malformed_wifi_profile(exc):
    text = f"{getattr(exc, 'stdout', '')}\n{getattr(exc, 'stderr', '')}"
    return "802-11-wireless-security.key-mgmt" in text or "wifi-sec.key-mgmt" in text


def rebuild_wifi_profile(ssid, password):
    run(["nmcli", "connection", "delete", ssid], check=False)
    run(wifi_connect_command(ssid, password))
    disable_wifi_powersave(ssid)


def switch_to_wifi(ssid, password):
    hotspot = hotspot_profile()
    set_radio_powersave_off()
    disable_wifi_powersave(hotspot)
    disable_duplicate_hotspots(hotspot)
    run(["nmcli", "connection", "modify", hotspot, "connection.autoconnect", "no"], check=False)
    run(["nmcli", "connection", "down", hotspot], check=False)
    time.sleep(1.0)

    try:
        if ssid in connection_names():
            try:
                if password:
                    run(["nmcli", "connection", "modify", ssid, "wifi-sec.key-mgmt", "wpa-psk"])
                    run(["nmcli", "connection", "modify", ssid, "wifi-sec.psk", password])
                disable_wifi_powersave(ssid)
                bring_up_wifi_profile(ssid)
            except subprocess.CalledProcessError as exc:
                if not malformed_wifi_profile(exc):
                    raise
                rebuild_wifi_profile(ssid, password)
        else:
            run(wifi_connect_command(ssid, password))
            disable_wifi_powersave(ssid)
        run(["nmcli", "connection", "modify", ssid, "connection.autoconnect", "yes"])
        run(["nmcli", "connection", "modify", ssid, "connection.autoconnect-priority", "100"])
        run(["nmcli", "connection", "modify", ssid, "connection.permissions", ""], check=False)
        set_radio_powersave_off()
        restart_discovery()
        print(f"Connected to Wi-Fi profile: {ssid}")
        return 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        run(["nmcli", "connection", "modify", hotspot, "connection.autoconnect", "yes"], check=False)
        run(["nmcli", "connection", "up", hotspot], check=False)
        print(f"Wi-Fi connection failed; restored hotspot: {exc}", file=sys.stderr)
        return 1


def switch_to_hotspot():
    hotspot = hotspot_profile()
    set_radio_powersave_off()
    disable_wifi_powersave(hotspot)
    disable_duplicate_hotspots(hotspot)
    run(["nmcli", "connection", "modify", hotspot, "connection.autoconnect", "yes"])
    run(["nmcli", "connection", "modify", hotspot, "connection.autoconnect-priority", "200"])
    try:
        run(["nmcli", "connection", "up", hotspot])
        set_radio_powersave_off()
        restart_discovery()
        print(f"Started hotspot profile: {hotspot}")
        return 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"Hotspot start failed: {exc}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(description="Switch Quadpod between Wi-Fi and hotspot modes.")
    parser.add_argument("--delay", type=float, default=2.0)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    wifi = subparsers.add_parser("wifi")
    wifi.add_argument("--ssid", required=True)
    wifi.add_argument("--password", default="")
    subparsers.add_parser("hotspot")
    args = parser.parse_args()

    time.sleep(max(0.0, args.delay))
    if args.mode == "wifi":
        return switch_to_wifi(args.ssid, args.password)
    return switch_to_hotspot()


if __name__ == "__main__":
    raise SystemExit(main())
