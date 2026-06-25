# Quadpod Engineering Guide

This guide is for maintaining, deploying, calibrating, and troubleshooting the APEC Quadpod app without AI assistance.

## Project Layout

- `config.py` holds environment-driven settings: app version, data/export/photo paths, hardware pins, PCA9685/Victor pulse widths, load-cell calibration, pull target, preload, failure detection, hotspot, and email.
- `flask_app/app.py` is the Flask entrypoint. It defines job/test/result/archive routes, JSON hardware APIs, setup check, calibration utility, Wi-Fi helper, USB export copy, and email queue actions.
- `flask_app/engine.py` owns the live control loop. It reads the load cell, drives the actuator, enforces pull-start gates, logs samples, detects stop conditions, and writes test status.
- `flask_app/storage.py` owns SQLite schema and all job/test/sample/event/email persistence. Form data is stored as JSON so new fields can be added without a table migration.
- `flask_app/exporter.py` writes the job composite CSV, per-test trace CSV files, one audit JSON per job, bundle ZIP files, and USB/export job folders.
- `hardware/loadcell.py` reads the HX711 load cell in mock or real GPIO mode and applies reference-unit calibration/filtering.
- `hardware/actuator.py` drives the PCA9685 PWM board and Victor SPX in mock or real hardware mode.
- `scripts/` contains Pi diagnostics, calibration helpers, `switch_network.py`, hotspot setup, Playwright UI/performance checks, and the systemd service.
- `tests/` contains unit tests for storage/export, actuator conversion, HX711 compatibility, control gates, and Flask API behavior when Flask is installed.

## Local Development

From Windows PowerShell:

```powershell
cd C:\Users\ayden\Documents\Codex\2026-05-25\repo-quadpod-project
python -m venv flask_app\.venv
.\flask_app\.venv\Scripts\Activate.ps1
pip install -r flask_app\requirements.txt
$env:QUADPOD_MOCK_HARDWARE="1"
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

- `http://quadpod.local`
- `http://10.42.0.1`
- legacy compatibility: port `5000`

The service binds ports 80 and 5000. The app returns `network_transition.html` before changing interfaces. A background thread launches `scripts/switch_network.py`, which manages one selected hotspot profile, disables duplicate hotspot autoconnect, and restores hotspot mode when a Wi-Fi connection fails.

Run `sudo bash /opt/quadpod/scripts/setup-mdns.sh quadpod` once per Pi image to advertise `quadpod.local`. This does not require changing the administrative hostname.

Do not run synchronous `nmcli` interface changes inside a Flask request. The request will lose its own transport and appear to crash.

The built-in Wi-Fi radio cannot remain an access point while also joining normal Wi-Fi. The phone/computer must follow the Pi onto the target network.

## Email Configuration

Email queueing is shown only when email is fully configured. Example Gmail SMTP environment values:

```bash
export QUADPOD_EMAIL_ENABLED=1
export QUADPOD_EMAIL_TO="aydenreese1430@gmail.com"
export QUADPOD_EMAIL_FROM="sender@gmail.com"
export QUADPOD_SMTP_HOST="smtp.gmail.com"
export QUADPOD_SMTP_PORT=587
export QUADPOD_SMTP_USERNAME="sender@gmail.com"
export QUADPOD_SMTP_PASSWORD="Google app password"
export QUADPOD_SMTP_USE_TLS=1
```

Google requires an app password or another supported SMTP credential. The recipient address alone is not enough to send mail. Keep credentials in the systemd environment, never in Git.

Store deployed credentials in root-owned `/etc/quadpod.env`; `quadpod.service` reads it through `EnvironmentFile`. When email is configured, the app sends one automatic undervoltage/throttling alert per unique fault state per Pi boot. The local Setup warning remains available because email cannot be trusted while the Pi is offline.

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

- `Project_Job#_ALL.csv`
- `audit.json`
- `tests/Project_Job#_Test-#.csv`
- `photos/<uploaded-photo-files>` when optional in-app photos were uploaded

The `Copy Job Folder to USB/Exports` action writes the same layout into a named job folder. If `QUADPOD_USB_EXPORT_ROOT` is set, that folder is used first. Otherwise the app looks for writable mounted media under `/media` or `/mnt`; if none is available it writes to `flask_app/static/exports/usb_copy`.

## Troubleshooting

- Cannot connect: verify the phone followed the Pi onto the selected network, try `http://quadpod.local`, then hotspot fallback `http://10.42.0.1`.
- Network switch fails: inspect `nmcli connection show`, ensure only `quadpod-hotspot` is allowed to autoconnect as a hotspot, and run `python scripts/switch_network.py hotspot` from a local console if recovery is needed.
- Undervoltage/intermittent networking: run `vcgencmd get_throttled` and `journalctl -k -b | grep -i voltage`. Correct the power supply/cable and reboot before further software diagnosis.
- App not opening: run `sudo systemctl status quadpod.service` and `journalctl -u quadpod.service -n 100`.
- Load cell not reading: press Tare in Pre-Test, run `scripts/check_hx711_dout.py`, then `scripts/read_hx711_raw.py`. Check DOUT/SCK pins and 5V/GND.
- Load values wrong: rerun `scripts/calibrate_loadcell.py`, verify `QUADPOD_LOADCELL_REFERENCE_UNIT`, and restart service.
- Actuator not moving: check PCA9685 power/I2C, run `scripts/probe_pwm.py`, verify Victor neutral/calibration and actuator wiring.
- Pull will not start: open `/setup-check`, confirm load cell/actuator OK, confirm calibration dates are recorded, confirm angle is recorded, tare, and preload to 10 lb +/- tolerance.
- Email not sending: download the ZIP manually or connect the Pi to internet and use Archive -> Try Sending Now.

## Performance and UI Verification

Install Playwright in the development virtual environment:

```powershell
.\venv\Scripts\python.exe -m pip install playwright
.\venv\Scripts\python.exe -m playwright install chromium
```

Run the reusable mobile/desktop layout and page-timing check while the mock app is running:

```powershell
.\venv\Scripts\python.exe scripts\playwright_ui_check.py --base-url http://127.0.0.1:5050
```

The report and screenshots are written under `artifacts/ui/`. Network status is lazy-loaded only when its collapsed panel opens; load-cell polling runs only while the calibration panel is open.
