import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / "flask_app"
DATA_DIR = APP_DIR / "data"
EXPORT_DIR = APP_DIR / "static" / "exports"
PHOTO_DIR = APP_DIR / "static" / "photos"
USB_EXPORT_ROOT = os.getenv("QUADPOD_USB_EXPORT_ROOT", "")

APP_VERSION = "0.3.0-field"
SECRET_KEY = os.getenv("QUADPOD_SECRET_KEY", "change-this-on-the-pi")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_float(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        # A bad value in /etc/quadpod.env must not crash the whole service at
        # import (that would leave a headless unit with no UI to recover). Warn
        # and fall back to the safe default.
        sys.stderr.write(f"[config] {name}={value!r} is not a valid number; using default {default}\n")
        return float(default)


def env_int(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError):
        sys.stderr.write(f"[config] {name}={value!r} is not a valid integer; using default {default}\n")
        return int(default)


def env_stage_overrides(name, default):
    value = os.getenv(name)
    stages = list(default)
    if value in (None, ""):
        return stages

    by_threshold = {threshold: index for index, (threshold, _, _) in enumerate(stages)}
    for raw_stage in value.split(","):
        raw_stage = raw_stage.strip()
        if not raw_stage:
            continue
        parts = [part.strip() for part in raw_stage.split(":")]
        if len(parts) != 3:
            raise ValueError(f"{name} stage must be threshold:speed:pulse, got {raw_stage!r}")
        threshold = float(parts[0])
        speed_percent = int(parts[1])
        pulse_seconds = float(parts[2])
        if threshold not in by_threshold:
            raise ValueError(f"{name} threshold {threshold} does not match a known auto tension stage")
        if not 1 <= speed_percent <= 100:
            raise ValueError(f"{name} speed must be 1-100 percent, got {speed_percent}")
        if not 0.005 <= pulse_seconds <= 0.5:
            raise ValueError(f"{name} pulse must be 0.005-0.5 seconds, got {pulse_seconds}")
        stages[by_threshold[threshold]] = (threshold, speed_percent, pulse_seconds)
    return stages


USE_MOCK_HARDWARE = env_bool("QUADPOD_MOCK_HARDWARE", True)
DATABASE_PATH = os.getenv("QUADPOD_DATABASE", str(DATA_DIR / "quadpod.db"))

# HX711 load cell pins and calibration.
LOADCELL_DOUT_PIN = env_int("QUADPOD_LOADCELL_DOUT_PIN", 5)
LOADCELL_PD_SCK_PIN = env_int("QUADPOD_LOADCELL_PD_SCK_PIN", 6)
LOADCELL_REFERENCE_UNIT = env_float("QUADPOD_LOADCELL_REFERENCE_UNIT", 1.0)
LOADCELL_AVERAGE_SAMPLES = env_int("QUADPOD_LOADCELL_AVERAGE_SAMPLES", 5)
LOADCELL_FILTER_WINDOW = env_int("QUADPOD_LOADCELL_FILTER_WINDOW", 5)
LOADCELL_CONTROL_SAMPLES = env_int("QUADPOD_LOADCELL_CONTROL_SAMPLES", 3)
LOADCELL_TRIM_EXTREMES = env_bool("QUADPOD_LOADCELL_TRIM_EXTREMES", True)
LOADCELL_RESET_SECONDS = env_float("QUADPOD_LOADCELL_RESET_SECONDS", 0.05)
LOADCELL_RESET_BEFORE_TARE = env_bool("QUADPOD_LOADCELL_RESET_BEFORE_TARE", True)
LOADCELL_RESET_ON_READ_ERROR = env_bool("QUADPOD_LOADCELL_RESET_ON_READ_ERROR", True)
# Liveness: a live HX711 always dithers a few counts. If this many consecutive
# reads are byte-for-byte identical the amp is stuck/disconnected (a shorted or
# floating DOUT reads a constant 0 or -1), so flag a fault instead of trusting it.
# Set 0 to disable. Large enough that a real steady load never trips it.
LOADCELL_LIVENESS_WINDOW = env_int("QUADPOD_LOADCELL_LIVENESS_WINDOW", 24)
# Glitch rejection: the bit-banged HX711 occasionally returns a spurious reading
# (~6 lb jump, clustering near a fixed desync value) that bounces back within a
# few samples. Reject a single read that jumps more than MAX_JUMP lb from the
# last good value; accept after MAX_CONSECUTIVE such reads so a genuine fast
# change is never permanently blocked. Real motion is <=~2.4 lb/sample.
LOADCELL_GLITCH_REJECT = env_bool("QUADPOD_LOADCELL_GLITCH_REJECT", True)
LOADCELL_GLITCH_MAX_JUMP_LBS = env_float("QUADPOD_LOADCELL_GLITCH_MAX_JUMP_LBS", 3.5)
LOADCELL_GLITCH_MAX_CONSECUTIVE = env_int("QUADPOD_LOADCELL_GLITCH_MAX_CONSECUTIVE", 3)
# A sustained glitch (HX711 channel desync) persists for many reads and would
# defeat the jump filter (it eventually accepts the bad value). On a sustained
# burst, reset/re-sync the HX711 instead of trusting it -- up to MAX_RESETS
# attempts, then accept as a fail-safe so we never get permanently stuck.
LOADCELL_GLITCH_MAX_RESETS = env_int("QUADPOD_LOADCELL_GLITCH_MAX_RESETS", 3)
LOADCELL_DISPLAY_ALPHA = env_float("QUADPOD_LOADCELL_DISPLAY_ALPHA", 0.35)
LOADCELL_DISPLAY_SNAP_DELTA_LBS = env_float("QUADPOD_LOADCELL_DISPLAY_SNAP_DELTA_LBS", 3.0)

# Device-side calibration provenance: reference_unit + the date it was last set
# on THIS unit + its source. Written whenever reference_unit changes; surfaced in
# health() for support. reference_unit itself stays canonical in /etc/quadpod.env.
CALIBRATION_PATH = Path(os.getenv("QUADPOD_CALIBRATION_FILE", str(DATA_DIR / "calibration.json")))

# PCA9685 / Victor SPX PWM settings. Pulse widths are in microseconds.
PWM_I2C_ADDRESS = env_int("QUADPOD_PWM_I2C_ADDRESS", 0x40)
PWM_I2C_BUSNUM = env_int("QUADPOD_PWM_I2C_BUSNUM", 1)
PWM_FREQUENCY_HZ = env_int("QUADPOD_PWM_FREQUENCY_HZ", 50)
VICTOR_CHANNEL = env_int("QUADPOD_VICTOR_CHANNEL", 0)
# True motor-stop for this Victor+PA-17P is 1650us (field-measured); the whole
# glide dead-band is tuned to it. A unit that boots without /etc/quadpod.env must
# still command real neutral, so the default matches the measured value.
VICTOR_NEUTRAL_US = env_int("QUADPOD_VICTOR_NEUTRAL_US", 1650)
VICTOR_FORWARD_US = env_int("QUADPOD_VICTOR_FORWARD_US", 2004)
VICTOR_REVERSE_US = env_int("QUADPOD_VICTOR_REVERSE_US", 250)
VICTOR_JOG_US = env_int("QUADPOD_VICTOR_JOG_US", VICTOR_FORWARD_US)
VICTOR_PULL_US = env_int("QUADPOD_VICTOR_PULL_US", 1850)
ACTUATOR_PULL_DIRECTION = os.getenv("QUADPOD_PULL_DIRECTION", "down").strip().lower()
ACTUATOR_INVERT = env_bool("QUADPOD_ACTUATOR_INVERT", False)

# Pull-test defaults. These remain configurable because field validation may
# tighten the numbers after APEC calibrates the assembled machine.
SAMPLE_RATE_HZ = env_float("QUADPOD_SAMPLE_RATE_HZ", 40.0)
PULL_TARGET_IN_PER_MIN = env_float("QUADPOD_PULL_TARGET_IPM", 5.0)
PRELOAD_TARGET_LBS = env_float("QUADPOD_PRELOAD_TARGET_LBS", 0.0)
PRELOAD_MIN_LBS = env_float("QUADPOD_PRELOAD_MIN_LBS", -0.5)
PRELOAD_MAX_LBS = env_float("QUADPOD_PRELOAD_MAX_LBS", 0.0)
PRELOAD_AUTO_ABORT_LBS = env_float("QUADPOD_PRELOAD_AUTO_ABORT_LBS", 1.0)
PRELOAD_READY_LATCH_MARGIN_LBS = env_float("QUADPOD_PRELOAD_READY_LATCH_MARGIN_LBS", 0.10)
# A pull must not begin with real pre-tension on the specimen (it biases the peak).
# Allow only load-cell noise above the band ceiling; a larger positive drift forces
# a re-seat rather than starting the pull. (Over-tension >1 lb is caught by the hold
# abort below.)
PRELOAD_READY_LATCH_POSITIVE_MARGIN_LBS = env_float("QUADPOD_PRELOAD_READY_LATCH_POSITIVE_MARGIN_LBS", 0.15)
PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS", 5.0)
PRELOAD_TOLERANCE_LBS = env_float(
    "QUADPOD_PRELOAD_TOLERANCE_LBS",
    max(abs(PRELOAD_TARGET_LBS - PRELOAD_MIN_LBS), abs(PRELOAD_MAX_LBS - PRELOAD_TARGET_LBS)),
)
PRELOAD_STABILITY_SECONDS = env_float("QUADPOD_PRELOAD_STABILITY_SECONDS", 8.0)
PRELOAD_AUTO_TIMEOUT_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_TIMEOUT_SECONDS", 180.0)

# Auto Tension continuous mode is the field path. The controller filters
# impossible control-read samples, predicts coast, and adapts speed by zone.
PRELOAD_AUTO_DEADBAND_LBS = env_float("QUADPOD_PRELOAD_AUTO_DEADBAND_LBS", 0.2)
PRELOAD_AUTO_DIRECT_LOAD_READ = env_bool("QUADPOD_PRELOAD_AUTO_DIRECT_LOAD_READ", True)
PRELOAD_AUTO_STOP_DURING_LOAD_READ = env_bool("QUADPOD_PRELOAD_AUTO_STOP_DURING_LOAD_READ", True)
PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES = env_int("QUADPOD_PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES", 5)
PRELOAD_AUTO_CONTROL_MIN_VALID_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_MIN_VALID_LBS", -20.0)
PRELOAD_AUTO_CONTROL_MAX_VALID_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_MAX_VALID_LBS", 10.0)
PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS", 1.5)
PRELOAD_AUTO_CONTROL_CONFIRM_MAX_RANGE_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_CONFIRM_MAX_RANGE_LBS", 3.0)
PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS", 25.0)
PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS", 0.05)
PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = env_int("QUADPOD_PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS", 2)
PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS", 0.35)
PRELOAD_AUTO_MOVING_CONTROL_SAMPLES = env_int("QUADPOD_PRELOAD_AUTO_MOVING_CONTROL_SAMPLES", 3)
PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS", 0.45)
PRELOAD_AUTO_SCAN_VERIFY_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_SCAN_VERIFY_SECONDS", 0.40)
PRELOAD_AUTO_PLAUSIBILITY_ENABLED = env_bool("QUADPOD_PRELOAD_AUTO_PLAUSIBILITY_ENABLED", True)
PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS", 0.35)
PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100 = env_float(
    "QUADPOD_PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100",
    18.0,
)
PRELOAD_AUTO_MODE = os.getenv("QUADPOD_PRELOAD_AUTO_MODE", "continuous").strip().lower()
PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS", 0.08)
PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS",
    min(PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS, 1.0 / max(1.0, SAMPLE_RATE_HZ)),
)
PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT", 3)
PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT", 23)
PRELOAD_AUTO_CONTINUOUS_KP = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_KP", 10.0)
PRELOAD_AUTO_CONTINUOUS_KD = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_KD", 12.0)
PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND",
    16.0,
)
PRELOAD_AUTO_CONTINUOUS_BRAKE_MARGIN_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_BRAKE_MARGIN_LBS", 0.35)
PRELOAD_AUTO_CONTINUOUS_SLOWDOWN_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_SLOWDOWN_LBS", 3.0)
PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND",
    0.32,
)
PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_START_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_START_LBS",
    -5.0,
)
PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_RATE_LBS_PER_SECOND = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_RATE_LBS_PER_SECOND",
    2.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_LBS",
    -5.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_LBS",
    -6.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_LBS",
    -4.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_LBS",
    -3.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS",
    -2.5,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS",
    -1.5,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS",
    -0.5,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT",
    16.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT",
    23.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT",
    12.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT",
    9.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT",
    7.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT",
    6.0,
)
PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT",
    3.5,
)
PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_CURVE = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_CURVE",
    1.4,
)
PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_RATE_SCALE = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_RATE_SCALE",
    1.0,
)
PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_RATE_LBS_PER_SECOND = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_RATE_LBS_PER_SECOND",
    0.05,
)
PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_SECONDS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_SECONDS",
    1.25,
)
PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT",
    10.0,
)
PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_FLOOR_START_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_FLOOR_START_LBS",
    -1.0,
)
PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT",
    4.0,
)
PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_STOP_MARGIN_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_STOP_MARGIN_LBS",
    0.08,
)
PRELOAD_AUTO_CONTINUOUS_CRAWL_ZONE_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_CRAWL_ZONE_LBS", 0.35)
PRELOAD_AUTO_CONTINUOUS_CRAWL_MIN_SPEED_PERCENT = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_CRAWL_MIN_SPEED_PERCENT", 1.0)
PRELOAD_AUTO_CONTINUOUS_CRAWL_MAX_SPEED_PERCENT = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_CRAWL_MAX_SPEED_PERCENT", 4.0)
PRELOAD_AUTO_CONTINUOUS_CRAWL_STOP_SPEED_PERCENT = env_float("QUADPOD_PRELOAD_AUTO_CONTINUOUS_CRAWL_STOP_SPEED_PERCENT", 0.5)
PRELOAD_HOLD_TRIM_ENABLED = env_bool("QUADPOD_PRELOAD_HOLD_TRIM_ENABLED", True)
PRELOAD_HOLD_TRIM_INTERVAL_SECONDS = env_float("QUADPOD_PRELOAD_HOLD_TRIM_INTERVAL_SECONDS", 1.0)
PRELOAD_HOLD_TRIM_STEP_US = env_int("QUADPOD_PRELOAD_HOLD_TRIM_STEP_US", 1)
PRELOAD_HOLD_TRIM_MAX_US = env_int("QUADPOD_PRELOAD_HOLD_TRIM_MAX_US", 15)
PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND = env_float("QUADPOD_PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND", 0.02)
PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS = env_float("QUADPOD_PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS", 2.0)
PRELOAD_AUTO_DOWN_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DOWN_PULSE_SECONDS", 0.01)
PRELOAD_AUTO_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_SETTLE_SECONDS", 8.0)
PRELOAD_AUTO_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_SETTLE_MAX_SECONDS", 20.0)
PRELOAD_AUTO_TARGET_LBS = env_float("QUADPOD_PRELOAD_AUTO_TARGET_LBS", -0.25)
PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS = env_float("QUADPOD_PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS", -0.30)
PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS = env_float("QUADPOD_PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS", 0.15)
PRELOAD_AUTO_PREDICT_STOP_LBS = env_float("QUADPOD_PRELOAD_AUTO_PREDICT_STOP_LBS", -0.15)
PRELOAD_AUTO_PREDICT_ENABLE_LBS = env_float("QUADPOD_PRELOAD_AUTO_PREDICT_ENABLE_LBS", -1.0)
PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS", 1.5)
PRELOAD_AUTO_RATE_WINDOW_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_RATE_WINDOW_SECONDS", 1.0)
PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND = env_float("QUADPOD_PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND", 0.15)

