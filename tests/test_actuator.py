import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
