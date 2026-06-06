# Quadpod Quick-Start Checklist

## Daily Start

1. Power on Pi, load cell, actuator controller, and Quadpod hardware.
2. Connect phone to Quadpod Wi-Fi.
3. Open `http://quadpod.local:5000`; fallback `http://10.42.0.1:5000`.
4. Open `Setup` and verify load cell/actuator status.
5. Enter operator PIN to arm controls.
6. Create or resume job.

## Before Each Pull

1. Confirm calibration dates are recorded.
2. Confirm no unsafe wind, lightning, rain/moisture, heat/cold hazard, or ice, or record an authorized weather bypass/deviation.
3. Confirm roof safety/PPE.
4. Select test point from investigation plan.
5. Confirm point is clear, representative, and free of blemishes/seams.
6. Record angle, temperatures, wind, shingle info, observations, and optional photo reference.
7. Use the company photo system for required photos; in-app photo upload/reference is optional.
8. Tare load cell.
9. Preload to 10 lb +/- tolerance.
10. Photograph initial 10 lb reading in the company photo system if required by the job.

## Pull and Result

1. Stand clear.
2. Press `Start Pull Test`.
3. Press `Stop Test` if anything unsafe occurs.
4. Review result.
5. Photograph final reading in the company photo system if required by the job.
6. Select failure type.
7. Record notes, deviations, repairs, samples, and maintenance notification.
8. Save and repeat for next test.

## Export

1. Open `Exports`.
2. Download `Bundle ZIP`.
3. Confirm ZIP includes `job_and_tests.csv`, `audit.json`, and `tests/`.
4. Use `Copy Job Folder to USB/Exports` for a job folder with the same files.
5. Queue email if SMTP has been configured.

## Fast Troubleshooting

- Cannot connect: use fallback URL, confirm Quadpod Wi-Fi, restart Pi if needed.
- Load cell not reading: press Tare, check wiring, run `scripts/read_hx711_raw.py`.
- Actuator not moving: arm controls, verify power, run `scripts/probe_pwm.py`.
- Pull will not start: open `Setup`, clear red/warn statuses, confirm checklists, preload exactly to 10 lb +/- tolerance.
- Email did not send: download ZIP manually; email waits until internet and SMTP are available.