# -----------------------------------------------------------------------------
# Glide mode: smooth velocity Auto Tension for the compliant (spring-mass-damper)
# rig. Never stops to read (stopping rings the system); trusts moving reads with
# a light EMA, commands velocity proportional to the remaining force error so it
# glides slower as it closes, slews smoothly, and eases to neutral before target
# so the compliant string relaxes into band. Adaptive to attachment weight
# because velocity tracks live error, not fixed lb zones.
# Enable with QUADPOD_PRELOAD_AUTO_MODE=glide.
# -----------------------------------------------------------------------------
# Overshoot above 0 lb ruins the test, and the real (nailed/adhesive) specimen
# has a steeper wall than the bench mock, so bias BELOW zero: land at/just under
# 0 and never above. Undershooting slightly is acceptable; overshoot is not.
PRELOAD_GLIDE_TARGET_LBS = env_float("QUADPOD_PRELOAD_GLIDE_TARGET_LBS", -0.25)
PRELOAD_GLIDE_TOL_LBS = env_float("QUADPOD_PRELOAD_GLIDE_TOL_LBS", 0.25)
# Hard ceiling: a settled reading above this counts as overshoot (relax-or-fail);
# Ready is only declared at rest at or below READY_CEILING_LBS.
PRELOAD_GLIDE_READY_CEILING_LBS = env_float("QUADPOD_PRELOAD_GLIDE_READY_CEILING_LBS", 0.0)
PRELOAD_GLIDE_OVERSHOOT_LBS = env_float("QUADPOD_PRELOAD_GLIDE_OVERSHOOT_LBS", 0.10)
# Once force-rate signals the wall, latch to a crawl and never re-accelerate.
# Latch OFF by default: it was firing on normal slack-takeoff rate (far from the
# target) and pinning speed to crawl for the whole run. The instantaneous rate
# governor already slows near the wall and recovers when force stalls/drops.
PRELOAD_GLIDE_WALL_LATCH = env_bool("QUADPOD_PRELOAD_GLIDE_WALL_LATCH", False)
# Seated = at rest, stable, slack removed: load within [SEATED_FLOOR, READY_CEILING]
# (i.e. just below 0). This IS the band the pull-start gate accepts, so once
# seated it latches Ready and you can start the pull without re-running.
PRELOAD_GLIDE_SEATED_FLOOR_LBS = env_float("QUADPOD_PRELOAD_GLIDE_SEATED_FLOOR_LBS", PRELOAD_MIN_LBS)
PRELOAD_GLIDE_KP_PCT_PER_LB = env_float("QUADPOD_PRELOAD_GLIDE_KP_PCT_PER_LB", 12.0)
# Min effective duty: below ~14% the Victor/actuator is in its dead-band (pulse
# too close to the 1650us neutral) and does not move. Keep the floor above that.
PRELOAD_GLIDE_MIN_MOVE_PCT = env_float("QUADPOD_PRELOAD_GLIDE_MIN_MOVE_PCT", 14.0)
PRELOAD_GLIDE_MAX_PCT = env_float("QUADPOD_PRELOAD_GLIDE_MAX_PCT", 22.0)
# Ease earlier so there's less momentum at stop -> smaller coast/jounce overshoot
# past 0. Slight undershoot is fine; the micro-trim hold brings it back up.
PRELOAD_GLIDE_EASE_MARGIN_LBS = env_float("QUADPOD_PRELOAD_GLIDE_EASE_MARGIN_LBS", 0.25)
PRELOAD_GLIDE_RAMP_PCT_PER_S = env_float("QUADPOD_PRELOAD_GLIDE_RAMP_PCT_PER_S", 40.0)
PRELOAD_GLIDE_RAMP_DOWN_PCT_PER_S = env_float("QUADPOD_PRELOAD_GLIDE_RAMP_DOWN_PCT_PER_S", 120.0)
# Wall governor: slow by how fast force is RISING (proximity to the taut wall),
# not just by error. Above RATE_CRAWL the drive drops to CRAWL_PCT.
PRELOAD_GLIDE_RATE_SLOW_LBS_PER_S = env_float("QUADPOD_PRELOAD_GLIDE_RATE_SLOW_LBS_PER_S", 1.5)
PRELOAD_GLIDE_RATE_CRAWL_LBS_PER_S = env_float("QUADPOD_PRELOAD_GLIDE_RATE_CRAWL_LBS_PER_S", 3.5)
PRELOAD_GLIDE_CRAWL_PCT = env_float("QUADPOD_PRELOAD_GLIDE_CRAWL_PCT", 14.0)
PRELOAD_GLIDE_RATE_WINDOW_S = env_float("QUADPOD_PRELOAD_GLIDE_RATE_WINDOW_S", 0.3)
# Predict past feedback latency: ease/stop on load + rate*lookahead, using the
# raw (unfiltered) reading so the filter lag can't hide the wall.
PRELOAD_GLIDE_LOOKAHEAD_S = env_float("QUADPOD_PRELOAD_GLIDE_LOOKAHEAD_S", 0.25)
# Keep logging after Auto Tension finishes to observe drift/creep/hold behavior.
PRELOAD_GLIDE_POST_LOG_S = env_float("QUADPOD_PRELOAD_GLIDE_POST_LOG_S", 45.0)
PRELOAD_GLIDE_POST_LOG_INTERVAL_S = env_float("QUADPOD_PRELOAD_GLIDE_POST_LOG_INTERVAL_S", 0.2)
PRELOAD_GLIDE_EMA_ALPHA = env_float("QUADPOD_PRELOAD_GLIDE_EMA_ALPHA", 0.4)
PRELOAD_GLIDE_READ_SAMPLES = env_int("QUADPOD_PRELOAD_GLIDE_READ_SAMPLES", 1)
PRELOAD_GLIDE_STABLE_S = env_float("QUADPOD_PRELOAD_GLIDE_STABLE_S", 1.0)
PRELOAD_GLIDE_STABLE_LBS = env_float("QUADPOD_PRELOAD_GLIDE_STABLE_LBS", 0.15)
PRELOAD_GLIDE_MAX_LBS = env_float("QUADPOD_PRELOAD_GLIDE_MAX_LBS", 0.5)
PRELOAD_GLIDE_ABORT_LBS = env_float("QUADPOD_PRELOAD_GLIDE_ABORT_LBS", PRELOAD_AUTO_ABORT_LBS)
PRELOAD_GLIDE_TIMEOUT_S = env_float("QUADPOD_PRELOAD_GLIDE_TIMEOUT_S", 60.0)
PRELOAD_GLIDE_POLL_S = env_float("QUADPOD_PRELOAD_GLIDE_POLL_S", 0.02)
PRELOAD_GLIDE_RELAX_S = env_float("QUADPOD_PRELOAD_GLIDE_RELAX_S", 2.0)
# Post-glide seating: settle-then-verify with open-loop micro-pulses. The actuator
# back-drives (slack returns) after the glide stops; a continuous integral trim can't
# correct that on this stick-slip actuator -- below the breakaway it does nothing, above
# it the slow load cell can't catch the motion before it runs away (windup -> lurch into
# over-tension). Instead: wait out the fast slack-return (SETTLE_S), then nudge the load
# into [AIM_LO, AIM_HI] with short OPEN-LOOP micro-pulses (PULSE_US for PULSE_MS), stopping
# to re-measure AT REST (REST_S) between each -- so the slow sensor is an asset. Pulse size
# adapts to the random stick-slip. Validated 2026-07-16 across full and partial slack.
PRELOAD_GLIDE_HOLD_AFTER = env_bool("QUADPOD_PRELOAD_GLIDE_HOLD_AFTER", False)
PRELOAD_GLIDE_HOLD_TIMEOUT_S = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_TIMEOUT_S", 120.0)
PRELOAD_GLIDE_HOLD_SETTLE_S = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_SETTLE_S", 15.0)
PRELOAD_GLIDE_HOLD_AIM_LO_LBS = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_AIM_LO_LBS", -0.35)
PRELOAD_GLIDE_HOLD_AIM_HI_LBS = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_AIM_HI_LBS", -0.10)
PRELOAD_GLIDE_HOLD_PULSE_US = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_PULSE_US", 35)
PRELOAD_GLIDE_HOLD_PULSE_MIN_US = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_PULSE_MIN_US", 24)
PRELOAD_GLIDE_HOLD_PULSE_MAX_US = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_PULSE_MAX_US", 55)
PRELOAD_GLIDE_HOLD_PULSE_MS = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_PULSE_MS", 70)
PRELOAD_GLIDE_HOLD_PULSE_MS_MAX = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_PULSE_MS_MAX", 110)
PRELOAD_GLIDE_HOLD_REST_S = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_REST_S", 3.5)
PRELOAD_GLIDE_HOLD_MAX_ITERS = env_int("QUADPOD_PRELOAD_GLIDE_HOLD_MAX_ITERS", 12)
# Real over-tension abort. The load cell is noisy (physics), so tolerate up to ~1 lb
# before treating a positive reading as genuine over-tension; above this the hold
# stops, clears Ready, and tells the operator to check tension.
PRELOAD_GLIDE_HOLD_ABORT_LBS = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_ABORT_LBS", 1.0)
PRELOAD_GLIDE_HOLD_GENTLE_GAP_LBS = env_float("QUADPOD_PRELOAD_GLIDE_HOLD_GENTLE_GAP_LBS", 0.20)

