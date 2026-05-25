# APEC Quadpod

Field ASTM-aligned shingle uplift resistance app for the APEC Quadpod.

The Raspberry Pi hosts a phone-first PWA, stores all test data locally, drives the load-cell/actuator hardware, and exports job bundles for download or queued email.

## Run In Mock Mode

```bash
cd flask_app
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export QUADPOD_MOCK_HARDWARE=1
python app.py
```

Open:

```text
http://localhost:5000
```

## Raspberry Pi OS Lite

Production setup notes are in `docs/pi-os-lite-setup.md`.

The default field network mode is a Pi-hosted WPA2 hotspot. Operators connect their phone to the Quadpod Wi-Fi network and open:

```text
http://quadpod.local:5000
```

Fallback:

```text
http://10.42.0.1:5000
```

## Important Field Notes

- v1 is field ASTM-aligned, not a formal strict ASTM apparatus certification.
- Every APEC form point is included in each test export row.
- Email is queued locally and retries when internet is available.
- The PA-17 actuator has no position feedback, so 5 in/min is calibrated open-loop by setting the Victor SPX pull pulse.
