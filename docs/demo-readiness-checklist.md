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
   - `http://quadpod.local`
   - fallback: `http://10.42.0.1`

## What To Show

1. `Setup` page:
   - load-cell status
   - actuator status
   - database/export paths
   - Wi-Fi/internet helper
   - load-cell calibration helper
   - collapsed network/calibration panels
   - Pi power warning status

2. `Job` page:
   - project/client/equipment fields
   - calibration dates
   - weather notes

3. `Test` page:
   - tare
   - jog controls
   - auto preload and jog speed controls
   - preload band: `10-15 lb`
   - shingle type

4. `Live Pull` page:
   - live force, peak, elapsed time, samples
   - start/stop behavior
   - server-side gate errors if prerequisites are missing

5. `Result` page:
   - failure type
   - operator notes
   - deviation record

6. `Archive` page:
   - job composite CSV
   - per-test CSV files and force-time graphs
   - audit JSON
   - USB/export job folder

## Safe Demo Flow

For a no-risk software walkthrough, keep the machine unloaded and use mock hardware on a laptop. For a Pi/hardware walkthrough, do not start a pull unless the rig is physically safe, unloaded checks have passed, and everyone is standing clear.

Suggested talk track:

1. The operator powers on the Pi and opens one URL.
2. The app keeps normal commands behind same-session browser validation.
3. The app prevents a pull until calibration dates are recorded, angle is recorded, hardware is healthy, and preload is correct.
4. Archive search can find past projects by project, address, job number, client, or date.
5. Exports carry the field record: form data, trace data, machine settings, and one audit payload.

## Last-Minute Recovery

- App will not load: `sudo systemctl restart quadpod.service`
- Phone cannot connect: join the network currently used by the Pi, then use `http://quadpod.local`; hotspot fallback is `http://10.42.0.1`
- Network switch looks frozen: wait for the handoff page, join the selected network, then reopen Quadpod. Avoid repeated switch submissions.
- Pi shows undervoltage: replace the supply/cable and reboot before the demonstration.
- Load cell reads wrong: press `Tare`; if still wrong, do not run a real pull.
- Actuator does not move: verify controls are armed, power is connected, and use `scripts/probe_pwm.py` only if qualified.
- Pull will not start: read the red gate message, then check preload, calibration dates, angle, load cell, and actuator status.