# Legacy pulse mode is retained as a fallback/test harness. These settings are
# not used by the normal continuous Auto Tension mode unless mode is switched.
PRELOAD_AUTO_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_SPEED_PERCENT", 10)
PRELOAD_AUTO_MIN_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_MIN_PULSE_SECONDS", 0.005)
PRELOAD_AUTO_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_PULSE_SECONDS", 0.006)
PRELOAD_AUTO_PULSE_CHECK_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_PULSE_CHECK_SECONDS", 0.02)
PRELOAD_AUTO_COARSE_MAX_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_MAX_DELTA_LBS", 0.75)
PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS", 0.35)
PRELOAD_AUTO_FINAL_MAX_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_FINAL_MAX_DELTA_LBS", 0.12)
PRELOAD_AUTO_CONTACT_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_DELTA_LBS", 0.4)
PRELOAD_AUTO_CONTACT_MAX_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_MAX_DELTA_LBS", 0.35)
PRELOAD_AUTO_CONTACT_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_CONTACT_SPEED_PERCENT", 50)
PRELOAD_AUTO_CONTACT_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_PULSE_SECONDS", 0.1)
PRELOAD_AUTO_CONTACT_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_SETTLE_SECONDS", 0.5)
PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS", 1.25)
PRELOAD_AUTO_CONTACT_MODE_START_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_MODE_START_LBS", -2.5)
PRELOAD_AUTO_CONTACT_COARSE_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_CONTACT_COARSE_SPEED_PERCENT", 70)
PRELOAD_AUTO_CONTACT_COARSE_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_COARSE_PULSE_SECONDS", 0.18)
PRELOAD_AUTO_CONTACT_COARSE_MAX_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_CONTACT_COARSE_MAX_DELTA_LBS", 0.5)
PRELOAD_AUTO_MIN_STOP_MARGIN_LBS = env_float("QUADPOD_PRELOAD_AUTO_MIN_STOP_MARGIN_LBS", 0.08)
PRELOAD_AUTO_MAX_STOP_MARGIN_LBS = env_float("QUADPOD_PRELOAD_AUTO_MAX_STOP_MARGIN_LBS", 0.45)
PRELOAD_AUTO_COAST_MARGIN_SCALE = env_float("QUADPOD_PRELOAD_AUTO_COAST_MARGIN_SCALE", 1.25)
PRELOAD_AUTO_ADAPTIVE_PULSE_MIN_SCALE = env_float("QUADPOD_PRELOAD_AUTO_ADAPTIVE_PULSE_MIN_SCALE", 0.35)
PRELOAD_AUTO_ADAPTIVE_SPEED_MIN_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_ADAPTIVE_SPEED_MIN_PERCENT", 10)
PRELOAD_AUTO_APPROACH_DISTANCE_LBS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_DISTANCE_LBS", 0.8)
PRELOAD_AUTO_COARSE_UNTIL_LBS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_UNTIL_LBS", -3.0)
PRELOAD_AUTO_COARSE_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_SETTLE_SECONDS", 0.75)
PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS", 1.5)
PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS", PRELOAD_MIN_LBS - 0.15)
PRELOAD_AUTO_APPROACH_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_SETTLE_SECONDS", 0.5)
PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS", 1.25)
PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS", 0.05)
PRELOAD_AUTO_STABLE_WINDOW_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_STABLE_WINDOW_SECONDS", 4.0)
PRELOAD_AUTO_STABLE_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_STABLE_DELTA_LBS", 0.2)
PRELOAD_AUTO_IN_BAND_END_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_IN_BAND_END_SECONDS", 2.0)
PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS = env_float("QUADPOD_PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS", 0.03)
PRELOAD_AUTO_NEAR_BAND_DROP_REJECT_LBS = env_float("QUADPOD_PRELOAD_AUTO_NEAR_BAND_DROP_REJECT_LBS", 0.75)
PRELOAD_AUTO_NEGATIVE_JUMP_GUARD_START_LBS = env_float(
    "QUADPOD_PRELOAD_AUTO_NEGATIVE_JUMP_GUARD_START_LBS",
    PRELOAD_MIN_LBS - 0.5,
)
PRELOAD_AUTO_NEGATIVE_JUMP_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_NEGATIVE_JUMP_DELTA_LBS", 0.5)
PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_WINDOW_SECONDS", 20.0)
PRELOAD_AUTO_DRIFT_MAX_DROP_LBS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_MAX_DROP_LBS", 0.15)
PRELOAD_AUTO_DRIFT_WARN_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_WARN_SECONDS", 60.0)
PRELOAD_AUTO_TRACE_MAX_ENTRIES = env_int("QUADPOD_PRELOAD_AUTO_TRACE_MAX_ENTRIES", 300)
PRELOAD_AUTO_TRACE_DIR = Path(os.getenv("QUADPOD_PRELOAD_AUTO_TRACE_DIR", str(DATA_DIR / "auto_tension_traces")))
DEFAULT_PRELOAD_AUTO_TENSION_STAGES = [
    (-5.0, 80, 0.25),
    (-4.5, 68, 0.18),
    (-4.0, 60, 0.14),
    (-3.5, 52, 0.11),
    (-3.0, 44, 0.09),
    (-2.5, 44, 0.09),
    (-2.0, 38, 0.07),
    (-1.5, 32, 0.055),
    (-1.0, 28, 0.045),
    (-0.8, 24, 0.032),
    (-0.6, 17, 0.018),
    (-0.4, 14, 0.014),
    (-0.2, 12, 0.010),
    (0.0, 10, 0.006),
]
PRELOAD_AUTO_TENSION_STAGES = env_stage_overrides(
    "QUADPOD_PRELOAD_AUTO_TENSION_STAGES",
    DEFAULT_PRELOAD_AUTO_TENSION_STAGES,
)
FAILURE_DROP_LBS = env_float("QUADPOD_FAILURE_DROP_LBS", 12.0)
FAILURE_DROP_PERCENT = env_float("QUADPOD_FAILURE_DROP_PERCENT", 0.35)
FAILURE_CONFIRM_SAMPLES = env_int("QUADPOD_FAILURE_CONFIRM_SAMPLES", 8)
FAILURE_MIN_PEAK_LBS = env_float("QUADPOD_FAILURE_MIN_PEAK_LBS", 20.0)
MAX_FORCE_LBS = env_float("QUADPOD_MAX_FORCE_LBS", 400.0)
MAX_TEST_SECONDS = env_float("QUADPOD_MAX_TEST_SECONDS", 300.0)
DISCONNECT_STOP_SECONDS = env_float("QUADPOD_DISCONNECT_STOP_SECONDS", 3.0)
LOAD_STABLE_WINDOW_SECONDS = env_float("QUADPOD_LOAD_STABLE_WINDOW_SECONDS", 1.5)
LOAD_STABLE_DELTA_LBS = env_float("QUADPOD_LOAD_STABLE_DELTA_LBS", 0.75)
POST_STOP_LOG_MAX_SECONDS = env_float("QUADPOD_POST_STOP_LOG_MAX_SECONDS", 6.0)

