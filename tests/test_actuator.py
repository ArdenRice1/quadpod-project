import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware.actuator import Actuator


class ActuatorTests(unittest.TestCase):
    def test_neutral_pulse_maps_to_expected_50hz_tick(self):
        actuator = Actuator(use_mock=True, frequency_hz=50)
        self.assertEqual(actuator.microseconds_to_ticks(1500), 307)

    def test_mock_stop_records_neutral_command(self):
        actuator = Actuator(use_mock=True)
        actuator.move_down(fast=True)
        actuator.stop()
        self.assertEqual(actuator.last_command, "neutral")
        self.assertEqual(actuator.last_pulse_us, 1500)

    def test_hardware_init_passes_explicit_i2c_bus(self):
        class FakePCA9685:
            def __init__(self, address, busnum):
                self.address = address
                self.busnum = busnum
                self.frequency = None
                self.commands = []

            def set_pwm_freq(self, frequency):
                self.frequency = frequency

            def set_pwm(self, channel, on_tick, off_tick):
                self.commands.append((channel, on_tick, off_tick))

        class FakeAdafruit:
            PCA9685 = FakePCA9685

        with patch.dict("sys.modules", {"Adafruit_PCA9685": FakeAdafruit}):
            actuator = Actuator(use_mock=False, address=0x40, busnum=1)

        self.assertEqual(actuator.pwm.address, 0x40)
        self.assertEqual(actuator.pwm.busnum, 1)
        self.assertEqual(actuator.pwm.frequency, 50)


if __name__ == "__main__":
    unittest.main()
