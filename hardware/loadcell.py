import datetime as dt
import json
import os
import random
import threading
import time
from collections import deque

from config import (
    CALIBRATION_PATH,
    LOADCELL_AVERAGE_SAMPLES,
    LOADCELL_CONTROL_SAMPLES,
    LOADCELL_DOUT_PIN,
    LOADCELL_FILTER_WINDOW,
    LOADCELL_GLITCH_MAX_CONSECUTIVE,
    LOADCELL_GLITCH_MAX_JUMP_LBS,
    LOADCELL_GLITCH_MAX_RESETS,
    LOADCELL_GLITCH_REJECT,
    LOADCELL_LIVENESS_WINDOW,
    LOADCELL_PD_SCK_PIN,
    LOADCELL_REFERENCE_UNIT,
    LOADCELL_RESET_BEFORE_TARE,
    LOADCELL_RESET_ON_READ_ERROR,
    LOADCELL_RESET_SECONDS,
    LOADCELL_TRIM_EXTREMES,
    USE_MOCK_HARDWARE,
)


def save_calibration_record(reference_unit, source, path=CALIBRATION_PATH, today=None):
    """Record device calibration provenance atomically.

    reference_unit stays canonical in /etc/quadpod.env; this file only records
    the value, the date it was last set on THIS unit, and where it came from, so
    support/status can see when the load cell was last calibrated. Written via a
    temp file + os.replace so a crash mid-write can't leave a half-written JSON.
    """
    day = (today or dt.date.today()).isoformat()
    record = {
        "reference_unit": float(reference_unit),
        "calibrated_at": day,
        "source": str(source),
    }
    path = str(path)
    directory = os.path.dirname(path) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        os.replace(tmp, path)
    except OSError:
        # Provenance is best-effort; never let it break a calibration.
        return record
    return record


