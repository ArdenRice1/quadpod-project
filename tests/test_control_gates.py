import datetime as dt
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
from engine import QuadpodEngine, _calibration_date_error
from config import VICTOR_PULL_US

RECENT_CAL_DATE = (dt.date.today() - dt.timedelta(days=1)).isoformat()


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
        self.original_moving_control_samples = engine_module.PRELOAD_AUTO_MOVING_CONTROL_SAMPLES
        self.original_stop_jounce = engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS
        self.original_scan_verify = engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS
        self.original_timeout = engine_module.PRELOAD_AUTO_TIMEOUT_SECONDS
        self.original_continuous_poll = engine_module.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS
        self.original_plausibility_enabled = engine_module.PRELOAD_AUTO_PLAUSIBILITY_ENABLED
        self.original_plausibility_base = engine_module.PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS
        self.original_plausibility_rate = engine_module.PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100
        self.original_trace_dir = engine_module.PRELOAD_AUTO_TRACE_DIR
        self.original_hold_interval = engine_module.PRELOAD_HOLD_TRIM_INTERVAL_SECONDS
        self.original_glide_hold_settle = engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S
        self.original_glide_hold_timeout = engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = 5.0
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = False
        engine_module.PRELOAD_AUTO_TRACE_DIR = self.root / "auto_tension_traces"
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
        engine_module.PRELOAD_AUTO_MOVING_CONTROL_SAMPLES = self.original_moving_control_samples
        engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS = self.original_stop_jounce
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = self.original_scan_verify
        engine_module.PRELOAD_AUTO_TIMEOUT_SECONDS = self.original_timeout
        engine_module.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS = self.original_continuous_poll
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_ENABLED = self.original_plausibility_enabled
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS = self.original_plausibility_base
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100 = self.original_plausibility_rate
        engine_module.PRELOAD_AUTO_TRACE_DIR = self.original_trace_dir
        engine_module.PRELOAD_HOLD_TRIM_INTERVAL_SECONDS = self.original_hold_interval
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = self.original_glide_hold_settle
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = self.original_glide_hold_timeout
        self.tempdir.cleanup()

    def _job_form(self, **updates):
        form = {
            "project_name": "Gate Job",
            "job_number": "G-001",
            "load_cell_id": "LC-1",
            "load_cell_calibration_date": RECENT_CAL_DATE,
            "ir_temp_gun_id": "IR-1",
            "ir_temp_gun_calibration_date": RECENT_CAL_DATE,
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

    def test_start_accepts_small_positive_recovery_within_ready_latch_margin(self):
        # A little load-cell noise above the band ceiling is tolerated.
        self.engine._set_preload_ready_latch_locked(0.0)
        self._set_load(0.1)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_start_rejects_large_positive_pretension_after_ready_latch(self):
        # A pull must not begin on a pre-tensioned specimen -- it biases the peak.
        self.engine._set_preload_ready_latch_locked(0.0)
        self._set_load(0.8)

        ok, message = self.engine.start_pull(self.test_id)

        self.assertFalse(ok)
        self.assertIn("tension", message)

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

    # --- Safety envelope: _stop_reason_locked (auto-stop triggers during a pull) ---

    def _prime_pull(self, peak):
        """State of a healthy running pull: connected, no fault, below limits."""
        self.engine.last_client_poll = time.monotonic()
        self.engine.load_cell.last_error = ""
        self.engine.failure_drop_samples = 0
        self.engine.state["peak_load"] = peak

    def _failure_drop_load(self, peak):
        """A load low enough to count as a failure drop from `peak`."""
        required = max(engine_module.FAILURE_DROP_LBS, peak * engine_module.FAILURE_DROP_PERCENT)
        return peak - required - 1.0

    def test_stop_reason_phone_disconnect(self):
        self._prime_pull(peak=5.0)
        self.engine.last_client_poll = time.monotonic() - (engine_module.DISCONNECT_STOP_SECONDS + 1)
        self.assertEqual(self.engine._stop_reason_locked(5.0, 1.0), "phone/app disconnected")

    def test_stop_reason_load_cell_fault(self):
        self._prime_pull(peak=5.0)
        self.engine.load_cell.last_error = "HX711 read timeout"
        self.assertEqual(self.engine._stop_reason_locked(5.0, 1.0), "load cell fault")

    def test_stop_reason_max_force(self):
        self._prime_pull(peak=engine_module.MAX_FORCE_LBS)
        self.assertEqual(self.engine._stop_reason_locked(10.0, 1.0), "maximum force limit")

    def test_stop_reason_max_time(self):
        self._prime_pull(peak=5.0)
        self.assertEqual(
            self.engine._stop_reason_locked(5.0, engine_module.MAX_TEST_SECONDS),
            "maximum run time/end of travel timeout",
        )

    def test_stop_reason_none_when_healthy(self):
        self._prime_pull(peak=5.0)  # peak below FAILURE_MIN_PEAK_LBS
        self.assertEqual(self.engine._stop_reason_locked(5.0, 1.0), "")

    def test_stop_reason_failure_drop_requires_confirm_samples(self):
        peak = engine_module.FAILURE_MIN_PEAK_LBS + 30.0
        self._prime_pull(peak=peak)
        dropped = self._failure_drop_load(peak)
        confirm = max(1, engine_module.FAILURE_CONFIRM_SAMPLES)
        for _ in range(confirm - 1):
            self.assertEqual(self.engine._stop_reason_locked(dropped, 1.0), "")
        self.assertEqual(self.engine._stop_reason_locked(dropped, 1.0), "confirmed load drop/failure")

    def test_stop_reason_failure_drop_resets_on_recovery(self):
        peak = engine_module.FAILURE_MIN_PEAK_LBS + 30.0
        self._prime_pull(peak=peak)
        dropped = self._failure_drop_load(peak)
        self.engine._stop_reason_locked(dropped, 1.0)
        self.assertEqual(self.engine.failure_drop_samples, 1)
        self.engine._stop_reason_locked(peak, 1.0)  # load recovered -> debounce resets
        self.assertEqual(self.engine.failure_drop_samples, 0)

    def test_stop_reason_ignores_small_drop_and_low_peak(self):
        # A small drop below a high peak never confirms...
        peak = engine_module.FAILURE_MIN_PEAK_LBS + 30.0
        self._prime_pull(peak=peak)
        for _ in range(engine_module.FAILURE_CONFIRM_SAMPLES + 2):
            self.assertEqual(self.engine._stop_reason_locked(peak - 1.0, 1.0), "")
        # ...and a big drop below FAILURE_MIN_PEAK_LBS is ignored (grip/seat noise).
        self._prime_pull(peak=engine_module.FAILURE_MIN_PEAK_LBS - 1.0)
        for _ in range(engine_module.FAILURE_CONFIRM_SAMPLES + 2):
            self.assertEqual(self.engine._stop_reason_locked(0.0, 1.0), "")

    # --- Glide post-tension hold (the shipping seating controller) ---

    def test_glide_hold_aborts_and_clears_ready_on_over_tension(self):
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = 0.0
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = 5.0
        self.engine._set_preload_ready_latch_locked(0.0)
        self.assertTrue(self.engine.state["preload_ready_latched"])
        # Load sits above the over-tension abort (default 1.0 lb).
        self.engine.state["current_load"] = engine_module.PRELOAD_GLIDE_HOLD_ABORT_LBS + 0.5
        self.engine.preload_hold_active = True

        self.engine._glide_hold_loop(self.engine.actuator_epoch)

        self.assertFalse(self.engine.state["preload_ready_latched"])
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")
        self.assertFalse(self.engine.preload_hold_active)
        events = [e["event"] for e in self.engine.auto_preload_trace]
        self.assertIn("hold_abort_high", events)

    def test_glide_hold_settles_in_aim_without_pulsing(self):
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = 0.0
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = 5.0
        # Load already inside the aim band -> no correction pulse should fire.
        mid = (engine_module.PRELOAD_GLIDE_HOLD_AIM_LO_LBS + engine_module.PRELOAD_GLIDE_HOLD_AIM_HI_LBS) / 2
        self.engine.state["current_load"] = mid
        self.engine.preload_hold_active = True

        self.engine._glide_hold_loop(self.engine.actuator_epoch)

        events = [e["event"] for e in self.engine.auto_preload_trace]
        self.assertIn("hold_in_aim", events)
        self.assertNotIn("hold_pulse", events)
        self.assertFalse(self.engine.preload_hold_active)

    def test_jog_clears_preload_ready_latch(self):
        self.engine._set_preload_ready_latch_locked(0.0)

        self.engine.jog("up")

        self.assertFalse(self.engine.state["preload_ready_latched"])

    def test_jog_stop_does_not_cancel_preload_hold(self):
        self.engine.preload_hold_active = True
        self.engine.preload_hold_trim_us = 3
        self.engine.actuator.set_pulse_us(engine_module.VICTOR_NEUTRAL_US - 3, command="hold_trim")

        ok, message = self.engine.jog("stop")

        self.assertTrue(ok, message)
        self.assertTrue(self.engine.preload_hold_active)
        self.assertEqual(self.engine.preload_hold_trim_us, 3)
        self.assertEqual(self.engine.actuator.last_command, "hold_trim")

    def test_jog_up_cancels_preload_hold(self):
        self.engine.preload_hold_active = True
        self.engine.preload_hold_trim_us = 3

        ok, message = self.engine.jog("up")

        self.assertTrue(ok, message)
        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.preload_hold_trim_us, 0)

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
        self.assertLess(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US)
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
        self.assertGreaterEqual(near_speed, 0.0)
        self.assertLessEqual(near_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT)

    def test_auto_preload_continuous_final_pull_uses_configured_floor(self):
        speed = self.engine._auto_preload_continuous_speed_locked(-0.8, 0.0, True)

        self.assertEqual(speed, engine_module.PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT)

    def test_auto_preload_continuous_speed_aims_for_internal_negative_target(self):
        self.engine.auto_preload_initial_stop_seen = True
        self.engine.auto_preload_final_approach_stop_seen = True
        at_target_speed = self.engine._auto_preload_continuous_speed_locked(
            engine_module.PRELOAD_AUTO_TARGET_LBS,
            0.0,
            True,
        )

        self.assertEqual(at_target_speed, 0.0)

    def test_auto_preload_continuous_crawl_zone_can_stop_instead_of_forcing_minimum(self):
        self.engine.auto_preload_initial_stop_seen = True
        self.engine.auto_preload_final_approach_stop_seen = True

        speed = self.engine._auto_preload_continuous_speed_locked(
            engine_module.PRELOAD_MIN_LBS - 0.01,
            0.0,
            True,
        )

        self.assertEqual(speed, 0.0)

    def test_auto_preload_continuous_speed_damps_fast_rise(self):
        slow_rise_speed = self.engine._auto_preload_continuous_speed_locked(-6.5, 0.0, True)
        fast_rise_speed = self.engine._auto_preload_continuous_speed_locked(-6.5, 1.0, True)

        self.assertLess(fast_rise_speed, slow_rise_speed)

    def test_auto_preload_continuous_speed_is_sensor_paced_near_contact(self):
        early_speed = self.engine._auto_preload_continuous_speed_locked(-5.7, 0.0, True)
        start_speed = self.engine._auto_preload_continuous_speed_locked(-4.7, 0.0, True)
        mid_speed = self.engine._auto_preload_continuous_speed_locked(-3.5, 0.0, True)
        approach_speed = self.engine._auto_preload_continuous_speed_locked(-2.8, 0.0, True)
        final_speed = self.engine._auto_preload_continuous_speed_locked(-2.0, 0.0, True)
        fine_speed = self.engine._auto_preload_continuous_speed_locked(-1.2, 0.0, True)
        final_floor_speed = self.engine._auto_preload_continuous_speed_locked(-0.8, 0.0, True)

        self.assertLessEqual(early_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT)
        self.assertLessEqual(start_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT)
        self.assertLessEqual(mid_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT)
        self.assertLessEqual(approach_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT)
        self.assertLessEqual(final_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT)
        self.assertLessEqual(fine_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT)
        self.assertEqual(final_floor_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT)

    def test_auto_preload_progressive_cap_slows_smoothly(self):
        caps = [
            self.engine._auto_preload_progressive_max_speed_locked(load, 0.0)
            for load in [-7.0, -6.5, -6.0, -5.5, -5.0, -4.5, -4.0, -3.0, -2.5, -1.5, -1.0]
        ]

        self.assertEqual(caps, sorted(caps, reverse=True))
        self.assertGreater(caps[0], caps[-1])

    def test_auto_preload_slew_can_be_clamped_to_sensor_paced_cap(self):
        slewed = self.engine._auto_preload_slew_speed(30.0, 9.0, 0.1)
        clamped = min(slewed, self.engine._auto_preload_progressive_max_speed_locked(-4.7, 0.0))

        self.assertLessEqual(clamped, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT)

    def test_auto_preload_no_progress_allows_final_speed_boost(self):
        self.assertTrue(self.engine._auto_preload_no_progress_locked(-1.3, 0.0))

        boosted_speed = self.engine._auto_preload_continuous_speed_locked(
            -1.3,
            0.0,
            True,
            max_speed_override=engine_module.PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT,
        )

        self.assertGreater(boosted_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT)
        self.assertLessEqual(boosted_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT)

    def test_auto_preload_no_progress_boost_sets_speed_floor_near_stall(self):
        self.engine.auto_preload_initial_stop_seen = True
        self.engine.auto_preload_final_approach_stop_seen = True

        normal_speed = self.engine._auto_preload_continuous_speed_locked(-0.8, 0.0, True)
        floor_speed = self.engine._auto_preload_no_progress_floor_speed_locked(-0.8)
        boosted_speed = self.engine._auto_preload_continuous_speed_locked(
            -0.8,
            0.0,
            True,
            max_speed_override=floor_speed,
            min_speed_override=floor_speed,
        )

        self.assertEqual(normal_speed, floor_speed)
        self.assertEqual(boosted_speed, floor_speed)
        self.assertLess(boosted_speed, engine_module.PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT)

    def test_auto_preload_no_progress_does_not_boost_final_creep(self):
        self.assertFalse(self.engine._auto_preload_no_progress_locked(-0.4, 0.0))

    def test_auto_preload_no_progress_does_not_apply_to_fast_rise(self):
        self.assertFalse(self.engine._auto_preload_no_progress_locked(-1.3, 0.5))

    def test_auto_preload_rate_uses_robust_recent_rise(self):
        self._set_load_history([
            (0.70, -4.864),
            (0.60, -4.864),
            (0.10, -3.385),
            (0.00, -3.385),
        ])

        rate = self.engine._auto_preload_load_rate_locked()

        self.assertGreater(rate, 2.0)

    def test_auto_preload_rate_ignores_single_jounce_spike(self):
        self._set_load_history([
            (0.50, -5.00),
            (0.40, -4.99),
            (0.30, -3.00),
            (0.20, -4.98),
            (0.10, -4.97),
            (0.00, -4.96),
        ])

        rate = self.engine._auto_preload_load_rate_locked()

        self.assertLess(rate, 1.0)

    def test_auto_preload_remembers_upward_momentum_past_stop_jounce(self):
        self.assertGreaterEqual(
            self.engine._auto_preload_up_rate_memory_seconds(),
            engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS * 2.5,
        )

    def test_auto_preload_continuous_speed_ramp_limits_step_change(self):
        ramped = self.engine._auto_preload_slew_speed(10.0, 50.0, 0.1)

        self.assertAlmostEqual(
            ramped,
            10.0 + (engine_module.PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND * 0.1),
        )

    def test_auto_preload_continuous_brakes_when_prediction_reaches_final_approach(self):
        self.engine.auto_preload_initial_stop_seen = True
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS - 0.2,
            0.0,
            engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS + 0.01,
        )

        self.assertTrue(should_brake)
        self.assertTrue(self.engine.auto_preload_final_approach_stop_seen)
        self.assertFalse(self.engine.auto_preload_near_band_seen)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "final_approach_stop_target")

    def test_auto_preload_continuous_creeps_after_final_brake_when_still_far(self):
        self.engine.auto_preload_initial_stop_seen = True
        self.engine.auto_preload_final_approach_stop_seen = True

        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_MIN_LBS - engine_module.PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS - 0.2,
            0.0,
            engine_module.PRELOAD_MIN_LBS - 0.01,
        )

        self.assertFalse(should_brake)

    def test_auto_preload_continuous_rebrakes_after_final_brake_if_prediction_reaches_band(self):
        self.engine.auto_preload_initial_stop_seen = True
        self.engine.auto_preload_final_approach_stop_seen = True

        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS - engine_module.PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS - 0.2,
            0.0,
            engine_module.PRELOAD_MIN_LBS + 0.01,
        )

        self.assertTrue(should_brake)

    def test_auto_preload_continuous_ignores_prediction_far_before_initial_gate(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            -7.3,
            4.7,
            -0.2,
        )

        self.assertFalse(should_brake)
        self.assertFalse(self.engine.auto_preload_initial_stop_seen)
        self.assertFalse(self.engine.auto_preload_final_approach_stop_seen)
        self.assertEqual(len(self.engine.auto_preload_trace), 0)

    def test_auto_preload_continuous_ignores_prediction_far_before_initial_gate_even_after_coast_start(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            -4.7,
            2.1,
            -0.2,
        )

        self.assertFalse(should_brake)
        self.assertFalse(self.engine.auto_preload_initial_stop_seen)
        self.assertFalse(self.engine.auto_preload_final_approach_stop_seen)
        self.assertEqual(len(self.engine.auto_preload_trace), 0)

    def test_auto_preload_continuous_ignores_prediction_close_to_initial_gate(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            -3.2,
            2.1,
            -0.2,
        )

        self.assertFalse(should_brake)
        self.assertFalse(self.engine.auto_preload_initial_stop_seen)
        self.assertFalse(self.engine.auto_preload_final_approach_stop_seen)

    def test_auto_preload_continuous_brakes_after_prediction_enable_point(self):
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_PREDICT_ENABLE_LBS + 0.05,
            0.5,
            engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS + 0.01,
        )

        self.assertTrue(should_brake)
        self.assertTrue(self.engine.auto_preload_final_approach_stop_seen)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "final_approach_stop_target")

    def test_auto_preload_continuous_brakes_without_final_phase_change_until_near_final(self):
        self.engine.auto_preload_initial_stop_seen = True

        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            -4.7,
            2.1,
            -0.2,
        )

        self.assertFalse(should_brake)
        self.assertFalse(self.engine.auto_preload_final_approach_stop_seen)

    def test_auto_preload_continuous_final_brake_target_after_initial_stop(self):
        self.assertEqual(
            self.engine._auto_preload_continuous_brake_target_locked(),
            min(engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS, engine_module.PRELOAD_MIN_LBS),
        )

        self.engine.auto_preload_initial_stop_seen = True

        self.assertEqual(
            self.engine._auto_preload_continuous_brake_target_locked(),
            min(engine_module.PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS, engine_module.PRELOAD_MIN_LBS),
        )

    def test_auto_preload_continuous_brakes_at_bottom_of_allowed_band(self):
        self.engine.auto_preload_initial_stop_seen = True
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_MIN_LBS - 0.5,
            1.0,
            engine_module.PRELOAD_MIN_LBS + 0.001,
        )

        self.assertTrue(should_brake)

    def test_auto_preload_continuous_brakes_on_fast_coast_before_target(self):
        self.engine.auto_preload_initial_stop_seen = True
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            -4.7,
            2.1,
            -1.9,
        )

        self.assertFalse(should_brake)

    def test_auto_preload_continuous_uses_fast_poll_interval(self):
        engine_module.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS = 0.025

        self.assertEqual(self.engine._auto_preload_continuous_poll_seconds(), 0.025)

    def test_auto_preload_continuous_poll_interval_has_floor(self):
        engine_module.PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS = -1.0

        self.assertEqual(self.engine._auto_preload_continuous_poll_seconds(), 0.01)

    def test_auto_preload_can_recover_small_overshoot_after_band_seen(self):
        self.assertFalse(self.engine._auto_preload_can_recover_post_band_locked(1.06))

        self.engine.auto_preload_near_band_seen = True

        self.assertTrue(self.engine._auto_preload_can_recover_post_band_locked(1.06))
        self.assertFalse(
            self.engine._auto_preload_can_recover_post_band_locked(
                engine_module.PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS + 0.1
            )
        )

    def test_auto_preload_latches_ready_when_overshoot_drifts_back_into_band(self):
        original_recovery_seconds = engine_module.PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS
        original_drift_window = engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS
        original_in_band_end = engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS
        engine_module.PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS = 0.5
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = 0.05
        engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS = 0.01
        loads = iter([-0.1, 1.08, 0.6, -0.1])
        self.engine.state["auto_preload_running"] = True

        def refresh(*args, **kwargs):
            try:
                value = next(loads)
            except StopIteration:
                value = -0.1
            self.engine._set_load_state_locked(value, 100.0)

        self.engine._refresh_auto_preload_load = refresh
        self.engine._auto_preload_ready_locked = lambda: True
        self.engine._auto_preload_scan_ready_locked = lambda: True

        try:
            self.engine._auto_preload_continuous_loop()
        finally:
            engine_module.PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS = original_recovery_seconds
            engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = original_drift_window
            engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS = original_in_band_end

        events = [entry["event"] for entry in self.engine.auto_preload_trace]
        self.assertIn("post_band_settle_start", events)
        self.assertIn("post_abort_recovery_ready", events)
        self.assertTrue(self.engine.state["preload_ready_latched"])

    def test_auto_preload_continuous_does_not_wait_for_zero_to_brake(self):
        self.engine.auto_preload_initial_stop_seen = True
        should_brake = self.engine._auto_preload_continuous_should_brake_locked(
            engine_module.PRELOAD_AUTO_TARGET_LBS - 0.05,
            0.0,
            engine_module.PRELOAD_AUTO_TARGET_LBS,
        )

        self.assertTrue(should_brake)

    def test_preload_hold_trim_increases_only_in_lower_half_while_dropping(self):
        hold_load = engine_module.PRELOAD_AUTO_TARGET_LBS - 0.05
        self.engine.state["current_load"] = hold_load
        self._set_load_history([
            (0.50, hold_load + 0.08),
            (0.25, hold_load + 0.04),
            (0.00, hold_load),
        ])

        self.engine._preload_hold_update_locked()

        self.assertEqual(self.engine.preload_hold_trim_us, 1)
        self.assertEqual(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US + 1)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "hold_trim")

    def test_preload_hold_trim_does_not_increase_below_allowed_band(self):
        self.engine.preload_hold_active = True
        self.engine.preload_hold_trim_us = 3
        self.engine.state["current_load"] = engine_module.PRELOAD_MIN_LBS - 0.01

        self.engine._preload_hold_update_locked()

        self.assertEqual(self.engine.preload_hold_trim_us, 0)
        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.actuator.last_command, "neutral")

    def test_preload_hold_uses_scan_load_without_direct_control_read(self):
        self.engine.preload_hold_active = True
        self.engine.state["current_load"] = engine_module.PRELOAD_MIN_LBS - 0.01
        self.engine._refresh_auto_preload_load = lambda *args, **kwargs: self.fail("hold should not direct-read load")

        self.engine._preload_hold_update_locked()

        self.assertFalse(self.engine.preload_hold_active)
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

    def test_preload_hold_trim_decreases_for_positive_recovery_after_latch(self):
        self.engine.preload_hold_active = True
        self.engine._set_preload_ready_latch_locked(0.0)
        self.engine.state["current_load"] = 0.8
        self._set_load_history([
            (1.00, 0.7),
            (0.50, 0.75),
            (0.00, 0.8),
        ])

        self.engine._preload_hold_update_locked()

        self.assertTrue(self.engine.preload_hold_active)
        self.assertEqual(self.engine.preload_hold_trim_us, -1)
        self.assertEqual(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US - 1)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "hold_trim")

    def test_preload_hold_stops_above_positive_recovery_limit(self):
        self.engine.preload_hold_active = True
        self.engine._set_preload_ready_latch_locked(0.0)
        self.engine.state["current_load"] = engine_module.PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS + 0.1

        self.engine._preload_hold_update_locked()

        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "hold_out_of_band")

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
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = 0.0
        engine_module.PRELOAD_AUTO_DRIFT_WINDOW_SECONDS = 0.05
        engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS = 0.0
        engine_module.PRELOAD_AUTO_TIMEOUT_SECONDS = 1.0
        self.engine.state["auto_preload_running"] = True
        self._set_load(0.0)
        self.engine.load_cell.samples.extend([-8.0, -8.0, -8.0, -8.0])
        self.engine._auto_preload_ready_locked = lambda: True

        self.engine._auto_preload_loop()

        self.assertFalse(self.engine.state["auto_preload_running"])
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(list(self.engine.load_cell.samples), [])
        self.assertIn("in_band_complete", [entry["event"] for entry in self.engine.auto_preload_trace])
        self.assertNotEqual(self.engine.state["auto_preload_message"], "Check tension")

    def test_auto_preload_scan_ready_blocks_when_scan_load_is_out_of_band(self):
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = 0.5
        now = time.monotonic()
        self.engine.scan_load_history.clear()
        for seconds_ago, value in [
            (0.45, engine_module.PRELOAD_MIN_LBS + 0.1),
            (0.25, engine_module.PRELOAD_MIN_LBS + 0.05),
            (0.0, engine_module.PRELOAD_MIN_LBS - 0.05),
        ]:
            self.engine.scan_load_history.append((now - seconds_ago, value))

        self.assertFalse(self.engine._auto_preload_scan_ready_locked())
        self.assertAlmostEqual(self.engine.state["scan_load_window_s"], 0.45, places=1)

    def test_auto_preload_scan_ready_allows_recent_scan_band_agreement(self):
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = 0.5
        now = time.monotonic()
        self.engine.scan_load_history.clear()
        for seconds_ago, value in [(0.45, -0.2), (0.25, -0.18), (0.0, -0.12)]:
            self.engine.scan_load_history.append((now - seconds_ago, value))

        self.assertTrue(self.engine._auto_preload_scan_ready_locked())

    def test_auto_preload_scan_ready_falls_back_to_stable_in_band_load(self):
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = 0.5
        self.engine.scan_load_history.clear()
        self.engine.state["current_load"] = -0.2
        self.engine.state["scan_load"] = -0.2
        self._set_load_history([
            (3.0, -0.2),
            (1.0, -0.21),
            (0.0, -0.2),
        ])

        self.assertTrue(self.engine._auto_preload_scan_ready_locked())

    def test_auto_preload_does_not_finish_when_scan_ready_is_false(self):
        engine_module.PRELOAD_AUTO_IN_BAND_END_SECONDS = 0.01
        engine_module.PRELOAD_AUTO_SCAN_VERIFY_SECONDS = 5.0
        engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS = 0.0
        engine_module.PRELOAD_AUTO_TIMEOUT_SECONDS = 0.2
        self.engine.state["auto_preload_running"] = True
        self._set_load(-0.19)

        self.engine._auto_preload_loop()

        events = [entry["event"] for entry in self.engine.auto_preload_trace]
        self.assertIn("in_band_complete", events)
        self.assertNotIn("hold_start", events)
        self.assertEqual(self.engine.state["auto_preload_message"], "Check tension")

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

    def test_auto_preload_accepts_small_low_drop_after_near_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.auto_preload_near_band_seen = True
        current_load = engine_module.PRELOAD_MIN_LBS - 0.02
        dropped_load = engine_module.PRELOAD_MIN_LBS - 0.07
        self.engine.state["current_load"] = current_load
        readings = iter([dropped_load, dropped_load - 0.01, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load, dropped_load])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertAlmostEqual(load, dropped_load)
        self.assertAlmostEqual(self.engine.state["current_load"], dropped_load)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(len(self.engine.auto_preload_trace), 0)

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

    def test_auto_preload_ignores_single_invalid_control_spike(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -7.85)
        self.assertEqual(self.engine.state["current_load"], -7.85)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_invalid_ignored")
        self.assertEqual(self.engine.auto_preload_trace[-1]["first_load"], 185.0)

    def test_auto_preload_ignores_out_of_band_high_control_loads(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0, 180.0, 181.0, 182.0, 183.0, 185.0, 180.0, 181.0, 182.0, 183.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -7.85)
        self.assertEqual(self.engine.state["current_load"], -7.85)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_invalid_ignored")

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
        readings = iter([-1.6, -19.0, -2.828, -19.0, -2.9, -19.0, -2.828, -19.0, -2.9, -19.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -3.381)
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_discarded")
        self.assertEqual(self.engine.auto_preload_control_rejects, 1)

    def test_auto_preload_ignores_far_invalid_sample_without_stopping_actuator(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ = True
        self.engine.state["current_load"] = -7.85
        readings = iter([185.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)
        self.engine.actuator.move_up(fast=True, speed_percent=45)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, -7.85)
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_invalid_ignored")

    def test_auto_preload_holds_neutral_after_discarded_control_burst(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_STOP_DURING_LOAD_READ = True
        engine_module.PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS = 2
        engine_module.PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS = 0.35
        self.engine.state["current_load"] = -3.381
        readings = iter([-1.6, -19.0, -2.828, -19.0, -2.9, -19.0, -2.828, -19.0, -2.9, -19.0])
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
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_invalid_ignored")

    def test_auto_preload_accepts_lower_reading_when_recovering_from_above_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.auto_preload_near_band_seen = True
        self.engine.state["current_load"] = 0.795
        readings = iter([-3.869, -5.9, -5.8, -5.7, -5.6])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertLess(load, engine_module.PRELOAD_MIN_LBS)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")

    def test_auto_preload_plausibility_gate_rejects_impossible_control_jump(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_ENABLED = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS = 0.35
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100 = 18.0
        self.engine.auto_preload_control_last_load = -6.768
        self.engine.auto_preload_control_last_time = time.monotonic() - 0.2
        self.engine.state["current_load"] = -6.768
        readings = iter([-1.0, -1.0, -1.0, -1.0, -1.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load(
            control_speed_percent=15,
            control_direction=True,
        )

        self.assertEqual(load, -6.768)
        self.assertEqual(self.engine.state["current_load"], -6.768)
        self.assertGreater(self.engine.auto_preload_control_hold_until, time.monotonic())
        self.assertIn("control_load_implausible", [entry["event"] for entry in self.engine.auto_preload_trace])

    def test_auto_preload_plausibility_gate_accepts_possible_control_change(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_ENABLED = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS = 0.35
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100 = 18.0
        self.engine.auto_preload_control_last_load = -2.765
        self.engine.auto_preload_control_last_time = time.monotonic() - 0.6
        self.engine.state["current_load"] = -2.765
        readings = iter([-1.0, -1.0, -1.0, -1.0, -1.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load(
            control_speed_percent=15,
            control_direction=True,
        )

        self.assertAlmostEqual(load, -1.0, places=2)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_confirmed")

    def test_auto_preload_ignores_jounce_during_stop_hold(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_ENABLED = True
        engine_module.PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS = 0.35
        self.engine.auto_preload_control_last_load = -0.15
        self.engine.auto_preload_control_last_time = time.monotonic()
        self.engine.auto_preload_control_hold_until = time.monotonic() + 0.45
        self.engine.state["current_load"] = -0.15
        self.engine.load_cell.get_control_force = lambda: -0.7

        load = self.engine._refresh_auto_preload_load(
            control_speed_percent=0,
            control_direction=None,
        )

        self.assertEqual(load, -0.15)
        self.assertEqual(self.engine.state["current_load"], -0.15)
        self.assertIn("control_load_jounce_ignored", [entry["event"] for entry in self.engine.auto_preload_trace])

    def test_auto_preload_rejects_large_negative_drop_after_near_band(self):
        engine_module.PRELOAD_AUTO_DIRECT_LOAD_READ = True
        self.engine.auto_preload_near_band_seen = True
        self.engine.state["current_load"] = 0.02
        readings = iter([-6.0, -6.1, -6.0, -6.05, -6.0, -6.0, -6.1, -6.0, -6.05, -6.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load = self.engine._refresh_auto_preload_load()

        self.assertEqual(load, 0.02)
        self.assertEqual(self.engine.state["current_load"], 0.02)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_drop_ignored_after_near_band")

    def test_auto_preload_ignores_direct_invalid_sample_without_stopping_actuator(self):
        self.engine.actuator.move_up(fast=True, speed_percent=20)
        readings = iter([120.0])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load, samples, needs_confirmation, rejected, trace_event = self.engine._read_auto_preload_control_load(
            -7.0,
            control_speed_percent=20,
            control_direction=True,
        )

        self.assertAlmostEqual(load, -7.0, places=1)
        self.assertTrue(needs_confirmation)
        self.assertFalse(rejected)
        self.assertEqual(trace_event, "control_load_invalid_ignored")
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_load_invalid_ignored")

    def test_auto_preload_uses_moving_control_sample_count_while_moving(self):
        engine_module.PRELOAD_AUTO_MOVING_CONTROL_SAMPLES = 3
        requested_samples = []

        def read_control_load(samples=None):
            requested_samples.append(samples)
            return -7.0

        self.engine.load_cell.get_control_force = read_control_load

        load, samples, needs_confirmation, rejected, trace_event = self.engine._read_auto_preload_control_load(
            -7.1,
            control_speed_percent=20,
            control_direction=True,
        )

        self.assertAlmostEqual(load, -7.0, places=1)
        self.assertEqual(samples, [-7.0])
        self.assertFalse(needs_confirmation)
        self.assertFalse(rejected)
        self.assertEqual(trace_event, "control_load_read")
        self.assertEqual(requested_samples, [3])

    def test_auto_preload_uses_default_control_read_when_stopped(self):
        requested_samples = []

        def read_control_load(samples=None):
            requested_samples.append(samples)
            return -7.0

        self.engine.load_cell.get_control_force = read_control_load

        self.engine._read_auto_preload_control_load(
            -7.1,
            control_speed_percent=0,
            control_direction=None,
        )

        self.assertEqual(requested_samples, [None])

    def test_auto_preload_stops_for_spike_confirmation_near_initial_gate(self):
        self.engine.actuator.move_up(fast=True, speed_percent=20)
        readings = iter([-1.0, -2.9, -2.8, -2.9, -2.8, -2.85, -2.9, -2.8, -2.9, -2.8])
        self.engine.load_cell.get_control_force = lambda: next(readings)

        load, samples, needs_confirmation, rejected, trace_event = self.engine._read_auto_preload_control_load(
            -2.9,
            control_speed_percent=20,
            control_direction=True,
        )

        self.assertAlmostEqual(load, -2.8, places=1)
        self.assertTrue(needs_confirmation)
        self.assertFalse(rejected)
        self.assertEqual(trace_event, "control_load_confirmed")
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_read_stop")

    def test_scan_rejects_large_negative_drop_after_near_band(self):
        self.engine.auto_preload_near_band_seen = True
        self.engine.state["current_load"] = 0.02
        self.engine.load_cell.get_force = lambda: -6.0

        self.engine._scan_once()

        self.assertEqual(self.engine.state["current_load"], 0.02)
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "scan_load_drop_ignored_after_near_band")

    def test_auto_preload_stop_jounce_hold_sets_control_anchor(self):
        engine_module.PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS = 0.45

        self.engine._hold_auto_preload_after_stop_locked(-0.12, "target_band")

        self.assertEqual(self.engine.auto_preload_control_last_load, -0.12)
        self.assertGreater(self.engine.auto_preload_control_hold_until, time.monotonic())
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "control_stop_jounce_hold")

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
            (0.60, -1.35),
            (0.30, -1.32),
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

    def test_auto_preload_trace_persists_jsonl(self):
        self.engine._start_auto_preload_trace_file_locked()
        self.engine._record_auto_preload_trace_locked("sample", index=1, load=-0.1)

        trace_files = list(engine_module.PRELOAD_AUTO_TRACE_DIR.glob("auto_tension_*.jsonl"))
        self.assertEqual(len(trace_files), 1)
        self.assertIn('"event": "sample"', trace_files[0].read_text(encoding="utf-8"))

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
        self.engine.auto_preload_cancel_requested = False
        self.engine.auto_preload_contact_detected = True

        ok, message = self.engine.start_pull(self.test_id)

        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])
        self.assertEqual(self.engine.state["auto_preload_message"], "")
        self.assertFalse(self.engine.state["auto_preload_sensor_fault"])
        self.assertFalse(self.engine.state["auto_preload_short_stable"])
        self.assertFalse(self.engine.state["auto_preload_drift_stable"])
        self.assertTrue(self.engine.auto_preload_cancel_requested)
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

    def test_preload_hold_loop_does_not_override_active_pull(self):
        engine_module.PRELOAD_HOLD_TRIM_INTERVAL_SECONDS = 0.01
        self.engine.actuator.pull_direction = "up"
        self.engine.preload_hold_active = True
        self.engine.state["test_running"] = True
        self.engine.actuator.pull()
        self.engine.state["actuator_command"] = self.engine.actuator.last_command

        self.engine._preload_hold_loop(self.engine.actuator_epoch)

        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.state["actuator_command"], "up_pull")

    def test_glide_hold_loop_does_not_override_active_pull(self):
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = 0.0
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = 0.05
        self.engine.actuator.pull_direction = "up"
        self.engine.preload_hold_active = True
        self.engine.state["test_running"] = True
        self.engine.actuator.pull()
        self.engine.state["actuator_command"] = self.engine.actuator.last_command

        self.engine._glide_hold_loop(self.engine.actuator_epoch)

        self.assertFalse(self.engine.preload_hold_active)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.state["actuator_command"], "up_pull")

    # --- Actuator ownership / epoch (jog-stomp BUG2) ---

    def test_actuator_epoch_advances_on_ownership_transfer(self):
        e0 = self.engine.actuator_epoch
        self.engine.jog("up")
        self.assertGreater(self.engine.actuator_epoch, e0)
        e1 = self.engine.actuator_epoch
        self.engine.jog("stop")
        self.assertGreater(self.engine.actuator_epoch, e1)
        e2 = self.engine.actuator_epoch
        self._set_load(-0.10)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        self.assertGreater(self.engine.actuator_epoch, e2)

    def test_glide_hold_hands_off_without_stomping_a_jog(self):
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = 0.0
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = 5.0
        # A glide hold is running under this epoch...
        old_epoch = self.engine.actuator_epoch
        self.engine.preload_hold_active = True
        # ...then the operator jogs up: ownership moves on and the actuator moves.
        self.engine.jog("up")
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertGreater(self.engine.actuator_epoch, old_epoch)
        # Simulate a hold loop that has not yet noticed: its flag is still set,
        # only the epoch has moved -- the epoch check ALONE must force a handoff.
        self.engine.preload_hold_active = True
        self.engine._glide_hold_loop(old_epoch)
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertFalse(self.engine.preload_hold_active)

    def test_preload_hold_hands_off_without_stomping_a_jog(self):
        engine_module.PRELOAD_HOLD_TRIM_INTERVAL_SECONDS = 0.01
        old_epoch = self.engine.actuator_epoch
        self.engine.preload_hold_active = True
        self.engine.jog("up")
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        # Flag still set, only the epoch has moved -> epoch check forces handoff.
        self.engine.preload_hold_active = True
        self.engine._preload_hold_loop(old_epoch)
        self.assertEqual(self.engine.actuator.last_command, "up_fast")
        self.assertFalse(self.engine.preload_hold_active)

    def test_glide_hold_self_stops_on_sensor_fault(self):
        engine_module.PRELOAD_GLIDE_HOLD_SETTLE_S = 0.0
        engine_module.PRELOAD_GLIDE_HOLD_TIMEOUT_S = 5.0
        # We still own the actuator (epoch matches) but the load cell faults:
        epoch = self.engine._bump_actuator_epoch_locked()
        self.engine.preload_hold_active = True
        self.engine.state["auto_preload_sensor_fault"] = True
        self.engine.actuator.move_up(fast=True, speed_percent=50)
        self.assertEqual(self.engine.actuator.last_command, "up_fast")

        self.engine._glide_hold_loop(epoch)

        # Self-stop (neutral) rather than hand off, because we still own it.
        self.assertEqual(self.engine.actuator.last_command, "neutral")
        self.assertEqual(self.engine.actuator.last_pulse_us, engine_module.VICTOR_NEUTRAL_US)
        self.assertFalse(self.engine.preload_hold_active)

    def test_auto_preload_move_does_not_override_active_pull(self):
        self.engine.actuator.pull_direction = "up"
        self._set_load(-0.10)

        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        pull_pulse = self.engine.actuator.last_pulse_us

        moved = self.engine._move_preload_direction_locked(increase=True, speed_percent=50)

        self.assertFalse(moved)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.actuator.last_pulse_us, pull_pulse)
        self.assertEqual(self.engine.state["actuator_command"], "up_pull")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "auto_move_ignored_during_pull")

    def test_auto_preload_stop_does_not_override_active_pull(self):
        self.engine.actuator.pull_direction = "up"
        self._set_load(-0.10)

        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        pull_pulse = self.engine.actuator.last_pulse_us

        stopped = self.engine._auto_preload_stop_actuator_locked()

        self.assertFalse(stopped)
        self.assertEqual(self.engine.actuator.last_command, "up_pull")
        self.assertEqual(self.engine.actuator.last_pulse_us, pull_pulse)
        self.assertEqual(self.engine.state["actuator_command"], "up_pull")
        self.assertEqual(self.engine.auto_preload_trace[-1]["event"], "auto_stop_ignored_during_pull")

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

    def test_start_rejects_future_calibration_date(self):
        future = (dt.date.today() + dt.timedelta(days=1)).isoformat()
        storage.update_job(self.job_id, form={"load_cell_calibration_date": future})
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("future", message)

    def test_start_rejects_unparseable_calibration_date(self):
        storage.update_job(self.job_id, form={"load_cell_calibration_date": "soon"})
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("must be recorded", message)

    def test_start_accepts_very_old_calibration_date(self):
        # Age is never gated: the recorded date is kept as entered, no matter how
        # old, as long as it is parseable and not in the future.
        storage.update_job(
            self.job_id,
            form={
                "load_cell_calibration_date": "2001-01-01",
                "ir_temp_gun_calibration_date": "2001-01-01",
            },
        )
        self._set_load(0.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)

    def test_calibration_date_error_helper(self):
        today = dt.date(2026, 7, 21)
        self.assertIsNone(_calibration_date_error("2020-01-01", today))
        self.assertIsNone(_calibration_date_error("2001-01-01", today))  # very old is fine
        self.assertEqual(_calibration_date_error("", today), "must be recorded")
        self.assertEqual(_calibration_date_error("nope", today), "must be recorded")
        self.assertIn("future", _calibration_date_error("2026-07-22", today))

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
