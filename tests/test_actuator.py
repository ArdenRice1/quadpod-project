import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hardware.actuator import Actuator
from config import VICTOR_PULL_US


class ActuatorTests(unittest.TestCase):
    def test_neutral_pulse_maps_to_expected_50hz_tick(self):
        actuator = Actuator(use_mock=True, frequency_hz=50)
        self.assertEqual(actuator.microseconds_to_ticks(1650), 338)

    def test_mock_stop_records_neutral_command(self):
        actuator = Actuator(use_mock=True)
        actuator.move_down(fast=True)
        actuator.stop()
        self.assertEqual(actuator.last_command, "neutral")
        self.assertEqual(actuator.last_pulse_us, 1650)

    def test_pull_uses_fixed_pull_pulse_not_jog_speed_scale(self):
        actuator = Actuator(use_mock=True, pull_direction="down")

        actuator.move_down(fast=True, speed_percent=1)
        jog_pulse = actuator.last_pulse_us
        actuator.pull()

        self.assertNotEqual(actuator.last_pulse_us, jog_pulse)
        self.assertEqual(actuator.last_command, "down_pull")
        self.assertEqual(actuator.last_pulse_us, VICTOR_PULL_US)

    def test_up_pull_uses_mirrored_fixed_pull_pulse_not_jog_speed_scale(self):
        actuator = Actuator(use_mock=True, pull_direction="up")

        actuator.move_up(fast=True, speed_percent=1)
        jog_pulse = actuator.last_pulse_us
        actuator.pull()

        self.assertNotEqual(actuator.last_pulse_us, jog_pulse)
        self.assertEqual(actuator.last_command, "up_pull")
        self.assertEqual(actuator.last_pulse_us, actuator._mirror(VICTOR_PULL_US))

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

    def test_stop_retries_transient_pwm_failure(self):
        actuator = Actuator(use_mock=True)
        actuator._mock_pwm_fail = 2  # fail twice, then succeed within stop()'s retries
        self.assertTrue(actuator.stop())
        self.assertEqual(actuator.last_error, "")
        self.assertEqual(actuator.last_command, "neutral")

    def test_stop_reports_failure_after_exhausting_retries(self):
        actuator = Actuator(use_mock=True)
        actuator._mock_pwm_fail = 99  # exceeds stop()'s retry budget
        self.assertFalse(actuator.stop())
        self.assertIn("PWM command failed", actuator.last_error)

    def test_close_forces_neutral(self):
        actuator = Actuator(use_mock=True)
        actuator.move_down(fast=True)
        actuator.close()
        self.assertEqual(actuator.last_command, "neutral")
        self.assertEqual(actuator.last_pulse_us, 1650)

    def test_movement_command_does_not_retry_by_default(self):
        # Only stop()/close() retry; movement commands keep the old fail-fast behavior.
        actuator = Actuator(use_mock=True)
        actuator._mock_pwm_fail = 1
        self.assertFalse(actuator.set_pulse_us(1700, command="test"))
        self.assertIn("PWM command failed", actuator.last_error)


if __name__ == "__main__":
    unittest.main()
