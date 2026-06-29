import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage
import engine as engine_module
from engine import QuadpodEngine
from config import VICTOR_PULL_US


class ControlGateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()
        self.engine = QuadpodEngine(use_mock=True)
        self.original_drift_window = engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = 5.0
        self.job_id = storage.create_job(self._job_form())
        self.test_id = storage.create_test(self.job_id, self._test_form())

    def tearDown(self):
        self.engine.stop("test cleanup")
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = self.original_drift_window
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
        self._set_load(0.6)
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

    def test_auto_preload_early_stages_are_modestly_faster(self):
        expected = [
            (-8.0, 95, 0.60),
            (-4.75, 78, 0.26),
            (-4.25, 70, 0.21),
            (-3.75, 62, 0.17),
            (-3.25, 54, 0.13),
        ]

        for load, speed, pulse in expected:
            stage = self.engine._auto_preload_stage_for_load(load, True)
            self.assertEqual(stage["speed_percent"], speed)
            self.assertEqual(stage["pulse_seconds"], pulse)

    def test_auto_preload_final_targeting_stages_remain_slow(self):
        expected = [
            (-2.75, 40, 0.08),
            (-2.25, 34, 0.06),
            (-1.75, 28, 0.045),
            (-1.25, 24, 0.035),
            (-0.9, 20, 0.025),
            (-0.7, 17, 0.018),
            (-0.5, 14, 0.014),
            (-0.3, 12, 0.010),
        ]

        for load, speed, pulse in expected:
            stage = self.engine._auto_preload_stage_for_load(load, True)
            self.assertEqual(stage["speed_percent"], speed)
            self.assertEqual(stage["pulse_seconds"], pulse)

    def test_auto_preload_aborts_any_load_over_limit_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(1.1)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertIn("exceeded 1.0 lb at 1.1 lb", self.engine.state["auto_preload_message"])

    def test_auto_preload_aborts_large_overshoot_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(65.0)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertIn("exceeded 1.0 lb at 65.0 lb", self.engine.state["auto_preload_message"])

    def test_auto_preload_pulses_only_outside_safe_band(self):
        self.assertTrue(self.engine._auto_preload_direction_for_load(-0.1))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.0))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.5))
        self.assertFalse(self.engine._auto_preload_direction_for_load(0.6))

    def _set_load_history(self, samples):
        now = time.monotonic()
        self.engine.load_history.clear()
        for seconds_ago, value in samples:
            self.engine.load_history.append((now - seconds_ago, value))

    def test_auto_preload_ready_blocks_long_downward_drift(self):
        self._set_load_history([
            (4.9, 0.45),
            (4.0, 0.40),
            (3.0, 0.23),
            (2.0, 0.22),
            (1.0, 0.21),
            (0.0, 0.20),
        ])

        self.assertFalse(self.engine._auto_preload_ready_locked())
        self.assertTrue(self.engine.state["auto_preload_short_stable"])
        self.assertFalse(self.engine.state["auto_preload_drift_stable"])
        self.assertGreater(self.engine.state["auto_preload_drift_drop_lbs"], 0.15)

    def test_auto_preload_ready_allows_settled_long_window(self):
        self._set_load_history([
            (4.9, 0.30),
            (4.0, 0.29),
            (3.0, 0.27),
            (2.0, 0.24),
            (1.0, 0.22),
            (0.0, 0.21),
        ])

        self.assertTrue(self.engine._auto_preload_ready_locked())
        self.assertTrue(self.engine.state["auto_preload_short_stable"])
        self.assertTrue(self.engine.state["auto_preload_drift_stable"])
        self.assertLessEqual(self.engine.state["auto_preload_drift_drop_lbs"], 0.15)

    def test_auto_preload_ready_requires_full_drift_window(self):
        self._set_load_history([
            (4.0, 0.30),
            (2.0, 0.29),
            (0.0, 0.28),
        ])

        self.assertFalse(self.engine._auto_preload_ready_locked())
        self.assertFalse(self.engine.state["auto_preload_drift_stable"])

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


    def test_start_pull_ignores_jog_speed_slider(self):
        self.engine.actuator.pull_direction = "up"
        self.engine.state["jog_speed_percent"] = 1
        self.engine.jog("up")
        jog_pulse = self.engine.actuator.last_pulse_us
        self._set_load(0.25)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertNotEqual(self.engine.actuator.last_pulse_us, jog_pulse)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.actuator.last_pulse_us, self.engine.actuator._mirror(VICTOR_PULL_US))
        self.assertEqual(self.engine.state["jog_speed_percent"], 1)

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
