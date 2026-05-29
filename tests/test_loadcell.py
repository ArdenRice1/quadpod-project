import sys
import types
import unittest

from hardware.loadcell import LoadCell


class FakeGPIO(types.SimpleNamespace):
    warnings_disabled = False

    @classmethod
    def setwarnings(cls, enabled):
        cls.warnings_disabled = not enabled


class FakeHX711:
    instances = []

    def __init__(self, dout_pin, pd_sck_pin):
        self.dout_pin = dout_pin
        self.pd_sck_pin = pd_sck_pin
        self.zero_calls = 0
        self.read_calls = 0
        FakeHX711.instances.append(self)

    def zero(self, times=1):
        self.zero_calls += times

    def get_weight_mean(self, times=1):
        self.read_calls += times
        return 42.5


class LoadCellHardwareCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.original_rpi = sys.modules.get("RPi")
        self.original_gpio = sys.modules.get("RPi.GPIO")
        self.original_hx711 = sys.modules.get("hx711")

        rpi_module = types.ModuleType("RPi")
        gpio_module = types.ModuleType("RPi.GPIO")
        gpio_module.setwarnings = FakeGPIO.setwarnings
        hx711_module = types.ModuleType("hx711")
        hx711_module.HX711 = FakeHX711

        sys.modules["RPi"] = rpi_module
        sys.modules["RPi.GPIO"] = gpio_module
        sys.modules["hx711"] = hx711_module
        FakeHX711.instances.clear()

    def tearDown(self):
        self._restore_module("RPi", self.original_rpi)
        self._restore_module("RPi.GPIO", self.original_gpio)
        self._restore_module("hx711", self.original_hx711)

    def _restore_module(self, name, original):
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original

    def test_hardware_mode_does_not_initialize_until_tare(self):
        load_cell = LoadCell(use_mock=False)

        self.assertIsNone(load_cell.hx)
        self.assertFalse(load_cell.hardware_ready)
        self.assertEqual(load_cell.get_force(), 0.0)
        self.assertIn("Press Tare", load_cell.last_error)

    def test_tare_initializes_hx711_without_legacy_methods(self):
        load_cell = LoadCell(use_mock=False, average_samples=3)

        self.assertTrue(load_cell.tare())
        self.assertTrue(load_cell.hardware_ready)
        self.assertEqual(FakeHX711.instances[0].zero_calls, 3)
        self.assertEqual(load_cell.get_force(), 42.5)
        self.assertEqual(FakeHX711.instances[0].read_calls, 3)


if __name__ == "__main__":
    unittest.main()
