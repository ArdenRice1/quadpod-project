# Quadpod Quick-Start Checklist

## Daily Start

1. Power on Pi, load cell, actuator controller, and Quadpod hardware.
2. Connect phone to Quadpod Wi-Fi.
3. Open `http://quadpod.local:5000`; fallback `http://10.42.0.1:5000`.
4. Open `Setup` and verify load cell/actuator status.
5. Enter operator PIN to arm controls.
6. Create or resume job.

## Before Each Pull

1. Confirm calibration dates are current.
2. Confirm no unsafe wind, lightning, rain/moisture, heat/cold hazard, or ice, or record an authorized weather bypass/deviation.
3. Confirm roof safety/PPE.
4. Select test point from investigation plan.
5. Confirm point is clear, representative, and free of blemishes/seams.
6. Record angle, temperatures, wind, shingle info, observations, and photo reference.
7. Photograph test point with board visible.
8. Tare load cell.
9. Preload to 10 lb +/- tolerance.
10. Photograph initial 10 lb reading.

## Pull and Result

1. Stand clear.
2. Press `Start Pull Test`.
3. Press `Stop Test` if anything unsafe occurs.
4. Review result.
5. Photograph final reading.
6. Select failure type.
7. Record notes, deviations, repairs, samples, and maintenance notification.
8. Save and repeat for next test.

## Export

1. Open `Exports`.
2. Download `Bundle ZIP`.
3. Confirm ZIP includes `summary.csv`, `report.html`, `audit.json`, `traces/`, and `photos/`.
4. Queue email if needed.

## Fast Troubleshooting

- Cannot connect: use fallback URL, confirm Quadpod Wi-Fi, restart Pi if needed.
- Load cell not reading: press Tare, check wiring, run `scripts/read_hx711_raw.py`.
- Actuator not moving: arm controls, verify power, run `scripts/probe_pwm.py`.
- Pull will not start: open `Setup`, clear red/warn statuses, confirm checklists, preload exactly to 10 lb +/- tolerance.
- Email did not send: download ZIP manually; email waits until internet and SMTP are available.
