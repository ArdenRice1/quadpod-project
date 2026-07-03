import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config


class ServiceConfigTests(unittest.TestCase):
    def test_service_uses_env_file_for_field_tuning(self):
        service = (ROOT / "scripts" / "quadpod.service").read_text()

        self.assertIn("EnvironmentFile=-/etc/quadpod.env", service)
        self.assertIn("Environment=QUADPOD_MOCK_HARDWARE=0", service)
        self.assertIn("Environment=QUADPOD_DATABASE=", service)

        blocked_prefixes = (
            "Environment=QUADPOD_PRELOAD_",
            "Environment=QUADPOD_LOADCELL_REFERENCE_UNIT",
            "Environment=QUADPOD_SAMPLE_RATE_HZ",
            "Environment=QUADPOD_VICTOR_",
            "Environment=QUADPOD_PULL_DIRECTION",
            "Environment=QUADPOD_FAILURE_",
        )
        for line in service.splitlines():
            self.assertFalse(line.startswith(blocked_prefixes), line)

    def test_env_example_has_full_stage_override_without_secrets(self):
        example = (ROOT / "scripts" / "quadpod.env.example").read_text()

        self.assertNotIn("SMTP_PASSWORD", example)
        self.assertIn("QUADPOD_LOADCELL_REFERENCE_UNIT=10077", example)

        stage_line = next(
            line for line in example.splitlines() if line.startswith("QUADPOD_PRELOAD_AUTO_TENSION_STAGES=")
        )
        stages = stage_line.split("=", 1)[1].split(",")
        thresholds = [float(stage.split(":", 1)[0]) for stage in stages]

        self.assertEqual(thresholds, [stage[0] for stage in config.DEFAULT_PRELOAD_AUTO_TENSION_STAGES])


if __name__ == "__main__":
    unittest.main()
