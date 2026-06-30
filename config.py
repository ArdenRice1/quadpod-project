import os
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
    return float(value)


def env_int(name, default):
    value = os.getenv(name)
    if value in (None, ""):
        return int(default)
    return int(value)


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

# PCA9685 / Victor SPX PWM settings. Pulse widths are in microseconds.
PWM_I2C_ADDRESS = env_int("QUADPOD_PWM_I2C_ADDRESS", 0x40)
PWM_I2C_BUSNUM = env_int("QUADPOD_PWM_I2C_BUSNUM", 1)
PWM_FREQUENCY_HZ = env_int("QUADPOD_PWM_FREQUENCY_HZ", 50)
VICTOR_CHANNEL = env_int("QUADPOD_VICTOR_CHANNEL", 0)
VICTOR_NEUTRAL_US = env_int("QUADPOD_VICTOR_NEUTRAL_US", 1500)
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
PRELOAD_MIN_LBS = env_float("QUADPOD_PRELOAD_MIN_LBS", 0.0)
PRELOAD_MAX_LBS = env_float("QUADPOD_PRELOAD_MAX_LBS", 0.5)
PRELOAD_AUTO_ABORT_LBS = env_float("QUADPOD_PRELOAD_AUTO_ABORT_LBS", 1.0)
PRELOAD_TOLERANCE_LBS = env_float("QUADPOD_PRELOAD_TOLERANCE_LBS", PRELOAD_MAX_LBS - PRELOAD_TARGET_LBS)
PRELOAD_STABILITY_SECONDS = env_float("QUADPOD_PRELOAD_STABILITY_SECONDS", 8.0)
PRELOAD_AUTO_TIMEOUT_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_TIMEOUT_SECONDS", 180.0)
PRELOAD_AUTO_DEADBAND_LBS = env_float("QUADPOD_PRELOAD_AUTO_DEADBAND_LBS", 0.2)
PRELOAD_AUTO_SPEED_PERCENT = env_int("QUADPOD_PRELOAD_AUTO_SPEED_PERCENT", 10)
PRELOAD_AUTO_MIN_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_MIN_PULSE_SECONDS", 0.005)
PRELOAD_AUTO_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_PULSE_SECONDS", 0.006)
PRELOAD_AUTO_PULSE_CHECK_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_PULSE_CHECK_SECONDS", 0.02)
PRELOAD_AUTO_DOWN_PULSE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DOWN_PULSE_SECONDS", 0.01)
PRELOAD_AUTO_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_SETTLE_SECONDS", 8.0)
PRELOAD_AUTO_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_SETTLE_MAX_SECONDS", 20.0)
PRELOAD_AUTO_COARSE_UNTIL_LBS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_UNTIL_LBS", -3.0)
PRELOAD_AUTO_COARSE_SETTLE_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_SETTLE_SECONDS", 0.75)
PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS", 1.5)
PRELOAD_AUTO_STABLE_WINDOW_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_STABLE_WINDOW_SECONDS", 4.0)
PRELOAD_AUTO_STABLE_DELTA_LBS = env_float("QUADPOD_PRELOAD_AUTO_STABLE_DELTA_LBS", 0.2)
PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_WINDOW_SECONDS", 20.0)
PRELOAD_AUTO_DRIFT_MAX_DROP_LBS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_MAX_DROP_LBS", 0.15)
PRELOAD_AUTO_DRIFT_WARN_SECONDS = env_float("QUADPOD_PRELOAD_AUTO_DRIFT_WARN_SECONDS", 60.0)
DEFAULT_PRELOAD_AUTO_TENSION_STAGES = [
    (-5.0, 80, 0.25),
    (-4.5, 68, 0.18),
    (-4.0, 60, 0.14),
    (-3.5, 52, 0.11),
    (-3.0, 44, 0.09),
    (-2.5, 40, 0.08),
    (-2.0, 34, 0.06),
    (-1.5, 28, 0.045),
    (-1.0, 24, 0.035),
    (-0.8, 20, 0.025),
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
EMAIL_ENABLED = env_bool("QUADPOD_EMAIL_ENABLED", False)
EMAIL_TO = os.getenv("QUADPOD_EMAIL_TO", "")
SMTP_HOST = os.getenv("QUADPOD_SMTP_HOST", "")
SMTP_PORT = env_int("QUADPOD_SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("QUADPOD_SMTP_USERNAME", "")
EMAIL_FROM = os.getenv("QUADPOD_EMAIL_FROM", SMTP_USERNAME)
SMTP_PASSWORD = os.getenv("QUADPOD_SMTP_PASSWORD", "")
SMTP_USE_TLS = env_bool("QUADPOD_SMTP_USE_TLS", True)
EMAIL_MAX_ATTEMPTS = env_int("QUADPOD_EMAIL_MAX_ATTEMPTS", 5)
