# Quadpod Field Operator Guide

This guide is for employees performing shingle uplift resistance testing with the APEC Quadpod app. Follow company roof safety rules and the project investigation plan at all times.

## Do Not Test If

- Lightning is present.
- It is actively raining or the roof has puddles or excessive moisture.
- Wind makes roof work unsafe or may move equipment.
- Heat, cold, or ice makes roof work unsafe.
- Required load cell or temperature gun calibration dates have not been recorded.
- The test point is near roof equipment, ducts, skylights, electrical lines, seams, or visible blemishes.
- The Quadpod, shingle gripper, load cell, or actuator does not operate normally.

Testing may continue with a checked weather blocker only if APEC/engineering authorizes it as a documented deviation and the reason/approval is recorded in the app.

## Start the App

1. Power on the Raspberry Pi and Quadpod hardware.
2. Connect the phone to the Quadpod Wi-Fi network.
3. Open `http://quadpod.local:5000`.
4. If that does not load, open `http://10.42.0.1:5000`.
5. Open `Setup` and enter the operator PIN to arm controls.

## Start a Job

1. Open `Job`.
2. Enter project, client, involved party, date, job number, building number, foreman, and technicians.
3. Enter equipment IDs and calibration dates.
4. Confirm equipment calibration records are checked and dates are recorded.
5. Record humidity, barometric pressure, and weather notes.
6. Confirm weather and safety checks.
7. Mark any unsafe weather condition if present. If any unsafe weather box is checked, do not test unless an authorized weather deviation/bypass is recorded.

## Prepare a Test Point

1. Open `Test`.
2. Use the investigation plan to choose the roof area and test point.
3. Confirm the point is clear of hazards, representative of the roof condition, and free of seams/visible blemishes.
4. Record test number, area, roof area, air temperature, roof temperature, wind speed/direction, and angle.
5. The pull cable must be roughly perpendicular to the roof surface: 90 degrees within 5 degrees.
6. Record manufacturer/product information if visible.
7. Record wind-lift evidence, nail size/placement notes, and shingle observations.
8. Prepare a board showing test point name/number, building number, and identifiers.
9. Photograph the test point with the board visible in the company photo system when required.
10. In-app photo upload or photo reference is optional.

## Rig and Preload

1. Place the shingle gripper under the shingle reveal and clamp the shingle securely.
2. Set the Quadpod over the shingle gripper.
3. Spread legs fully and seat feet firmly.
4. Suspend the load cell and attach the gripper chain.
5. Align the load cell with the length of the gripper.
6. Press `Tare` with the rig hanging freely.
7. Take up cable slack.
8. Jog to a 10 lb preload.
9. Photograph the initial 10 lb load-cell reading in the company photo system when required.
10. Mark the photo boxes only when those photos were captured.

## Run the Pull Test

1. Stand clear.
2. Confirm the phone shows preload within 10 lb +/- tolerance.
3. Press `Start Pull Test`.
4. Watch the load and hardware. Use `Stop Test` if anything unsafe happens.
5. The app stops automatically for confirmed load drop/failure, max force, timeout, load-cell fault, or phone disconnect.
6. Continue only after the actuator is stopped.

## Record Results

1. Open `Review Result`.
2. Photograph the final load-cell reading in the company photo system when required.
3. Select failure type: glue gave way, shingle tear, operator stop, no failure before limit, or other.
4. Enter operator notes.
5. Complete deviation records if the procedure was not followed exactly.
6. Record repairs, sample removal, and maintenance notification if applicable.
7. Save and continue to the next test.

## Export and Shutdown

1. Repeat tests required by the investigation plan.
2. Open `Exports`.
3. Download `CSV Bundle ZIP`.
4. Use `Copy Job Folder to USB/Exports` when a flash drive or local job folder is needed.
5. Queue email only when SMTP sending has been configured.
6. Verify the export contains `job_and_tests.csv`, one `audit.json`, and per-test CSV files under `tests/`.
7. Clean and pack equipment.
8. Inspect the job site for stray objects and trash.
9. Shut down the Pi normally.
