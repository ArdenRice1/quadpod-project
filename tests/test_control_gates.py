import sys
import tempfile
import threading
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
        self.original_coarse_settle = engine_module.PRELOAD_AUTO_COARSE_SETTLE_SECONDS
        self.original_coarse_settle_max = engine_module.PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS
        self.original_direct_load_read = engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = 5.0
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = False
        self.job_id = storage.create_job(self._job_form())
        self.test_id = storage.create_test(self.job_id, self._test_form())

    def tearDown(self):
        self.engine.stop("test cleanup")
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = self.original_drift_window
        engine_module.PRELOAD_AUTO_COARSE_SETTLE_SECONDS = self.original_coarse_settle
        engine_module.PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS = self.original_coarse_settle_max
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = self.original_direct_load_read
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

    def _pulse_stage(self, pulse_seconds=0.2, max_delta_lbs=0.0):
        return {
            "coarse": False,
            "pulse_seconds": pulse_seconds,
            "max_delta_lbs": max_delta_lbs,
            "speed_percent": 80,
        }

    def test_start_rejects_low_preload(self):
        self._set_load(-0.6)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("tension", message)

    def test_start_rejects_high_preload(self):
        self._set_load(0.6)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("tension", message)

    def test_start_accepts_preload_inside_tight_band(self):
        for load in (-0.5, 0.0, 0.5):
            with self.subTest(load=load):
                self.engine.state["test_running"] = False
                self._set_load(load)
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
            (-8.0, 80, 0.25),
            (-4.75, 68, 0.18),
            (-4.25, 60, 0.14),
            (-3.75, 52, 0.11),
            (-3.25, 44, 0.09),
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

    def test_auto_preload_marks_only_far_from_target_stages_as_coarse(self):
        self.assertTrue(self.engine._auto_preload_stage_for_load(-4.75, True)["coarse"])
        self.assertTrue(self.engine._auto_preload_stage_for_load(-3.25, True)["coarse"])
        self.assertFalse(self.engine._auto_preload_stage_for_load(-2.75, True)["coarse"])
        self.assertFalse(self.engine._auto_preload_stage_for_load(-0.3, True)["coarse"])

    def test_auto_preload_stage_limits_load_delta_by_zone(self):
        self.assertEqual(
            self.engine._auto_preload_stage_for_load(-4.75, True)["max_delta_lbs"],
            engine_module.PRELOAD_AUTO_COARSE_MAX_DELTA_LBS,
        )
        self.assertEqual(
            self.engine._auto_preload_stage_for_load(-2.75, True)["max_delta_lbs"],
            engine_module.PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS,
        )
        self.assertEqual(
            self.engine._auto_preload_stage_for_load(-0.3, True)["max_delta_lbs"],
            engine_module.PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
        )

    def test_auto_preload_coarse_settle_does_not_wait_for_final_stability(self):
        engine_module.PRELOAD_AUTO_COARSE_SETTLE_SECONDS = 0.01
        engine_module.PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS = 0.03
        self._set_load_history([
            (0.10, -6.0),
            (0.05, -5.0),
            (0.00, -4.0),
        ])

        started = time.monotonic()
        self.engine._wait_for_auto_preload_settle(time.monotonic() + 1.0, coarse=True)

        self.assertLess(time.monotonic() - started, 0.2)

    def test_auto_preload_aborts_any_load_over_limit_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(1.1)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-2]["event"], "abort")

    def test_auto_preload_aborts_large_overshoot_without_easing_down(self):
        self.engine.state["auto_preload_running"] = True
        self._set_load(65.0)
        self.engine._auto_preload_loop()
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-2]["event"], "abort")

    def test_auto_preload_pulses_only_outside_safe_band(self):
        self.assertTrue(self.engine._auto_preload_direction_for_load(-0.6))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(-0.5))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(-0.1))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.0))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.5))
        self.assertFalse(self.engine._auto_preload_direction_for_load(0.6))

    def test_auto_preload_pulse_stops_when_max_reached(self):
        self.engine.state["current_load"] = 0.51
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_above_band")

    def test_auto_preload_pulse_stops_when_allowed_band_is_reached(self):
        self.engine.state["current_load"] = -0.4
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_allowed_band")

    def test_auto_preload_pulse_aborts_if_load_exceeds_limit(self):
        self.engine.state["current_load"] = 1.1
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertFalse(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_abort")

    def test_auto_preload_pulse_uses_fresh_control_load(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -4.0
        readings = iter([1.2, 1.25, 1.22, 1.21, 1.24])
        self.engine.load_cell.get_control_force = lambda: next(readings)
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertFalse(keep_running)
        self.assertEqual(self.engine.state["current_load"], 1.22)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_abort")

    def test_auto_preload_reads_control_load_once_after_pulse(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -1.1
        calls = []

        def read_control_load():
            calls.append(time.monotonic())
            return -1.0

        self.engine.load_cell.get_control_force = read_control_load
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(0.05), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_complete")

    def test_auto_preload_confirms_and_rejects_single_control_spike(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0, -7.82, -7.88, -7.83, -7.86, -7.84, -7.85, -7.83, -7.86, -7.84])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertAlmostEqual(load, -7.84)
        self.assertAlmostEqual(self.engine.state["current_load"], -7.84)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")
        self.assertEqual(self.engine.auto_preload_trace[-1]["first_load"], 185.0)

    def test_auto_preload_confirms_real_high_control_load(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0, 180.0, 181.0, 182.0, 183.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, 182.0)
        self.assertEqual(self.engine.state["current_load"], 182.0)

    def test_auto_preload_rejects_inconsistent_hard_spike_after_retry(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([415.0, -7.8, 220.0, -7.9, 42.0, 415.0, -7.8, 220.0, -7.9, 42.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -7.85)
        self.assertTrue(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_rejected")

    def test_auto_preload_ignores_inconsistent_spike_after_reaching_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = 0.077
        readings = iter([415.0, 0.05, 220.0, 0.07, 42.0, 415.0, 0.04, 220.0, 0.08, 42.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, 0.077)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_spike_ignored_in_band")

    def test_auto_preload_pulse_stops_on_inconsistent_sensor_spike(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([415.0, -7.8, 220.0, -7.9, 42.0, 415.0, -7.8, 220.0, -7.9, 42.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertFalse(keep_running)
        self.assertTrue(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_sensor_fault")

    def test_auto_preload_pulse_stops_on_predicted_overshoot(self):
        self.engine.state["current_load"] = -0.6
        self._set_load_history([
            (0.60, -1.2),
            (0.30, -0.9),
            (0.00, -0.6),
        ])
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(0.2), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_predicted")

    def test_auto_preload_pulse_stops_after_large_load_change(self):
        self.engine.state["current_load"] = -8.0

        def update_load():
            time.sleep(0.03)
            self.engine.state["current_load"] = -7.4

        thread = threading.Thread(target=update_load)
        thread.start()
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(
            True,
            self._pulse_stage(0.2, max_delta_lbs=0.5),
            time.monotonic() + 1.0,
        )
        thread.join(timeout=1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_delta")

    def test_auto_preload_stops_when_force_rises_quickly_near_target(self):
        self.engine.state["current_load"] = -1.2
        self._set_load_history([
            (0.60, -1.8),
            (0.30, -1.5),
            (0.00, -1.2),
        ])
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(0.2), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_fast_rise")

    def test_auto_preload_adapts_stage_after_learning_coast(self):
        stage = self.engine._auto_preload_stage_for_load(-0.9, True)
        self.engine.auto_preload_coast_lbs = 0.3

        adjusted = self.engine._auto_preload_adjust_stage_for_slope_locked(stage, -0.9, True)

        self.assertTrue(adjusted["adapted"])
        self.assertLess(adjusted["pulse_seconds"], stage["pulse_seconds"])
        self.assertLess(adjusted["speed_percent"], stage["speed_percent"])
        self.assertEqual(adjusted["max_delta_lbs"], engine_module.PRELOAD_AUTO_FINAL_MAX_DELTA_LBS)

    def test_auto_preload_settle_learns_coast_after_stop(self):
        self.engine.auto_preload_last_stop_load = -0.9
        self.engine.auto_preload_last_stop_increase = True
        self.engine.state["current_load"] = -0.55

        coast = self.engine._update_auto_preload_coast_locked()

        self.assertAlmostEqual(coast, 0.35)
        self.assertAlmostEqual(self.engine.auto_preload_coast_lbs, 0.175)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "coast_measured")

    def test_auto_preload_trace_is_internal_and_bounded(self):
        for index in range(engine_module.PRELOAD_AUTO_TRACE_MAX_ENTRIES + 10):
            self.engine._record_auto_preload_trace_locked("sample", index=index, load=-0.1)

        self.assertEqual(len(self.engine.auto_preload_trace), engine_module.PRELOAD_AUTO_TRACE_MAX_ENTRIES)
        self.assertEqual(self.engine.auto_preload_trace[-1]["index"], engine_module.PRELOAD_AUTO_TRACE_MAX_ENTRIES + 9)
        self.assertNotIn("auto_preload_trace", self.engine.snapshot())

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
