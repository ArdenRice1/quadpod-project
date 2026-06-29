import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage
from engine import QuadpodEngine


class ControlGateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()
        self.engine = QuadpodEngine(use_mock=True)
        self.job_id = storage.create_job(self._job_form())
        self.test_id = storage.create_test(self.job_id, self._test_form())

    def tearDown(self):
        self.engine.stop("test cleanup")
        self.tempdir.cleanup()

    def _job_form(self, **updates):
        form = {
            "project_name": "Gate Job",
            "job_number": "G-001",
            "load_cell_id": "LC-1",
            "load_cell_calibration_date": "2099-01-01",
            "ir_temp_gun_id": "IR-1",
            "ir_temp_gun_calibration_date": "2099-01-01",
        }
        form.update(updates)
        return form

    def _test_form(self, **updates):
        form = {
            "test_number": "1",
            "angle_degrees": "90",
        }
        form.update(updates)
        return form

    def _set_load(self, value):
        self.engine.state["current_load"] = value

    def test_start_rejects_low_preload(self):
        self._set_load(-0.1)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("tension", message)

    def test_start_rejects_high_preload(self):
        self._set_load(1.1)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("tension", message)

    def test_start_accepts_preload_inside_tight_band(self):
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_auto_preload_uses_configured_pull_direction_to_increase_load(self):
        self.engine.actuator.pull_direction = "up"
        self.engine.state["jog_speed_percent"] = 1
        self.engine._move_auto_preload_direction_locked(increase=True)
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertGreater(self.engine.actuator.last_pulse_us, 1200)
        self.assertLess(self.engine.actuator.last_pulse_us, 1500)
        self.engine._move_auto_preload_direction_locked(increase=False)
        self.assertEqual(self.engine.actuator.last_command, "down_fast")

    def test_auto_preload_stages_get_smaller_near_zero_tension(self):
        stages = [
            self.engine._auto_preload_stage_for_load(-10.0, True),
            self.engine._auto_preload_stage_for_load(-4.75, True),
            self.engine._auto_preload_stage_for_load(-4.25, True),
            self.engine._auto_preload_stage_for_load(-3.75, True),
            self.engine._auto_preload_stage_for_load(-3.25, True),
            self.engine._auto_preload_stage_for_load(-2.75, True),
            self.engine._auto_preload_stage_for_load(-2.25, True),
            self.engine._auto_preload_stage_for_load(-1.75, True),
            self.engine._auto_preload_stage_for_load(-1.25, True),
            self.engine._auto_preload_stage_for_load(-0.9, True),
            self.engine._auto_preload_stage_for_load(-0.7, True),
            self.engine._auto_preload_stage_for_load(-0.5, True),
            self.engine._auto_preload_stage_for_load(-0.3, True),
            self.engine._auto_preload_stage_for_load(-0.1, True),
        ]

        for earlier, later in zip(stages, stages[1:]):
            self.assertGreaterEqual(earlier["pulse_seconds"], later["pulse_seconds"])
            self.assertGreater(earlier["speed_percent"], later["speed_percent"])
        self.assertEqual(stages[-1]["speed_percent"], 10)
        self.assertEqual(stages[-1]["pulse_seconds"], 0.006)

    def test_auto_preload_fast_course_stage_for_hanging_attachment_weight(self):
        stage = self.engine._auto_preload_stage_for_load(-8.0, True)

        self.assertEqual(stage["speed_percent"], 90)
        self.assertEqual(stage["pulse_seconds"], 0.5)

    def test_auto_preload_aborts_any_load_over_limit_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(1.6)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertIn("exceeded 1.5 lb at 1.6 lb", self.engine.state["auto_preload_message"])

    def test_auto_preload_aborts_large_overshoot_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(65.0)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertIn("exceeded 1.5 lb at 65.0 lb", self.engine.state["auto_preload_message"])

    def test_auto_preload_pulses_only_outside_safe_band(self):
        self.assertTrue(self.engine._auto_preload_direction_for_load(-0.1))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.0))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(1.0))
        self.assertFalse(self.engine._auto_preload_direction_for_load(1.1))

    def test_auto_preload_ease_down_uses_configured_pull_direction(self):
        self.engine.actuator.pull_direction = "up"
        self.engine._move_auto_preload_direction_locked(increase=False)
        self.assertEqual(self.engine.actuator.last_command, "down_fast")

    def test_start_rejects_load_cell_fault(self):
        self._set_load(0.5)
        self.engine.load_cell.last_error = "load cell test fault"
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("load cell test fault", message)

    def test_start_rejects_actuator_fault(self):
        self._set_load(0.5)
        self.engine.actuator.last_error = "actuator test fault"
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("actuator test fault", message)

    def test_start_succeeds_when_all_gates_pass(self):
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_start_rejects_angle_outside_allowed_range(self):
        storage.update_test(self.test_id, form={"angle_degrees": "101"})
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("80 and 100", message)

    def test_start_accepts_recorded_past_calibration_dates(self):
        storage.update_job(
            self.job_id,
            form={
                "load_cell_calibration_date": "2024-01-01",
                "ir_temp_gun_calibration_date": "2024-01-01",
            },
        )
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)

    def test_start_does_not_require_photo_reference(self):
        storage.update_test(self.test_id, form={"photo_reference": ""})
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)

    def test_start_does_not_require_removed_site_checkboxes(self):
        storage.update_test(
            self.test_id,
            form={
                "site_clear_of_hazards": "",
                "site_representative": "",
                "site_free_of_blemishes": "",
            },
        )
        self._set_load(0.5)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()
