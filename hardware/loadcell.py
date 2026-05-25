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
        self.reference_unit = reference_unit
        self.average_samples = max(1, int(average_samples))
        self.filter_window = max(1, int(filter_window))
        self.samples = deque(maxlen=self.filter_window)
        self.last_raw_lbs = 0.0
        self.last_error = ""
        self._mock_force = 0.0
        self._mock_zero = 0.0
        self.hx = None

        if not self.use_mock:
            self._init_hardware()

    def _init_hardware(self):
        try:
            import RPi.GPIO as GPIO  # noqa: F401
            from hx711 import HX711

            self.hx = HX711(dout_pin=self.dout_pin, pd_sck_pin=self.pd_sck_pin)
            self.hx.set_reading_format("MSB", "MSB")
            self.hx.set_reference_unit(self.reference_unit)
            self.hx.reset()
            self.hx.tare()
            self.last_error = ""
        except Exception as exc:
            self.last_error = f"HX711 init failed: {exc}"
            raise

    def tare(self):
        self.samples.clear()
        if self.use_mock:
            self._mock_zero = self._mock_force
            self.last_error = ""
            return True

        try:
            self.hx.tare()
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = f"HX711 tare failed: {exc}"
            return False

    def set_reference_unit(self, reference_unit):
        self.reference_unit = float(reference_unit)
        if self.hx is not None:
            self.hx.set_reference_unit(self.reference_unit)

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

        try:
            value = self.hx.get_weight(self.average_samples)
            self.hx.power_down()
            time.sleep(0.003)
            self.hx.power_up()
            self.last_raw_lbs = float(value)
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
        }
