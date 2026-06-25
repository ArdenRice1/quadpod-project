# Quadpod Quick-Start Checklist

## Daily Start

1. Power on Pi, load cell, actuator controller, and Quadpod hardware.
2. Connect phone to Quadpod Wi-Fi.
3. Open `http://quadpod.local`; fallback `http://10.42.0.1`. Port `5000` remains a legacy fallback.
4. Open `Setup` and verify load cell/actuator status.
5. Create or resume job.

## Before Each Pull

1. Confirm calibration dates are recorded.
2. Select test point from investigation plan.
3. Record angle, temperatures, wind, shingle info, and observations.
4. Tare load cell.
5. Preload to 10 lb +/- tolerance.

## Pull and Result

1. Stand clear.
2. Press `Start Pull Test`.
3. Press `Stop Test` if anything unsafe occurs.
4. Review result.
5. Select failure type.
6. Record notes and any deviation information.
7. Save and repeat for next test.

## Export

1. Open `Archive`.
2. Download `Bundle ZIP`.
3. Confirm ZIP includes `Project_Job#_ALL.csv`, `audit.json`, and named test CSV files under `tests/`.
4. Use `Copy Job Folder to USB/Exports` for a job folder with the same files.
5. Queue email if SMTP has been configured.

## Fast Troubleshooting

- Cannot connect: join the network Quadpod was switched to, then use `http://quadpod.local`; in hotspot mode use `http://10.42.0.1`.
- Network switch appears stuck: wait at least 15 seconds, join the target Wi-Fi/hotspot, then reopen the stable URL. Do not repeatedly submit switch commands.
- Pi power warning: replace the power supply/cable before troubleshooting intermittent Wi-Fi. `vcgencmd get_throttled` should return `0x0` after a clean reboot and stable power.
- Load cell not reading: press Tare, check wiring, run `scripts/read_hx711_raw.py`.
- Actuator not moving: arm controls, verify power, run `scripts/probe_pwm.py`.
- Pull will not start: open `Setup`, confirm load cell/actuator OK, calibration dates recorded, angle recorded, and preload exactly to 10 lb +/- tolerance.
- Email did not send: download ZIP manually; Archive shows whether SMTP is configured.