def load_calibration_record(path=CALIBRATION_PATH):
    """Return the persisted calibration record, or {} if absent/unreadable."""
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class LoadCell:
    def __init__(
        self,
        use_mock=USE_MOCK_HARDWARE,
        dout_pin=LOADCELL_DOUT_PIN,
        pd_sck_pin=LOADCELL_PD_SCK_PIN,
        reference_unit=LOADCELL_REFERENCE_UNIT,
        average_samples=LOADCELL_AVERAGE_SAMPLES,
        control_samples=LOADCELL_CONTROL_SAMPLES,
        filter_window=LOADCELL_FILTER_WINDOW,
        trim_extremes=LOADCELL_TRIM_EXTREMES,
        reset_seconds=LOADCELL_RESET_SECONDS,
        reset_before_tare=LOADCELL_RESET_BEFORE_TARE,
        reset_on_read_error=LOADCELL_RESET_ON_READ_ERROR,
    ):
        self.use_mock = use_mock
        self.dout_pin = dout_pin
        self.pd_sck_pin = pd_sck_pin
        self.reference_unit = float(reference_unit)
        self.average_samples = max(1, int(average_samples))
        self.control_samples = max(1, int(control_samples))
        self.filter_window = max(1, int(filter_window))
        self.trim_extremes = bool(trim_extremes)
        self.reset_seconds = max(0.0001, float(reset_seconds))
        self.reset_before_tare = bool(reset_before_tare)
        self.reset_on_read_error = bool(reset_on_read_error)
        # Serializes bit-banged HX711 access. The scan loop and the auto-tension
        # loop both read the load cell from different threads; without this they
        # can interleave clock pulses on the shared GPIO and corrupt readings.
        self._io_lock = threading.RLock()
        # Glitch rejection state (see _guard_glitch).
        self.glitch_reject = bool(LOADCELL_GLITCH_REJECT)
        self.glitch_max_jump = float(LOADCELL_GLITCH_MAX_JUMP_LBS)
        self.glitch_max_consecutive = max(1, int(LOADCELL_GLITCH_MAX_CONSECUTIVE))
        self.glitch_max_resets = max(0, int(LOADCELL_GLITCH_MAX_RESETS))
        self._last_good_lbs = None
        self._glitch_rejects = 0
        self._glitch_resets = 0
        self._glitch_total = 0
        self._glitch_reset_total = 0
        self.last_glitch = False
        self.samples = deque(maxlen=self.filter_window)
        self.last_raw_lbs = 0.0
        self.last_raw_counts = 0.0
        self.last_raw_range_counts = 0.0
        self.last_error = ""
        self._liveness_window = max(0, int(LOADCELL_LIVENESS_WINDOW))
        self._raw_history = deque(maxlen=self._liveness_window or 1)
        self._mock_force = 0.0
        self._mock_zero = 0.0
        self._zero_counts = 0.0
        self.calibrated_at = load_calibration_record().get("calibrated_at", "")
        self.gpio = None
        self.hardware_ready = self.use_mock

    def _init_hardware(self):
        if self.gpio is not None:
            return

        try:
            import RPi.GPIO as GPIO

            if hasattr(GPIO, "setwarnings"):
                GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pd_sck_pin, GPIO.OUT)
            GPIO.setup(self.dout_pin, GPIO.IN)
            GPIO.output(self.pd_sck_pin, False)
            self.gpio = GPIO
            self.hardware_ready = True
            self.last_error = ""
        except Exception as exc:
            self.hardware_ready = False
            self.last_error = f"HX711 GPIO init failed: {exc}"
            raise

    def _wait_ready(self, timeout=1.0):
        started = time.monotonic()
        while self.gpio.input(self.dout_pin):
            if time.monotonic() - started >= timeout:
                raise TimeoutError("HX711 DOUT did not go LOW/data-ready before timeout")

    def _read_raw_counts_once(self):
        self._wait_ready()
        value = 0
        for _ in range(24):
            self.gpio.output(self.pd_sck_pin, True)
            self.gpio.output(self.pd_sck_pin, False)
            value = (value << 1) | int(self.gpio.input(self.dout_pin))

        # One extra pulse selects channel A at 128 gain for the next conversion.
        self.gpio.output(self.pd_sck_pin, True)
        self.gpio.output(self.pd_sck_pin, False)

        value ^= 0x800000
        return value - 0x800000

    def _read_raw_counts(self, samples=None):
        with self._io_lock:
            return self._read_raw_counts_unlocked(samples=samples)

    def _read_raw_counts_unlocked(self, samples=None):
        sample_count = max(1, int(samples or self.average_samples))
        values = []
        for _ in range(sample_count):
            raw = self._read_raw_counts_once()
            # Drop impossible single-sample rail glitches without hiding real faults.
            if raw in (-8388608, 8388607, 4194303, -4194304):
                continue
            values.append(float(raw))

        if not values:
            raise ValueError("HX711 returned only saturated/glitch samples")
        self.last_raw_range_counts = max(values) - min(values)
        if self.trim_extremes and len(values) >= 5:
            values = sorted(values)[1:-1]
        return sum(values) / len(values)

    def _quick_resync(self):
        """Fast HX711 re-sync for glitch recovery: a brief PD_SCK-high pulse
        (>60us) powers the chip down and it wakes to channel A gain 128, so the
        clock/channel is back in phase. Far shorter than reset_hardware()'s full
        reset, so it barely perturbs the read cadence."""
        if self.use_mock:
            return True
        try:
            with self._io_lock:
                self._init_hardware()
                self.gpio.output(self.pd_sck_pin, True)
                time.sleep(0.001)
                self.gpio.output(self.pd_sck_pin, False)
            return True
        except Exception:
            return False

    def reset_hardware(self):
        if self.use_mock:
            return True
        try:
            with self._io_lock:
                self._init_hardware()
                self.gpio.output(self.pd_sck_pin, True)
                time.sleep(self.reset_seconds)
                self.gpio.output(self.pd_sck_pin, False)
            self.last_error = ""
            return True
        except Exception as exc:
            self.hardware_ready = False
            self.last_error = f"HX711 reset failed: {exc}"
            return False

    def tare(self):
        self.samples.clear()
        if self.use_mock:
            self._mock_zero = self._mock_force
            self.last_error = ""
            return True

        try:
            self._init_hardware()
            if self.reset_before_tare:
                self.reset_hardware()
            self._zero_counts = self._read_raw_counts()
            self.last_raw_counts = self._zero_counts
            self.last_raw_lbs = 0.0
            # Let the first post-tare reading establish the baseline. The
            # attachment may be lowered after tare and legitimately jump several
            # pounds negative.
            self._last_good_lbs = None
            self._glitch_rejects = 0
            self.last_error = ""
            return True
        except Exception as exc:
            self.hardware_ready = False
            self.last_error = f"HX711 tare failed: {exc}"
            return False

    def pause_glitch_reject(self):
        """Disable jump-rejection (e.g. during a pull test, where force changes
        fast and every real reading must be faithful)."""
        self.glitch_reject = False

    def resume_glitch_reject(self):
        self.glitch_reject = bool(LOADCELL_GLITCH_REJECT)
        self._last_good_lbs = None
        self._glitch_rejects = 0
        self._glitch_resets = 0

    def set_reference_unit(self, reference_unit):
        self.reference_unit = float(reference_unit)

    def persist_calibration(self, source):
        """Record current reference_unit + today's date as device provenance."""
        record = save_calibration_record(self.reference_unit, source)
        self.calibrated_at = record.get("calibrated_at", self.calibrated_at)
        return record

    def calibrate_from_known_weight(self, raw_delta, known_lbs):
        if known_lbs == 0:
            raise ValueError("known_lbs must be non-zero")
        self.set_reference_unit(float(raw_delta) / float(known_lbs))
        return self.reference_unit

    def set_mock_force(self, force_lbs):
        self._mock_force = max(0.0, float(force_lbs))

    def get_force(self):
        force = self._read_force()
        self.samples.append(force)
        return round(sum(self.samples) / len(self.samples), 3)

    def get_reading(self):
        return self.get_force()

    def get_control_force(self, samples=None):
        sample_count = self.control_samples if samples is None else max(1, int(samples))
        return round(self._read_force(samples=sample_count), 3)

    def _note_liveness(self, raw_counts):
        """Track raw counts across reads; return True if the amp looks stuck.

        A working HX711 always dithers a few counts, so a full window of
        byte-for-byte identical reads means a shorted/floating/frozen sensor
        (a dead DOUT reads a constant 0 or -1). Recovers automatically once the
        readings start dithering again.
        """
        if self._liveness_window <= 0:
            return False
        self._raw_history.append(float(raw_counts))
        if len(self._raw_history) < self._liveness_window:
            return False
        return (max(self._raw_history) - min(self._raw_history)) == 0.0

    def _read_force(self, samples=None):
        if self.use_mock:
            noise = random.uniform(-0.08, 0.08)
            self.last_raw_lbs = max(0.0, self._mock_force - self._mock_zero + noise)
            return self.last_raw_lbs

        if self.gpio is None or not self.hardware_ready:
            self.last_error = "Load cell not initialized. Press Tare on the Pre-Test screen."
            return self.last_raw_lbs

        try:
            raw_counts = self._read_raw_counts(samples=samples)
            self.last_raw_counts = raw_counts
            if self._note_liveness(raw_counts):
                self.last_error = "Load cell not responding -- check the connection."
                return self.last_raw_lbs
            lbs = (raw_counts - self._zero_counts) / self.reference_unit
            self.last_raw_lbs = self._guard_glitch(lbs)
            self.last_error = ""
            return self.last_raw_lbs
        except Exception as exc:
            if self.reset_on_read_error:
                self.reset_hardware()
            self.last_error = f"HX711 read failed: {exc}"
            return self.last_raw_lbs

    def _guard_glitch(self, lbs):
        """Reject a single physically-impossible jump (HX711 desync glitch).

        Real motion is a fraction of a lb per read; a glitch is a ~6 lb jump that
        bounces back. Reject reads that jump more than glitch_max_jump from the
        last good value, but accept after glitch_max_consecutive so a genuine fast
        change is never permanently blocked.
        """
        if not self.glitch_reject or self._last_good_lbs is None:
            self._last_good_lbs = lbs
            self.last_glitch = False
            return lbs
        if abs(lbs - self._last_good_lbs) > self.glitch_max_jump:
            self._glitch_rejects += 1
            self._glitch_total += 1
            self.last_glitch = True
            if self._glitch_rejects < self.glitch_max_consecutive:
                return self._last_good_lbs
            # Sustained burst: try to re-sync the HX711 rather than trust it.
            if self._glitch_resets < self.glitch_max_resets:
                self._glitch_resets += 1
                self._glitch_reset_total += 1
                self._glitch_rejects = 0
                try:
                    self._quick_resync()
                except Exception:
                    pass
                return self._last_good_lbs
            # Resets exhausted -> accept as a fail-safe (don't get stuck).
            self._glitch_rejects = 0
            self._glitch_resets = 0
            self._last_good_lbs = lbs
            self.last_glitch = False
            return lbs
        self._glitch_rejects = 0
        self._glitch_resets = 0
        self._last_good_lbs = lbs
        self.last_glitch = False
        return lbs

    def health(self):
        return {
            "mock": self.use_mock,
            "ok": not self.last_error,
            "last_error": self.last_error,
            "reference_unit": self.reference_unit,
            "calibrated_at": self.calibrated_at,
            "control_samples": self.control_samples,
            "filter_window": self.filter_window,
            "trim_extremes": self.trim_extremes,
            "hardware_ready": self.hardware_ready,
            "last_raw_counts": self.last_raw_counts,
            "last_raw_range_counts": self.last_raw_range_counts,
            "zero_counts": self._zero_counts,
            "glitch_rejects_total": self._glitch_total,
            "glitch_resets_total": self._glitch_reset_total,
            "last_glitch": self.last_glitch,
        }
