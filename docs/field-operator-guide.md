# Quadpod Field Operator Guide

This guide is for employees performing shingle uplift resistance testing with the APEC Quadpod app. Follow company roof safety rules and the project investigation plan at all times.

## Do Not Test If

- Required load cell or temperature gun calibration dates have not been recorded.
- The Quadpod, shingle gripper, load cell, or actuator does not operate normally.

Use normal company roof-safety judgment before testing. The app records the measurements; it does not replace field safety decisions.

## Start the App

1. Power on the Raspberry Pi and Quadpod hardware.
2. Connect the phone to the Quadpod Wi-Fi network.
3. Open `http://quadpod.local`.
4. In hotspot mode, use `http://10.42.0.1` if the hostname does not load. Port `5000` is a legacy fallback.
5. Open `Setup` to confirm load cell, actuator, network, and calibration status.

Network and calibration tools are collapsed by default. Open only the panel needed. When switching networks, wait for the handoff page, join the target network on the phone, then reopen the displayed Quadpod address.

## Start a Job

1. Open `Job`.
2. Enter project, client, involved party, date, job number, building number, foreman, and technicians.
3. Enter equipment IDs and calibration dates.
4. Confirm equipment calibration dates are recorded.
5. Record humidity, barometric pressure, and weather notes.

## Prepare a Test Point

1. Open `Test`.
2. Use the investigation plan to choose the roof area and test point.
3. Confirm the point is clear of hazards, representative of the roof condition, and free of seams/visible blemishes.
4. Record test number, area, roof area, air temperature, roof temperature, wind speed/direction, angle, and shingle type.
5. The pull cable must be roughly perpendicular to the roof surface: 80-100 degrees is allowed.
6. Record wind-lift evidence and nail size/placement notes.
7. Prepare a board showing test point name/number, building number, and identifiers.

## Rig and Preload

1. Place the shingle gripper under the shingle reveal and clamp the shingle securely.
2. Set the Quadpod over the shingle gripper.
3. Spread legs fully and seat feet firmly.
4. Suspend the load cell and attach the gripper chain.
5. Align the load cell with the length of the gripper.
6. Press `Tare` with the rig hanging freely.
7. Take up cable slack.
8. Use `Auto Tension` after taring in the air and lowering the attachment into place.

## Run the Pull Test

1. Stand clear.
2. Confirm the phone shows Ready after Auto Tension settles.
3. Press `Start Pull Test`.
4. Watch the load and hardware. Use `Stop Test` if anything unsafe happens.
5. The app stops automatically for confirmed load drop/failure, max force, timeout, load-cell fault, or phone disconnect.
6. Continue only after the actuator is stopped.

## Record Results

1. Open `Review Result`.
2. Select failure type: glue gave way, shingle tear, operator stop, no failure before limit, or other.
3. Enter operator notes.
4. Complete deviation records if the procedure was not followed exactly.
5. Save and continue to the next test.

## Export and Shutdown

1. Repeat tests required by the investigation plan.
2. Open `Archive`.
3. Download `CSV Bundle ZIP`.
4. Use `Copy Job Folder to USB/Exports` when a flash drive or local job folder is needed.
5. Queue email only when SMTP sending has been configured.
6. Verify the export contains a named `Project_Job#_ALL.csv`, one `audit.json`, named per-test CSV files under `tests/`, and force-time graphs under `graphs/`.
7. Clean and pack equipment.
8. Inspect the job site for stray objects and trash.
9. Shut down the Pi normally.

## Power Warning

If Setup reports undervoltage or throttling, stop troubleshooting software and correct Pi power first. Use a stable Raspberry Pi power supply and a short, adequate cable. Unstable power can interrupt Wi-Fi, USB, storage, and hardware readings.