# Pi-hosted WPA2 hotspot defaults for setup docs/scripts.
HOTSPOT_SSID_PREFIX = os.getenv("QUADPOD_HOTSPOT_PREFIX", "Quadpod")
HOTSPOT_IP = os.getenv("QUADPOD_HOTSPOT_IP", "10.42.0.1")
HOTSPOT_CIDR = os.getenv("QUADPOD_HOTSPOT_CIDR", "10.42.0.1/24")
PUBLIC_URL = os.getenv("QUADPOD_PUBLIC_URL", "http://quadpod.local")

# Email queue settings. Downloads always work even when these are unset.
EMAIL_FEATURE_VISIBLE = env_bool("QUADPOD_EMAIL_FEATURE_VISIBLE", False)
EMAIL_ENABLED = env_bool("QUADPOD_EMAIL_ENABLED", False)
EMAIL_TO = os.getenv("QUADPOD_EMAIL_TO", "")
SMTP_HOST = os.getenv("QUADPOD_SMTP_HOST", "")
SMTP_PORT = env_int("QUADPOD_SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("QUADPOD_SMTP_USERNAME", "")
EMAIL_FROM = os.getenv("QUADPOD_EMAIL_FROM", SMTP_USERNAME)
SMTP_PASSWORD = os.getenv("QUADPOD_SMTP_PASSWORD", "")
SMTP_USE_TLS = env_bool("QUADPOD_SMTP_USE_TLS", True)
EMAIL_MAX_ATTEMPTS = env_int("QUADPOD_EMAIL_MAX_ATTEMPTS", 5)
