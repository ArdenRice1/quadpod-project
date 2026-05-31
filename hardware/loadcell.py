import random
import time
from collections import deque

from config import (
    LOADCELL_AVERAGE_SAMPLES,
    LOADCELL_DOUT_PIN,
    LOADCELL_FILTER_WINDOW,
    LOADCELL_PD_SCK_PIN,
    LOADCELL_REFERENCE_UNIT,
    USE_MOCK_HARDWARE,
)


class LoadCell:
    def __init__(
        self,
        use_mock=USE_MOCK_HARDWARE,
        dout_pin=LOADCELL_DOUT_PIN,
        pd_sck_pin=LOADCELL_PD_SCK_PIN,
        reference_unit=LOADCELL_REFERENCE_UNIT,
        average_samples=LOADCELL_AVERAGE_SAMPLES,
        filter_window=LOADCELL_FILTER_WINDOW,
    ):
        self.use_mock = use_mock
        self.dout_pin = dout_pin
        self.pd_sck_pin = pd_sck_pin
        self.reference_unit = float(reference_unit)
        self.average_samples = max(1, int(average_samples))
        self.filter_window = max(1, int(filter_window))
        self.samples = deque(maxlen=self.filter_window)
        self.last_raw_lbs = 0.0
        self.last_raw_counts = 0.0
        self.last_error = ""
        self._mock_force = 0.0
        self._mock_zero = 0.0
        self._zero_counts = 0.0
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

    def _read_raw_counts(self):
        values = []
        for _ in range(self.average_samples):
            raw = self._read_raw_counts_once()
            # Drop impossible single-sample rail glitches without hiding real faults.
            if raw in (-8388608, 8388607, 4194303, -4194304):
                continue
            values.append(float(raw))

        if not values:
            raise ValueError("HX711 returned only saturated/glitch samples")
        return sum(values) / len(values)

    def tare(self):
        self.samples.clear()
        if self.use_mock:
            self._mock_zero = self._mock_force
            self.last_error = ""
            return True

        try:
            self._init_hardware()
            self._zero_counts = self._read_raw_counts()
            self.last_raw_counts = self._zero_counts
            self.last_raw_lbs = 0.0
            self.last_error = ""
            return True
        except Exception as exc:
            self.hardware_ready = False
            self.last_error = f"HX711 tare failed: {exc}"
            return False

    def set_reference_unit(self, reference_unit):
        self.reference_unit = float(reference_unit)

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

    def _read_force(self):
        if self.use_mock:
            noise = random.uniform(-0.08, 0.08)
            self.last_raw_lbs = max(0.0, self._mock_force - self._mock_zero + noise)
            return self.last_raw_lbs

        if self.gpio is None or not self.hardware_ready:
            self.last_error = "Load cell not initialized. Press Tare on the Pre-Test screen."
            return self.last_raw_lbs

        try:
            raw_counts = self._read_raw_counts()
            self.last_raw_counts = raw_counts
            self.last_raw_lbs = (raw_counts - self._zero_counts) / self.reference_unit
            self.last_error = ""
            return self.last_raw_lbs
        except Exception as exc:
            self.last_error = f"HX711 read failed: {exc}"
            return self.last_raw_lbs

    def health(self):
        return {
            "mock": self.use_mock,
            "ok": not self.last_error,
            "last_error": self.last_error,
            "reference_unit": self.reference_unit,
            "filter_window": self.filter_window,
            "hardware_ready": self.hardware_ready,
            "last_raw_counts": self.last_raw_counts,
            "zero_counts": self._zero_counts,
        }
