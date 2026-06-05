# Quadpod Engineering Guide

This guide is for maintaining, deploying, calibrating, and troubleshooting the APEC Quadpod app without AI assistance.

## Project Layout

- `config.py` holds environment-driven settings: app version, data/export/photo paths, hardware pins, PCA9685/Victor pulse widths, load-cell calibration, pull target, preload, failure detection, hotspot, email, and operator PIN.
- `flask_app/app.py` is the Flask entrypoint. It defines job/test/result/export routes, JSON hardware APIs, operator arming, setup check, photo upload, and email queue actions.
- `flask_app/engine.py` owns the live control loop. It reads the load cell, drives the actuator, enforces pull-start gates, logs samples, detects stop conditions, and writes test status.
- `flask_app/storage.py` owns SQLite schema and all job/test/sample/event/email persistence. Form data is stored as JSON so new fields can be added without a table migration.
- `flask_app/exporter.py` writes summary CSV, trace CSV, report HTML, audit JSON, and bundle ZIP files.
- `hardware/loadcell.py` reads the HX711 load cell in mock or real GPIO mode and applies reference-unit calibration/filtering.
- `hardware/actuator.py` drives the PCA9685 PWM board and Victor SPX in mock or real hardware mode.
- `scripts/` contains Pi diagnostics and calibration helpers for HX711, GPIO, PCA9685, Victor SPX, hotspot setup, and systemd service.
- `tests/` contains unit tests for storage/export, actuator conversion, HX711 compatibility, control gates, and Flask API behavior when Flask is installed.

## Local Development

From Windows PowerShell:

```powershell
cd C:\Users\ayden\Documents\Codex\2026-05-25\repo-quadpod-project
python -m venv flask_app\.venv
.\flask_app\.venv\Scripts\Activate.ps1
pip install -r flask_app\requirements.txt
$env:QUADPOD_MOCK_HARDWARE="1"
$env:QUADPOD_OPERATOR_PIN="1234"
python flask_app\app.py
```

Open `http://localhost:5000`.

Run tests:

```powershell
python -m unittest discover -s tests
```

If `git` is not on PATH, use:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' status
```

## Raspberry Pi Deployment

Target: Raspberry Pi OS Lite. Copy the repo to `/opt/quadpod`, then:

```bash
cd /opt/quadpod
python3 -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -r flask_app/requirements.txt
```

Production environment values:

```bash
export QUADPOD_MOCK_HARDWARE=0
export QUADPOD_SECRET_KEY="replace-with-random-long-value"
export QUADPOD_OPERATOR_PIN="replace-with-field-pin"
export QUADPOD_DATABASE=/opt/quadpod/flask_app/data/quadpod.db
export QUADPOD_LOADCELL_REFERENCE_UNIT=10433.64
export QUADPOD_VICTOR_NEUTRAL_US=1650
export QUADPOD_VICTOR_PULL_US=1850
export QUADPOD_VICTOR_JOG_US=1850
```

Install service:

```bash
sudo cp /opt/quadpod/scripts/quadpod.service /etc/systemd/system/quadpod.service
sudo systemctl daemon-reload
sudo systemctl enable --now quadpod.service
sudo systemctl status quadpod.service
```

Logs:

```bash
journalctl -u quadpod.service -f
```

## Hotspot/WAP Setup

Use the provided NetworkManager script:

```bash
sudo bash /opt/quadpod/scripts/setup-hotspot.sh Quadpod-0001 "change-this-password"
```

Field URLs:

- `http://quadpod.local:5000`
- `http://10.42.0.1:5000`

Email will normally queue until the Pi has internet via Ethernet, USB Wi-Fi, phone tethering, or router mode.

## Calibration

Load cell:

```bash
cd /opt/quadpod
. venv/bin/activate
python scripts/diagnose_loadcell.py --samples 20
python scripts/calibrate_loadcell.py --known-lbs 25
```

Update `QUADPOD_LOADCELL_REFERENCE_UNIT` with the reported value and restart the service:

```bash
sudo systemctl restart quadpod.service
```

Victor SPX / actuator:

```bash
python scripts/calibrate_victor_spx.py
python scripts/probe_pwm.py --pulse 1650 --hold 5
python scripts/probe_pwm.py --pulse 1850 --hold 5 --neutral-after
```

Pull rate target is 5 in/min. One inch should take 12 seconds; six inches should take 72 seconds. Move `QUADPOD_VICTOR_PULL_US` closer to neutral if too fast, farther from neutral if too slow. Restart the service after changing pulse values.

Direction:

- Use `/setup-check` and the Pre-Test jog buttons unloaded first.
- If up/down are reversed, set `QUADPOD_ACTUATOR_INVERT=1`.
- If the live pull direction is wrong, set `QUADPOD_PULL_DIRECTION=up` or `down` and verify unloaded.

## Data, Exports, and Backup

Default locations:

- Database: `flask_app/data/quadpod.db`
- Photos: `flask_app/static/photos`
- Exports: `flask_app/static/exports`

Back up a Pi:

```bash
sudo systemctl stop quadpod.service
tar -czf quadpod-backup-$(date +%F).tgz /opt/quadpod/flask_app/data /opt/quadpod/flask_app/static/photos /opt/quadpod/flask_app/static/exports
sudo systemctl start quadpod.service
```

Export bundle contents:

- `summary.csv`
- `report.html`
- `audit.json`
- `traces/test_<id>_trace.csv`
- `photos/<uploaded-photo-files>`

## Troubleshooting

- Cannot connect: verify phone is on Quadpod Wi-Fi, try `http://10.42.0.1:5000`, then run `nmcli connection show` and restart NetworkManager if needed.
- App not opening: run `sudo systemctl status quadpod.service` and `journalctl -u quadpod.service -n 100`.
- Load cell not reading: press Tare in Pre-Test, run `scripts/check_hx711_dout.py`, then `scripts/read_hx711_raw.py`. Check DOUT/SCK pins and 5V/GND.
- Load values wrong: rerun `scripts/calibrate_loadcell.py`, verify `QUADPOD_LOADCELL_REFERENCE_UNIT`, and restart service.
- Actuator not moving: confirm controls are armed, check PCA9685 power/I2C, run `scripts/probe_pwm.py`, verify Victor neutral/calibration and actuator wiring.
- Pull will not start: open `/setup-check`, arm controls, confirm calibration/weather/safety, clear weather blockers or record an authorized weather bypass with a reason, confirm site/photo checklists, tare, and preload to 10 lb +/- tolerance.
- Email not sending: download the ZIP manually or connect the Pi to internet and use Exports -> Try Sending Now.
