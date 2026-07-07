import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        importlib.reload(config)

    def test_auto_tension_stage_env_overrides_known_thresholds_only(self):
        override = "-5:90:0.35,-4.5:76:0.25,-4:66:0.19,-3.5:58:0.15,-3:50:0.11"

        with patch.dict(os.environ, {"QUADPOD_PRELOAD_AUTO_TENSION_STAGES": override}):
            loaded = importlib.reload(config)

        self.assertEqual(
            loaded.PRELOAD_AUTO_TENSION_STAGES[:5],
            [
                (-5.0, 90, 0.35),
                (-4.5, 76, 0.25),
                (-4.0, 66, 0.19),
                (-3.5, 58, 0.15),
                (-3.0, 50, 0.11),
            ],
        )
        self.assertEqual(loaded.PRELOAD_AUTO_TENSION_STAGES[5:], config.DEFAULT_PRELOAD_AUTO_TENSION_STAGES[5:])

    def test_auto_tension_stage_env_rejects_unknown_threshold(self):
        with patch.dict(os.environ, {"QUADPOD_PRELOAD_AUTO_TENSION_STAGES": "-4.8:90:0.2"}):
            with self.assertRaises(ValueError):
                importlib.reload(config)

    def test_auto_tension_poll_interval_defaults_to_sample_period(self):
        with patch.dict(
            os.environ,
            {
                "QUADPOD_SAMPLE_RATE_HZ": "40",
                "QUADPOD_PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS": "0.08",
            },
            clear=False,
        ):
            loaded = importlib.reload(config)

        self.assertEqual(loaded.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS, 0.025)

    def test_auto_tension_poll_interval_can_be_overridden(self):
        with patch.dict(os.environ, {"QUADPOD_PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS": "0.04"}):
            loaded = importlib.reload(config)

        self.assertEqual(loaded.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS, 0.04)


if __name__ == "__main__":
    unittest.main()
