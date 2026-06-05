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

The current calibrated Quadpod field values are:

```bash
export QUADPOD_MOCK_HARDWARE=0
export QUADPOD_SECRET_KEY="replace-with-random-text"
export QUADPOD_OPERATOR_PIN="replace-with-field-pin"
export QUADPOD_LOADCELL_REFERENCE_UNIT=10433.64
export QUADPOD_VICTOR_NEUTRAL_US=1650
export QUADPOD_VICTOR_PULL_US=1850
export QUADPOD_PULL_DIRECTION=up
export QUADPOD_EMAIL_ENABLED=0
```

Keep `QUADPOD_MOCK_HARDWARE=1` while developing away from the Pi hardware. Re-run `scripts/calibrate_loadcell.py` if the load cell, HX711, wiring, or mechanical load path changes.

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
2. Verify Victor SPX neutral pulse stops movement. Current neutral is `1650 us`.
3. Verify jog direction; set `QUADPOD_ACTUATOR_INVERT=1` if up/down are reversed.
4. Tare the load cell with the rig hanging freely.
5. Apply a known load and update `QUADPOD_LOADCELL_REFERENCE_UNIT`. Current reference unit is `10433.64`.
6. Measure actuator travel over time under realistic load and adjust `QUADPOD_VICTOR_PULL_US` until the pull rate is 5 in/min.
7. Run at least three known-load repeatability checks and keep the results with the equipment calibration records.

## Pull Speed Check

Use measured travel, not PWM alone, to verify pull speed:

```text
speed_ipm = travel_inches / elapsed_seconds * 60
elapsed_seconds = travel_inches / target_ipm * 60
```

For the 5 in/min target, 1 inch should take 12 seconds and a 6 inch stroke should take 72 seconds. If the actuator is too fast, move `QUADPOD_VICTOR_PULL_US` closer to neutral. If it is too slow, move it farther from neutral.
