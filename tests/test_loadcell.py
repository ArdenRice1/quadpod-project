import datetime as dt
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from hardware.loadcell import (
    LoadCell,
    load_calibration_record,
    save_calibration_record,
)


class FakeGPIO(types.SimpleNamespace):
    BCM = "BCM"
    IN = "IN"
    OUT = "OUT"
    outputs = []
    reads = []

    @classmethod
    def reset(cls, bits=None):
        cls.outputs = []
        cls.reads = list(bits or [])

    @classmethod
    def setwarnings(cls, enabled):
        cls.warnings_disabled = not enabled

    @classmethod
    def setmode(cls, mode):
        cls.mode = mode

    @classmethod
    def setup(cls, pin, mode):
        cls.outputs.append(("setup", pin, mode))

    @classmethod
    def output(cls, pin, value):
        cls.outputs.append(("output", pin, bool(value)))

    @classmethod
    def input(cls, pin):
        if cls.reads:
            return cls.reads.pop(0)
        return 0


class LoadCellHardwareCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.original_rpi = sys.modules.get("RPi")
        self.original_gpio = sys.modules.get("RPi.GPIO")

        rpi_module = types.ModuleType("RPi")
        gpio_module = types.ModuleType("RPi.GPIO")
        for name in ("BCM", "IN", "OUT", "setwarnings", "setmode", "setup", "output", "input"):
            setattr(gpio_module, name, getattr(FakeGPIO, name))

        sys.modules["RPi"] = rpi_module
        sys.modules["RPi.GPIO"] = gpio_module
        FakeGPIO.reset()

    def tearDown(self):
        self._restore_module("RPi", self.original_rpi)
        self._restore_module("RPi.GPIO", self.original_gpio)

    def _restore_module(self, name, original):
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

    def _bits_for_raw(self, raw):
        encoded = raw & 0xFFFFFF
        return [0] + [(encoded >> bit) & 1 for bit in range(23, -1, -1)]

    def test_hardware_mode_does_not_initialize_until_tare(self):
        load_cell = LoadCell(use_mock=False)

        self.assertIsNone(load_cell.gpio)
        self.assertFalse(load_cell.hardware_ready)
        self.assertEqual(load_cell.get_force(), 0.0)
        self.assertIn("Press Tare", load_cell.last_error)

    def test_tare_initializes_and_reads_direct_gpio_hx711(self):
        FakeGPIO.reset(self._bits_for_raw(3900) + self._bits_for_raw(4050))
        load_cell = LoadCell(use_mock=False, average_samples=1, reference_unit=10.0)

        self.assertTrue(load_cell.tare())
        self.assertTrue(load_cell.hardware_ready)
        self.assertEqual(load_cell.last_raw_counts, 3900)
        self.assertEqual(load_cell.get_force(), 15.0)
        self.assertEqual(load_cell.last_raw_counts, 4050)

    def test_trimmed_mean_drops_high_and_low_raw_samples(self):
        raw_values = [1000, 1005, 50000, 1010, 995]
        FakeGPIO.reset([bit for raw in raw_values for bit in self._bits_for_raw(raw)])
        load_cell = LoadCell(use_mock=False, average_samples=5, reference_unit=10.0, trim_extremes=True)
        load_cell._init_hardware()

        self.assertEqual(load_cell._read_raw_counts(), 1005.0)
        self.assertEqual(load_cell.last_raw_range_counts, 49005.0)

    def test_control_force_uses_control_sample_count_without_filtering(self):
        FakeGPIO.reset(self._bits_for_raw(3900) + self._bits_for_raw(4050))
        load_cell = LoadCell(
            use_mock=False,
            average_samples=1,
            control_samples=1,
            filter_window=5,
            reference_unit=10.0,
        )

        self.assertTrue(load_cell.tare())
        self.assertEqual(load_cell.get_control_force(), 15.0)
        self.assertEqual(len(load_cell.samples), 0)

    def test_reset_hardware_pulses_clock_high_then_low(self):
        load_cell = LoadCell(use_mock=False, reset_seconds=0.0001)

        self.assertTrue(load_cell.reset_hardware())
        self.assertIn(("output", load_cell.pd_sck_pin, True), FakeGPIO.outputs)
        self.assertEqual(FakeGPIO.outputs[-1], ("output", load_cell.pd_sck_pin, False))


class LoadCellLivenessTests(unittest.TestCase):
    def test_flags_stuck_sensor_after_full_window(self):
        lc = LoadCell(use_mock=True)
        lc._liveness_window = 4
        self.assertFalse(lc._note_liveness(1000.0))
        self.assertFalse(lc._note_liveness(1000.0))
        self.assertFalse(lc._note_liveness(1000.0))
        self.assertTrue(lc._note_liveness(1000.0))  # 4 byte-for-byte identical -> stuck

    def test_ok_when_readings_dither(self):
        lc = LoadCell(use_mock=True)
        lc._liveness_window = 4
        for i in range(12):
            self.assertFalse(lc._note_liveness(1000.0 + (i % 2)))

    def test_recovers_after_dither_resumes(self):
        lc = LoadCell(use_mock=True)
        lc._liveness_window = 3
        self.assertFalse(lc._note_liveness(5.0))
        self.assertFalse(lc._note_liveness(5.0))
        self.assertTrue(lc._note_liveness(5.0))    # stuck
        self.assertFalse(lc._note_liveness(6.0))   # dither returns -> recovered

    def test_disabled_when_window_zero(self):
        lc = LoadCell(use_mock=True)
        lc._liveness_window = 0
        for _ in range(50):
            self.assertFalse(lc._note_liveness(1000.0))


class CalibrationRecordTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "calibration.json"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_round_trip(self):
        record = save_calibration_record(
            10077.0, "bench-script", path=self.path, today=dt.date(2026, 7, 21)
        )
        self.assertEqual(record["reference_unit"], 10077.0)
        self.assertEqual(record["calibrated_at"], "2026-07-21")
        self.assertEqual(record["source"], "bench-script")
        loaded = load_calibration_record(path=self.path)
        self.assertEqual(loaded, record)

    def test_write_is_atomic_no_temp_left(self):
        save_calibration_record(1.0, "runtime", path=self.path)
        siblings = list(Path(self.tempdir.name).iterdir())
        self.assertEqual([p.name for p in siblings], ["calibration.json"])

    def test_load_missing_returns_empty(self):
        self.assertEqual(load_calibration_record(path=self.path), {})

    def test_load_corrupt_returns_empty(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_calibration_record(path=self.path), {})


if __name__ == "__main__":
    unittest.main()
