# Quadpod Demo Readiness Checklist

Use this the day before and the morning of a customer/APEC walkthrough.

## Night Before

1. Charge the phone/tablet and any camera/GoPro batteries.
2. Confirm the Pi boots and `quadpod.service` is active:

```bash
ssh apec@quadpod-3
cd /opt/quadpod
sudo systemctl status quadpod.service
```

3. Confirm the app responds:

```bash
curl -I http://127.0.0.1:5000/setup-check
```

4. Confirm code and tests:

```bash
cd /opt/quadpod
git status --short --branch
./venv/bin/python -m unittest discover -s tests
```

5. Open the app from a phone on Quadpod Wi-Fi:
   - `http://quadpod.local:5000`
   - fallback: `http://10.42.0.1:5000`

## What To Show

1. `Setup` page:
   - hardware mode
   - load-cell status
   - actuator status
   - database/export/photo paths
   - operator arming

2. `Job` page:
   - project/client/equipment fields
   - calibration dates
   - weather and safety checks
   - environmental blockers and documented bypass/deviation

3. `Test` page:
   - tare
   - jog controls
   - preload target: `10 lb +/- tolerance`
   - site suitability checklist
   - shingle observations and photo reference

4. `Live Pull` page:
   - armed controls
   - live force, peak, elapsed time, samples
   - start/stop behavior
   - server-side gate errors if prerequisites are missing

5. `Result` page:
   - failure type
   - operator notes
   - deviation record
   - final reading photo confirmation
   - repair/sample/maintenance closeout

6. `Exports` page:
   - summary CSV
   - trace CSV
   - report HTML
   - audit JSON
   - uploaded photos inside bundle ZIP

## Safe Demo Flow

For a no-risk software walkthrough, keep the machine unloaded and use mock hardware on a laptop. For a Pi/hardware walkthrough, do not start a pull unless the rig is physically safe, unloaded checks have passed, and everyone is standing clear.

Suggested talk track:

1. The operator powers on the Pi and opens one URL.
2. The app prevents movement until controls are armed.
3. The app prevents a pull until calibration, safety, weather, site, photo, and preload gates pass.
4. Environmental blockers follow the APEC procedure by stopping normal testing, but can be documented as an authorized deviation if engineering approves.
5. Exports carry the field record: form data, trace data, machine settings, report, audit payload, and photos.

## Last-Minute Recovery

- App will not load: `sudo systemctl restart quadpod.service`
- Phone cannot connect: use fallback `http://10.42.0.1:5000`
- Load cell reads wrong: press `Tare`; if still wrong, do not run a real pull.
- Actuator does not move: verify controls are armed, power is connected, and use `scripts/probe_pwm.py` only if qualified.
- Pull will not start: read the red gate message, then check preload, calibration dates, safety/weather, site checklist, photo checklist, and operator arming.

