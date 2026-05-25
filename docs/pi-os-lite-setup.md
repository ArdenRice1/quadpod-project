# Raspberry Pi OS Lite Setup

Production target: Raspberry Pi OS Lite on the Raspberry Pi 3B+. The phone is the operator screen, so no desktop environment is required.

## Install

1. Flash Raspberry Pi OS Lite.
2. Enable SSH.
3. Copy this project to `/opt/quadpod`.
4. Create a virtual environment and install requirements:

```bash
cd /opt/quadpod/flask_app
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Hardware Settings

Set production environment values before starting the service:

```bash
export QUADPOD_MOCK_HARDWARE=0
export QUADPOD_SECRET_KEY="replace-with-random-text"
export QUADPOD_LOADCELL_REFERENCE_UNIT="replace-after-calibration"
export QUADPOD_VICTOR_PULL_US=1600
export QUADPOD_EMAIL_ENABLED=0
```

Keep `QUADPOD_MOCK_HARDWARE=1` while developing away from the Pi hardware.

## Pi WPA Hotspot

The v1 field default is a Pi-hosted WPA2 hotspot. Run the setup script on the Pi:

```bash
sudo bash /opt/quadpod/scripts/setup-hotspot.sh Quadpod-0001 "change-this-password"
```

Operators connect their phone to the `Quadpod-0001` Wi-Fi network, then open:

```text
http://quadpod.local:5000
```

Fallback address:

```text
http://10.42.0.1:5000
```

The built-in Wi-Fi radio is being used as the local access point, so automatic email normally waits until the Pi later gets internet through Ethernet, USB Wi-Fi, phone tethering, or router mode.

## Service

Copy the service file and enable it:

```bash
sudo cp /opt/quadpod/scripts/quadpod.service /etc/systemd/system/quadpod.service
sudo systemctl daemon-reload
sudo systemctl enable --now quadpod.service
```

Logs:

```bash
journalctl -u quadpod.service -f
```

## Calibration Workflow

1. Confirm actuator wiring with the machine unloaded.
2. Verify Victor SPX neutral pulse stops movement.
3. Verify jog direction; set `QUADPOD_ACTUATOR_INVERT=1` if up/down are reversed.
4. Tare the load cell with the rig hanging freely.
5. Apply a known load and update `QUADPOD_LOADCELL_REFERENCE_UNIT`.
6. Measure actuator travel over time under realistic load and adjust `QUADPOD_VICTOR_PULL_US` until the pull rate is 5 in/min.
7. Run at least three known-load repeatability checks and keep the results with the equipment calibration records.
