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
        self.original_in_band_end = engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS
        self.original_contact_settle = engine_module.PRELOAD_AUTO_CONTACT_SETTLE_SECONDS
        self.original_contact_settle_max = engine_module.PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS
        self.original_approach_settle = engine_module.PRELOAD_AUTO_APPROACH_SETTLE_SECONDS
        self.original_approach_settle_max = engine_module.PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS
        self.original_approach_settle_delta = engine_module.PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS
        self.original_control_max_transient_rejects = engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS
        self.original_stop_during_load_read = engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ
        self.original_discard_settle = engine_module.PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS
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
        engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS = self.original_in_band_end
        engine_module.PRELOAD_AUTO_CONTACT_SETTLE_SECONDS = self.original_contact_settle
        engine_module.PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS = self.original_contact_settle_max
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_SECONDS = self.original_approach_settle
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS = self.original_approach_settle_max
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS = self.original_approach_settle_delta
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = self.original_control_max_transient_rejects
        engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ = self.original_stop_during_load_read
        engine_module.PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS = self.original_discard_settle
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
        for load in (engine_module.PRELOAD_MIN_LBS, 0.0, engine_module.PRELOAD_MAX_LBS):
            with self.subTest(load=load):
                self.engine.state["test_running"] = False
                self._set_load(load)
                ok, message = self.engine.start_pull(self.test_id)
                self.assertTrue(ok, message)
                self.assertTrue(self.engine.state["test_running"])

    def test_start_accepts_small_drift_after_auto_preload_ready_latch(self):
        self.engine._set_preload_ready_latch_locked(0.0)
        self._set_load(engine_module.PRELOAD_MIN_LBS - 0.05)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_start_rejects_drift_outside_ready_latch_margin(self):
        self.engine._set_preload_ready_latch_locked(0.0)
        self._set_load(engine_module.PRELOAD_MIN_LBS - engine_module.PRELOAD_READY_LATCH_MARGIN_LBS - 0.01)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertFalse(ok)
        self.assertIn("tension", message)

    def test_preload_ready_stays_latched_for_small_drift_after_auto_preload(self):
        self.engine._set_preload_ready_latch_locked(0.0)
        self.engine._set_load_state_locked(engine_module.PRELOAD_MIN_LBS - 0.05, 123.0)

        self.assertTrue(self.engine.state["preload_ready"])
        self.assertTrue(self.engine.state["preload_ready_latched"])

    def test_jog_clears_preload_ready_latch(self):
        self.engine._set_preload_ready_latch_locked(0.0)

        self.engine.jog("up")

        self.assertFalse(self.engine.state["preload_ready_latched"])

    def test_tare_rejects_while_auto_preload_running(self):
        self.engine.state["auto_preload_running"] = True
        ok, message = self.engine.tare()
        self.assertFalse(ok)
        self.assertIn("Auto Tension", message)

    def test_calibrate_rejects_while_auto_preload_running(self):
        self.engine.state["auto_preload_running"] = True
        ok, message = self.engine.calibrate_load_cell(10.0)
        self.assertFalse(ok)
        self.assertIn("Auto Tension", message)

    def test_stop_cancels_auto_preload(self):
        self.engine.state["auto_preload_running"] = True
        ok = self.engine.stop("operator stop")
        self.assertTrue(ok)
        self.assertTrue(self.engine.auto_preload_cancel_requested)
        self.assertEqual(self.engine.state["actuator_command"], "neutral")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "cancel_requested")

    def test_start_pull_clears_samples_when_restarting_test_record(self):
        storage.add_sample(self.test_id, 0.0, 10.0)
        storage.add_sample(self.test_id, 0.5, 12.0)
        storage.update_test(
            self.test_id,
            status="complete",
            started_at="2026-07-03T17:00:00Z",
            completed_at="2026-07-03T17:01:00Z",
            peak_load_lbs=12.0,
            stop_reason="previous run",
            sample_count=2,
        )

        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertEqual(storage.list_samples(self.test_id), [])
        test = storage.get_test(self.test_id)
        self.assertEqual(test["status"], "running")
        self.assertIsNone(test["completed_at"])
        self.assertEqual(test["sample_count"], 0)
        self.assertEqual(test["stop_reason"], "")

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
            self.assertGreaterEqual(earlier["speed_percent"], later["speed_percent"])
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
            (-2.75, 44, 0.09),
            (-2.25, 38, 0.07),
            (-1.75, 32, 0.055),
            (-1.25, 28, 0.045),
            (-0.9, 24, 0.032),
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

    def test_auto_preload_uses_approach_settle_before_final_zone(self):
        self.assertTrue(self.engine._auto_preload_stage_for_load(-0.8, True)["approach_settle"])
        self.assertFalse(self.engine._auto_preload_stage_for_load(engine_module.PRELOAD_MIN_LBS - 0.05, True)["approach_settle"])

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
            self.engine._auto_preload_stage_for_load(engine_module.PRELOAD_MIN_LBS + 0.01, True)["max_delta_lbs"],
            engine_module.PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
        )

    def test_auto_preload_continuous_speed_slows_near_target(self):
        far_speed = self.engine._auto_preload_continuous_speed_locked(-7.0, 0.0, True)
        mid_speed = self.engine._auto_preload_continuous_speed_locked(-3.0, 0.0, True)
        near_speed = self.engine._auto_preload_continuous_speed_locked(
            engine_module.PRELOAD_MIN_LBS - 0.05,
            0.0,
            True,
        )

        self.assertGreater(far_speed, mid_speed)
        self.assertGreater(mid_speed, near_speed)
        self.assertGreaterEqual(near_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT)

    def test_auto_preload_continuous_speed_aims_for_internal_negative_target(self):
        at_target_speed = self.engine._auto_preload_continuous_speed_locked(
            engine_module.PRELOAD_AUTO_TARGET_LBS,
            0.0,
            True,
        )

        self.assertEqual(at_target_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT)

    def test_auto_preload_continuous_speed_damps_fast_rise(self):
        slow_rise_speed = self.engine._auto_preload_continuous_speed_locked(-5.0, 0.0, True)
        fast_rise_speed = self.engine._auto_preload_continuous_speed_locked(-5.0, 1.0, True)

        self.assertLess(fast_rise_speed, slow_rise_speed)

    def test_auto_preload_continuous_speed_ramp_limits_step_change(self):
        ramped = self.engine._auto_preload_slew_speed(10.0, 50.0, 0.1)

        self.assertAlmostEqual(
            ramped,
            10.0 + (engine_module.PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND * 0.1),
        )

    def test_auto_preload_continuous_brakes_when_prediction_reaches_band(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_TARGET_LBS - 0.2,
            0.0,
            engine_module.PRELOAD_AUTO_TARGET_LBS + 0.01,
        )

        self.assertTrue(should_brake)
        self.assertTrue(self.engine.auto_preload_near_band_seen)

    def test_auto_preload_continuous_does_not_wait_for_zero_to_brake(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_TARGET_LBS - 0.05,
            0.0,
            engine_module.PRELOAD_AUTO_TARGET_LBS,
        )

        self.assertTrue(should_brake)

    def test_preload_hold_trim_increases_only_in_lower_half_while_dropping(self):
        self.engine.state["current_load"] = -0.2
        self._set_load_history([
            (0.50, -0.12),
            (0.25, -0.16),
            (0.00, -0.20),
        ])

        self.engine._preload_hold_update_locked()

        self.assertEqual(self.engine.preload_hold_trim_us, 1)
        self.assertEqual(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US + 1)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "hold_trim")

    def test_preload_hold_trim_does_not_increase_below_allowed_band(self):
        self.engine.preload_hold_trim_us = 3
        self.engine.state["current_load"] = engine_module.PRELOAD_MIN_LBS - 0.01

        self.engine._preload_hold_update_locked()

        self.assertEqual(self.engine.preload_hold_trim_us, 0)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "hold_out_of_band")

    def test_preload_hold_trim_moves_back_to_neutral_at_or_above_zero(self):
        self.engine.preload_hold_trim_us = 3
        self.engine.state["current_load"] = 0.0
        self._set_load_history([
            (0.50, -0.02),
            (0.25, -0.01),
            (0.00, 0.00),
        ])

        self.engine._preload_hold_update_locked()

        self.assertEqual(self.engine.preload_hold_trim_us, 2)
        self.assertEqual(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US + 2)

    def test_auto_preload_contact_detection_keeps_coarse_stage_far_from_target(self):
        normal = self.engine._auto_preload_stage_for_load(-6.0, True)
        self.engine.auto_preload_contact_detected = True

        contact = self.engine._auto_preload_stage_for_load(-6.0, True)

        self.assertTrue(normal["coarse"])
        self.assertTrue(contact["coarse"])
        self.assertTrue(contact["contact_coarse"])
        self.assertLess(contact["speed_percent"], normal["speed_percent"])
        self.assertLess(contact["pulse_seconds"], normal["pulse_seconds"])
        self.assertEqual(contact["max_delta_lbs"], engine_module.PRELOAD_AUTO_CONTACT_COARSE_MAX_DELTA_LBS)

    def test_auto_preload_contact_mode_tightens_stage_near_target(self):
        normal = self.engine._auto_preload_stage_for_load(-2.0, True)
        self.engine.auto_preload_contact_detected = True

        contact = self.engine._auto_preload_stage_for_load(-2.0, True)

        self.assertFalse(contact["coarse"])
        self.assertTrue(contact["contact"])
        self.assertLessEqual(contact["speed_percent"], normal["speed_percent"])
        self.assertLessEqual(contact["pulse_seconds"], normal["pulse_seconds"])
        self.assertEqual(contact["max_delta_lbs"], engine_module.PRELOAD_AUTO_CONTACT_MAX_DELTA_LBS)

    def test_auto_preload_contact_settle_does_not_wait_for_final_stability(self):
        engine_module.PRELOAD_AUTO_CONTACT_SETTLE_SECONDS = 0.01
        engine_module.PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS = 0.03
        self._set_load_history([
            (0.10, -7.0),
            (0.05, -6.9),
            (0.00, -6.8),
        ])

        started = time.monotonic()
        self.engine._wait_for_auto_preload_settle(
            time.monotonic() + 1.0,
            fast_contact=True,
        )

        self.assertLess(time.monotonic() - started, 0.2)
        self.assertTrue(self.engine.auto_preload_trace[-1]["fast_contact"])

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

    def test_auto_preload_approach_settle_uses_short_tight_band(self):
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_SECONDS = 0.01
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS = 0.2
        engine_module.PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS = 0.05
        self._set_load_history([
            (0.015, -0.72),
            (0.010, -0.70),
            (0.000, -0.69),
        ])

        started = time.monotonic()
        self.engine._wait_for_auto_preload_settle(time.monotonic() + 1.0, approach=True)

        self.assertLess(time.monotonic() - started, 0.2)
        self.assertTrue(self.engine.auto_preload_trace[-1]["approach"])

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

    def test_auto_preload_finishes_after_short_in_band_dwell(self):
        engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS = 0.01
        self.engine.state["auto_preload_running"] = True
        self._set_load(0.0)

        self.engine._auto_preload_loop()

        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertIn("in_band_complete", [entry["event"] for entry in self.engine.auto_preload_trace])
        self.assertNotEqual(self.engine.state["auto_preload_message"], "Check tension")

    def test_auto_preload_pulses_only_outside_safe_band(self):
        self.assertTrue(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MIN_LBS - 0.1))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MIN_LBS))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(-0.1))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(0.0))
        self.assertIsNone(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MAX_LBS))
        self.assertFalse(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MAX_LBS + 0.1))

    def test_auto_preload_holds_near_band_after_target_seen(self):
        self.engine.auto_preload_near_band_seen = True

        self.assertIsNone(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MIN_LBS - 0.02))
        self.assertTrue(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MIN_LBS - 0.04))

    def test_auto_preload_marks_near_band_after_predicted_stop(self):
        self.engine.state["current_load"] = -0.6
        self._set_load_history([
            (0.60, -1.2),
            (0.30, -0.9),
            (0.00, -0.6),
        ])
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(0.2), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertTrue(self.engine.auto_preload_near_band_seen)
        self.assertIsNone(self.engine._auto_preload_direction_for_load(engine_module.PRELOAD_MIN_LBS - 0.02))

    def test_auto_preload_ignores_sudden_low_drop_after_near_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.auto_preload_near_band_seen = True
        current_load = engine_module.PRELOAD_MIN_LBS - 0.02
        dropped_load = engine_module.PRELOAD_MIN_LBS - 0.07
        self.engine.state["current_load"] = current_load
        readings = iter([dropped_load, dropped_load - 0.01, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, current_load)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_drop_ignored_after_near_band")

    def test_auto_preload_pulse_stops_when_max_reached(self):
        self.engine.state["current_load"] = engine_module.PRELOAD_MAX_LBS + 0.01
        self.engine.actuator.move_up(fast=True, speed_percent=80)

        keep_running = self.engine._run_auto_preload_pulse(True, self._pulse_stage(), time.monotonic() + 1.0)

        self.assertTrue(keep_running)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_above_band")

    def test_auto_preload_pulse_stops_when_allowed_band_is_reached(self):
        self.engine.state["current_load"] = engine_module.PRELOAD_MIN_LBS + 0.01
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

    def test_auto_preload_confirms_stable_positive_jump(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.0
        readings = iter([-5.0, -5.1, -5.0, -5.05, -5.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertAlmostEqual(load, -5.0)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")

    def test_auto_preload_confirms_stable_negative_jump(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -1.0
        readings = iter([-3.0, -3.1, -3.0, -3.05, -3.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertAlmostEqual(load, -3.0)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")

    def test_auto_preload_rejects_inconsistent_hard_spike_after_retry(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = 0
        self.engine.state["current_load"] = -7.85
        readings = iter([415.0, -7.8, 220.0, -7.9, 42.0, 415.0, -7.8, 220.0, -7.9, 42.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -7.85)
        self.assertTrue(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_rejected")

    def test_display_load_smooths_without_changing_current_load(self):
        self.engine.state["display_load"] = 0.0
        self.engine._set_load_state_locked(1.0, 123.0)

        self.assertEqual(self.engine.state["current_load"], 1.0)
        self.assertGreater(self.engine.state["display_load"], 0.0)
        self.assertLess(self.engine.state["display_load"], 1.0)

    def test_display_load_snaps_on_large_change(self):
        self.engine.state["display_load"] = 0.0
        self.engine._set_load_state_locked(-7.4, 123.0)

        self.assertEqual(self.engine.state["current_load"], -7.4)
        self.assertEqual(self.engine.state["display_load"], -7.4)

    def test_auto_preload_discards_transient_inconsistent_control_burst(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = 2
        self.engine.state["current_load"] = -3.381
        readings = iter([14.793, -2.828, 14.793, -2.9, 10.0, 14.793, -2.828, 14.793, -2.9, 10.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -3.381)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_discarded")
        self.assertEqual(self.engine.auto_preload_control_rejects, 1)

    def test_auto_preload_stops_actuator_during_suspicious_control_confirmation(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0, -7.82, -7.88, -7.83, -7.86, -7.84, -7.85, -7.83, -7.86, -7.84])
        self.engine.load_cell.get_control_force = lambda: next(readings)
        self.engine.actuator.move_up(fast=True, speed_percent=45)

        load = self.engine._refresh_auto_preload_load()

        self.assertAlmostEqual(load, -7.84)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertIn("control_read_stop", [entry["event"] for entry in self.engine.auto_preload_trace])

    def test_auto_preload_holds_neutral_after_discarded_control_burst(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ = True
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = 2
        engine_module.PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS = 0.35
        self.engine.state["current_load"] = -3.381
        readings = iter([14.793, -2.828, 14.793, -2.9, 10.0, 14.793, -2.828, 14.793, -2.9, 10.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)
        self.engine.actuator.move_up(fast=True, speed_percent=45)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -3.381)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertGreater(self.engine.auto_preload_control_hold_until, time.monotonic())
        self.assertEqual(self.engine.state["auto_preload_message"], "Settling")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_discarded")

    def test_auto_preload_ignores_inconsistent_spike_after_reaching_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -0.077
        readings = iter([415.0, -0.05, 220.0, -0.07, 42.0, 415.0, -0.04, 220.0, -0.08, 42.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -0.077)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_spike_ignored_in_band")

    def test_auto_preload_accepts_lower_reading_when_recovering_from_above_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.auto_preload_near_band_seen = True
        self.engine.state["current_load"] = 0.795
        readings = iter([-3.869, -5.9, -5.8, -5.7, -5.6])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertLess(load, engine_module.PRELOAD_MIN_LBS)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")

    def test_auto_preload_pulse_stops_on_inconsistent_sensor_spike(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = 0
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

    def test_auto_preload_waits_when_prediction_reaches_band(self):
        self.engine.state["current_load"] = -0.6
        self._set_load_history([
            (0.60, -1.2),
            (0.30, -0.9),
            (0.00, -0.6),
        ])

        should_wait = self.engine._auto_preload_should_wait_for_settle_locked(-0.6, True)

        self.assertTrue(should_wait)
        self.assertTrue(self.engine.auto_preload_near_band_seen)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "predicted_settle_hold")
        self.assertGreaterEqual(self.engine.auto_preload_trace[-1]["predicted_load"], engine_module.PRELOAD_MIN_LBS)

    def test_auto_preload_does_not_wait_when_prediction_stays_below_band(self):
        self.engine.state["current_load"] = -1.3
        self._set_load_history([
            (0.60, -1.1),
            (0.30, -1.45),
            (0.00, -1.3),
        ])

        should_wait = self.engine._auto_preload_should_wait_for_settle_locked(-1.3, True)

        self.assertFalse(should_wait)
        self.assertFalse(self.engine.auto_preload_near_band_seen)
        self.assertEqual(len(self.engine.auto_preload_trace), 0)

    def test_auto_preload_waits_on_sudden_negative_jump_near_target(self):
        self.engine.state["current_load"] = -1.57
        self._set_load_history([
            (0.60, -0.66),
            (0.30, -0.63),
            (0.00, -1.57),
        ])

        should_wait = self.engine._auto_preload_should_wait_for_settle_locked(-1.57, True)

        self.assertTrue(should_wait)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "negative_jump_hold")
        self.assertGreaterEqual(self.engine.auto_preload_trace[-1]["drop_lbs"], 0.5)

    def test_auto_preload_allows_normal_below_band_reading(self):
        self.engine.state["current_load"] = -1.57
        self._set_load_history([
            (0.60, -1.72),
            (0.30, -1.63),
            (0.00, -1.57),
        ])

        should_wait = self.engine._auto_preload_should_wait_for_settle_locked(-1.57, True)

        self.assertFalse(should_wait)
        self.assertEqual(len(self.engine.auto_preload_trace), 0)

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
        self.assertTrue(self.engine.auto_preload_contact_detected)
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
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "pulse_stop_predicted")

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
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_start_pull_rejects_while_auto_preload_running(self):
        self._set_load(0.0)
        self.engine.state["auto_preload_running"] = True

        ok, message = self.engine.start_pull(self.test_id)

        self.assertFalse(ok)
        self.assertIn("Auto Tension", message)
        self.assertTrue(self.engine.state["auto_preload_running"])
        self.assertFalse(self.engine.state["test_running"])

    def test_auto_preload_rejects_while_pull_running(self):
        self.engine.state["test_running"] = True
        self.engine.state["active_test_id"] = self.test_id
        self.engine.state["auto_preload_running"] = False

        ok, message = self.engine.auto_preload()

        self.assertFalse(ok)
        self.assertIn("pull test", message)
        self.assertTrue(self.engine.state["test_running"])
        self.assertEqual(self.engine.state["active_test_id"], self.test_id)
        self.assertFalse(self.engine.state["auto_preload_running"])

    def test_start_pull_clears_finished_auto_preload_state(self):
        self._set_load(0.0)
        self.engine.state["auto_preload_message"] = "Check tension"
        self.engine.state["auto_preload_sensor_fault"] = True
        self.engine.state["auto_preload_short_stable"] = True
        self.engine.state["auto_preload_drift_stable"] = True
        self.engine.auto_preload_contact_detected = True

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])
        self.assertEqual(self.engine.state["auto_preload_message"], "")
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertFalse(self.engine.state["auto_preload_short_stable"])
        self.assertFalse(self.engine.state["auto_preload_drift_stable"])
        self.assertFalse(self.engine.auto_preload_contact_detected)

    def test_start_pull_ignores_jog_speed_slider(self):
        self.engine.actuator.pull_direction = "up"
        self.engine.state["jog_speed_percent"] = 1
        self.engine.jog("up")
        jog_pulse = self.engine.actuator.last_pulse_us
        self._set_load(-0.10)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertNotEqual(self.engine.actuator.last_pulse_us, jog_pulse)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.actuator.last_pulse_us, self.engine.actuator._mirror(VICTOR_PULL_US))
        self.assertEqual(self.engine.state["jog_speed_percent"], 1)

    def test_start_pull_cancels_preload_hold_trim(self):
        self.engine.preload_hold_active = True
        self.engine.preload_hold_trim_us = 5
        self.engine.actuator.set_pulse_us(engine_module.VICTOR_NEUTRAL_US + 5, command="hold_trim")
        self._set_load(0.0)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.preload_hold_trim_us, 0)
        self.assertIn(self.engine.actuator.last_command, {"up_pull", "down_pull"})

    def test_start_rejects_angle_outside_allowed_range(self):
        storage.update_test(self.test_id, form={"angle_degrees": "101"})
        self._set_load(0.0)
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
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)

    def test_start_does_not_require_photo_reference(self):
        storage.update_test(self.test_id, form={"photo_reference": ""})
        self._set_load(0.0)
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
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()
