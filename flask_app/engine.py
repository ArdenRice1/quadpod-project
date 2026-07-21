import datetime as dt
import json
import threading
import time
from collections import deque

from config import (
    APP_VERSION,
    DISCONNECT_STOP_SECONDS,
    FAILURE_CONFIRM_SAMPLES,
    FAILURE_DROP_LBS,
    FAILURE_DROP_PERCENT,
    FAILURE_MIN_PEAK_LBS,
    MAX_FORCE_LBS,
    MAX_TEST_SECONDS,
    LOAD_STABLE_DELTA_LBS,
    LOAD_STABLE_WINDOW_SECONDS,
    LOADCELL_DISPLAY_ALPHA,
    LOADCELL_DISPLAY_SNAP_DELTA_LBS,
    POST_STOP_LOG_MAX_SECONDS,
    PRELOAD_AUTO_ABORT_LBS,
    PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS,
    PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS,
    PRELOAD_AUTO_APPROACH_SETTLE_SECONDS,
    PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS,
    PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS,
    PRELOAD_AUTO_COARSE_SETTLE_SECONDS,
    PRELOAD_AUTO_COARSE_UNTIL_LBS,
    PRELOAD_AUTO_DEADBAND_LBS,
    PRELOAD_AUTO_DRIFT_MAX_DROP_LBS,
    PRELOAD_AUTO_DRIFT_WARN_SECONDS,
    PRELOAD_AUTO_DRIFT_WINDOW_SECONDS,
    PRELOAD_AUTO_DOWN_PULSE_SECONDS,
    PRELOAD_AUTO_MIN_PULSE_SECONDS,
    PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS,
    PRELOAD_AUTO_ADAPTIVE_PULSE_MIN_SCALE,
    PRELOAD_AUTO_ADAPTIVE_SPEED_MIN_PERCENT,
    PRELOAD_AUTO_APPROACH_DISTANCE_LBS,
    PRELOAD_AUTO_COAST_MARGIN_SCALE,
    PRELOAD_AUTO_COARSE_MAX_DELTA_LBS,
    PRELOAD_AUTO_CONTROL_CONFIRM_MAX_RANGE_LBS,
    PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES,
    PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS,
    PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS,
    PRELOAD_AUTO_CONTROL_MAX_VALID_LBS,
    PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS,
    PRELOAD_AUTO_CONTROL_MIN_VALID_LBS,
    PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS,
    PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS,
    PRELOAD_AUTO_MOVING_CONTROL_SAMPLES,
    PRELOAD_AUTO_CONTINUOUS_BRAKE_MARGIN_LBS,
    PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_START_LBS,
    PRELOAD_AUTO_CONTINUOUS_CRAWL_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_CRAWL_MIN_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_CRAWL_STOP_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_CRAWL_ZONE_LBS,
    PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_FLOOR_START_LBS,
    PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_STOP_MARGIN_LBS,
    PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS,
    PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS,
    PRELOAD_AUTO_CONTINUOUS_KD,
    PRELOAD_AUTO_CONTINUOUS_KP,
    PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND,
    PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_SECONDS,
    PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_CURVE,
    PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_RATE_SCALE,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_LBS,
    PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_SLOWDOWN_LBS,
    PRELOAD_AUTO_CONTACT_COARSE_MAX_DELTA_LBS,
    PRELOAD_AUTO_CONTACT_COARSE_PULSE_SECONDS,
    PRELOAD_AUTO_CONTACT_COARSE_SPEED_PERCENT,
    PRELOAD_AUTO_CONTACT_DELTA_LBS,
    PRELOAD_AUTO_CONTACT_MAX_DELTA_LBS,
    PRELOAD_AUTO_CONTACT_MODE_START_LBS,
    PRELOAD_AUTO_CONTACT_PULSE_SECONDS,
    PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS,
    PRELOAD_AUTO_CONTACT_SETTLE_SECONDS,
    PRELOAD_AUTO_CONTACT_SPEED_PERCENT,
    PRELOAD_AUTO_DIRECT_LOAD_READ,
    PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS,
    PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
    PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS,
    PRELOAD_AUTO_IN_BAND_END_SECONDS,
    PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_MAX_STOP_MARGIN_LBS,
    PRELOAD_AUTO_MIN_STOP_MARGIN_LBS,
    PRELOAD_AUTO_MODE,
    PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS,
    PRELOAD_AUTO_NEAR_BAND_DROP_REJECT_LBS,
    PRELOAD_AUTO_NEGATIVE_JUMP_DELTA_LBS,
    PRELOAD_AUTO_NEGATIVE_JUMP_GUARD_START_LBS,
    PRELOAD_AUTO_PULSE_SECONDS,
    PRELOAD_AUTO_PULSE_CHECK_SECONDS,
    PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS,
    PRELOAD_AUTO_PLAUSIBILITY_ENABLED,
    PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100,
    PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS,
    PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS,
    PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS,
    PRELOAD_AUTO_PREDICT_ENABLE_LBS,
    PRELOAD_AUTO_PREDICT_STOP_LBS,
    PRELOAD_AUTO_RATE_WINDOW_SECONDS,
    PRELOAD_AUTO_SPEED_PERCENT,
    PRELOAD_AUTO_SCAN_VERIFY_SECONDS,
    PRELOAD_AUTO_STABLE_DELTA_LBS,
    PRELOAD_AUTO_STOP_DURING_LOAD_READ,
    PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS,
    PRELOAD_AUTO_STABLE_WINDOW_SECONDS,
    PRELOAD_AUTO_SETTLE_MAX_SECONDS,
    PRELOAD_AUTO_SETTLE_SECONDS,
    PRELOAD_AUTO_TARGET_LBS,
    PRELOAD_AUTO_TIMEOUT_SECONDS,
    PRELOAD_AUTO_TENSION_STAGES,
    PRELOAD_AUTO_TRACE_DIR,
    PRELOAD_AUTO_TRACE_MAX_ENTRIES,
    PRELOAD_GLIDE_ABORT_LBS,
    PRELOAD_GLIDE_CRAWL_PCT,
    PRELOAD_GLIDE_EASE_MARGIN_LBS,
    PRELOAD_GLIDE_EMA_ALPHA,
    PRELOAD_GLIDE_HOLD_ABORT_LBS,
    PRELOAD_GLIDE_HOLD_AFTER,
    PRELOAD_GLIDE_HOLD_AIM_HI_LBS,
    PRELOAD_GLIDE_HOLD_AIM_LO_LBS,
    PRELOAD_GLIDE_HOLD_GENTLE_GAP_LBS,
    PRELOAD_GLIDE_HOLD_MAX_ITERS,
    PRELOAD_GLIDE_HOLD_PULSE_MAX_US,
    PRELOAD_GLIDE_HOLD_PULSE_MIN_US,
    PRELOAD_GLIDE_HOLD_PULSE_MS,
    PRELOAD_GLIDE_HOLD_PULSE_MS_MAX,
    PRELOAD_GLIDE_HOLD_PULSE_US,
    PRELOAD_GLIDE_HOLD_REST_S,
    PRELOAD_GLIDE_HOLD_SETTLE_S,
    PRELOAD_GLIDE_HOLD_TIMEOUT_S,
    PRELOAD_GLIDE_KP_PCT_PER_LB,
    PRELOAD_GLIDE_LOOKAHEAD_S,
    PRELOAD_GLIDE_MAX_LBS,
    PRELOAD_GLIDE_MAX_PCT,
    PRELOAD_GLIDE_MIN_MOVE_PCT,
    PRELOAD_GLIDE_OVERSHOOT_LBS,
    PRELOAD_GLIDE_POLL_S,
    PRELOAD_GLIDE_POST_LOG_INTERVAL_S,
    PRELOAD_GLIDE_POST_LOG_S,
    PRELOAD_GLIDE_READY_CEILING_LBS,
    PRELOAD_GLIDE_SEATED_FLOOR_LBS,
    PRELOAD_GLIDE_RAMP_DOWN_PCT_PER_S,
    PRELOAD_GLIDE_RAMP_PCT_PER_S,
    PRELOAD_GLIDE_RATE_CRAWL_LBS_PER_S,
    PRELOAD_GLIDE_RATE_SLOW_LBS_PER_S,
    PRELOAD_GLIDE_RATE_WINDOW_S,
    PRELOAD_GLIDE_READ_SAMPLES,
    PRELOAD_GLIDE_RELAX_S,
    PRELOAD_GLIDE_STABLE_LBS,
    PRELOAD_GLIDE_STABLE_S,
    PRELOAD_GLIDE_TARGET_LBS,
    PRELOAD_GLIDE_TIMEOUT_S,
    PRELOAD_GLIDE_TOL_LBS,
    PRELOAD_GLIDE_WALL_LATCH,
    PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND,
    PRELOAD_HOLD_TRIM_ENABLED,
    PRELOAD_HOLD_TRIM_INTERVAL_SECONDS,
    PRELOAD_HOLD_TRIM_MAX_US,
    PRELOAD_HOLD_TRIM_STEP_US,
    PRELOAD_MAX_LBS,
    PRELOAD_MIN_LBS,
    PRELOAD_READY_LATCH_MARGIN_LBS,
    PRELOAD_READY_LATCH_POSITIVE_MARGIN_LBS,
    PRELOAD_STABILITY_SECONDS,
    PRELOAD_TARGET_LBS,
    PRELOAD_TOLERANCE_LBS,
    PULL_TARGET_IN_PER_MIN,
    SAMPLE_RATE_HZ,
    USE_MOCK_HARDWARE,
    VICTOR_NEUTRAL_US,
)
from hardware.actuator import Actuator
from hardware.loadcell import LoadCell
import storage


class QuadpodEngine:
    def __init__(self, use_mock=USE_MOCK_HARDWARE):
        self.use_mock = use_mock
        self.load_cell = LoadCell(use_mock=use_mock)
        self.actuator = Actuator(use_mock=use_mock)
        self.lock = threading.RLock()
        self.running = False
        self.thread = None
        self.last_client_poll = time.monotonic()
        self.failure_drop_samples = 0
        self.load_history = deque()
        self.scan_load_history = deque()
        self.auto_preload_trace = deque(maxlen=max(1, int(PRELOAD_AUTO_TRACE_MAX_ENTRIES)))
        self.auto_preload_trace_file = None
        self.auto_preload_coast_lbs = 0.0
        self.auto_preload_last_stop_load = None
        self.auto_preload_last_stop_increase = None
        self.auto_preload_contact_detected = False
        self.auto_preload_near_band_seen = False
        self.auto_preload_initial_stop_seen = False
        self.auto_preload_final_approach_stop_seen = False
        self.auto_preload_control_rejects = 0
        self.auto_preload_control_hold_until = 0.0
        self.auto_preload_control_hold_logged = False
        self.auto_preload_control_last_load = None
        self.auto_preload_control_last_time = None
        self.auto_preload_cancel_requested = False
        self.auto_preload_thread = None
        self.preload_hold_thread = None
        self.preload_hold_active = False
        self.preload_hold_trim_us = 0
        # Actuator ownership token. Bumped on every ownership transfer (jog,
        # start_pull, stop, a new auto-tension run, hold start). A background
        # loop captures the epoch it started under and refuses to command the
        # actuator -- even to neutral/stop -- once the epoch has moved on, so a
        # jog/pull/Stop that lands mid-loop is never stomped by a late command.
        self.actuator_epoch = 0
        # Epoch owned by the current auto-tension run (its command helpers only
        # act while this still matches actuator_epoch).
        self.auto_preload_epoch = 0
        self.state = {
            "current_load": 0.0,
            "scan_load": 0.0,
            "scan_load_window_s": 0.0,
            "display_load": 0.0,
            "raw_load": 0.0,
            "peak_load": 0.0,
            "preload_ready": False,
            "preload_ready_latched": False,
            "preload_stable": False,
            "test_running": False,
            "test_complete": False,
            "active_test_id": None,
            "started_at_monotonic": None,
            "elapsed_s": 0.0,
            "sample_count": 0,
            "stop_reason": "",
            "stop_pending": False,
            "stop_pending_started_at": None,
            "last_error": "",
            "actuator_command": "neutral",
            "jog_speed_percent": 100,
            "auto_preload_running": False,
            "auto_preload_message": "",
            "auto_preload_short_stable": False,
            "auto_preload_drift_stable": False,
            "auto_preload_drift_drop_lbs": 0.0,
            "auto_preload_drift_window_s": 0.0,
            "auto_preload_sensor_fault": False,
        }

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            status = dict(self.state)
            status["load_cell"] = self.load_cell.health()
            status["actuator"] = self.actuator.health()
            status["mock_hardware"] = self.use_mock
            status["preload_target_lbs"] = PRELOAD_TARGET_LBS
            status["preload_min_lbs"] = PRELOAD_MIN_LBS
            status["preload_max_lbs"] = PRELOAD_MAX_LBS
            status["preload_tolerance_lbs"] = PRELOAD_TOLERANCE_LBS
            status["app_version"] = APP_VERSION
            self.last_client_poll = time.monotonic()
            return status

    def auto_preload_trace_snapshot(self):
        with self.lock:
            return list(self.auto_preload_trace)

    def _bump_actuator_epoch_locked(self):
        """Take actuator ownership: invalidate any background loop's epoch."""
        self.actuator_epoch += 1
        return self.actuator_epoch

    def _owns_actuator_locked(self, epoch):
        """True if the caller's captured epoch is still the current owner."""
        return self.actuator_epoch == epoch

    def jog(self, action, speed_percent=None):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot jog while a pull test is running."
            if action in {"up", "down"}:
                self._clear_preload_ready_latch_locked()
                self._stop_preload_hold_locked()
            if speed_percent is not None:
                self.state["jog_speed_percent"] = max(1, min(100, int(float(speed_percent))))
            speed = self.state["jog_speed_percent"]
            if action == "up":
                ok = self.actuator.move_up(fast=True, speed_percent=speed)
            elif action == "down":
                ok = self.actuator.move_down(fast=True, speed_percent=speed)
            elif action == "stop":
                if self.preload_hold_active:
                    return True, self.actuator.last_error
                self._bump_actuator_epoch_locked()
                ok = self.actuator.stop()
            else:
                return False, "Unknown jog action."
            self.state["actuator_command"] = self.actuator.last_command
            return ok, self.actuator.last_error

    def set_jog_speed(self, speed_percent):
        with self.lock:
            self.state["jog_speed_percent"] = max(1, min(100, int(float(speed_percent))))
            return True, f"Jog speed set to {self.state['jog_speed_percent']}%."

    def auto_preload(self):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot auto tension while a pull test is running."
            if self.state["auto_preload_running"]:
                return True, "Auto tension is already running."
            self._stop_preload_hold_locked()
            self._reset_test_session_locked()
            self._clear_preload_ready_latch_locked()
            self.auto_preload_trace.clear()
            self._start_auto_preload_trace_file_locked()
            self._reset_auto_preload_control_locked()
            self.auto_preload_cancel_requested = False
            if self.load_cell.use_mock or self.load_cell.gpio is not None:
                self.load_cell.reset_hardware()
            self.state["auto_preload_running"] = True
            self.state["auto_preload_message"] = "Auto Tension"
            self.state["auto_preload_sensor_fault"] = False
            self._record_auto_preload_trace_locked(
                "start",
                load=self.state.get("current_load"),
                min_lbs=PRELOAD_MIN_LBS,
                max_lbs=PRELOAD_MAX_LBS,
                abort_lbs=PRELOAD_AUTO_ABORT_LBS,
            )
            self.auto_preload_epoch = self._bump_actuator_epoch_locked()
            self.auto_preload_thread = threading.Thread(target=self._auto_preload_loop, daemon=True)
            self.auto_preload_thread.start()
            return True, self.state["auto_preload_message"]

    def tare(self):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot tare while a pull test is running."
            if self.state["auto_preload_running"]:
                return False, "Cannot tare while Auto Tension is running."
            self._clear_preload_ready_latch_locked()
            self._stop_preload_hold_locked()
            ok = self.load_cell.tare()
            return ok, self.load_cell.last_error

    def calibrate_load_cell(self, known_lbs):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot calibrate while a pull test is running."
            if self.state["auto_preload_running"]:
                return False, "Cannot calibrate while Auto Tension is running."
            self._clear_preload_ready_latch_locked()
            self._stop_preload_hold_locked()
            if known_lbs <= 0:
                return False, "Known weight must be greater than zero."
            self.load_cell.get_force()
            raw_counts = float(getattr(self.load_cell, "last_raw_counts", 0.0) or 0.0)
            zero_counts = float(self.load_cell.health().get("zero_counts") or 0.0)
            raw_delta = raw_counts - zero_counts
            if abs(raw_delta) < 1.0:
                return False, "Known weight did not create enough raw load-cell change after tare."
            reference_unit = self.load_cell.calibrate_from_known_weight(raw_delta, known_lbs)
            self.load_cell.samples.clear()
            self.load_cell.persist_calibration("runtime")
            return True, f"Runtime reference unit set to {reference_unit:.6f}. Update QUADPOD_LOADCELL_REFERENCE_UNIT to make it permanent."

    def start_pull(self, test_id):
        with self.lock:
            if self.state["test_running"]:
                return False, "A pull test is already running."
            if self.state["auto_preload_running"]:
                return False, "Wait for Auto Tension to finish before starting the pull."
            test = storage.get_test(test_id)
            if not test:
                return False, "Test record not found."

            load = float(self.state["current_load"])
            gate_errors = self._start_gate_errors_locked(test, load)
            if gate_errors:
                return False, "Cannot start pull: " + "; ".join(gate_errors)

            self._stop_preload_hold_locked()
            self._clear_preload_ready_latch_locked()
            storage.clear_samples(test_id)
            self.failure_drop_samples = 0
            self.load_history.clear()
            self._reset_auto_preload_control_locked()
            self.auto_preload_cancel_requested = True
            self.preload_hold_active = False
            self.preload_hold_trim_us = 0
            self.state.update(
                {
                    "peak_load": max(load, 0.0),
                    "test_running": True,
                    "test_complete": False,
                    "active_test_id": test_id,
                    "started_at_monotonic": time.monotonic(),
                    "elapsed_s": 0.0,
                    "sample_count": 0,
                    "stop_reason": "",
                    "stop_pending": False,
                    "stop_pending_started_at": None,
                    "last_error": "",
                }
            )
            self._clear_auto_preload_status_locked()
            self.last_client_poll = time.monotonic()
            storage.update_test(
                test_id,
                status="running",
                started_at=storage.utc_now(),
                completed_at=None,
                initial_preload_lbs=round(load, 3),
                peak_load_lbs=round(load, 3),
                stop_reason="",
                sample_count=0,
                software_version=APP_VERSION,
            )
            # Pull force changes fast -> disable glitch rejection so no real
            # reading is ever dropped/held during the actual test.
            self.load_cell.pause_glitch_reject()
            self.actuator.stop()
            self.state["actuator_command"] = self.actuator.last_command
            ok = self.actuator.pull()
            self.state["actuator_command"] = self.actuator.last_command
            if not ok:
                self._finish_stop_locked("actuator fault")
                return False, self.actuator.last_error
            storage.add_event(
                "Pull started",
                test_id=test_id,
                data={
                    "initial_load_lbs": load,
                    "pull_command": self.actuator.last_command,
                    "pull_pulse_us": self.actuator.last_pulse_us,
                    "pull_target_ipm": PULL_TARGET_IN_PER_MIN,
                    "jog_speed_percent": self.state.get("jog_speed_percent"),
                },
            )
            return True, "Pull started."

    def _start_gate_errors_locked(self, test, load):
        errors = []
        if not self._preload_start_allowed_locked(load):
            errors.append(f"tension must be {PRELOAD_MIN_LBS:.1f}-{PRELOAD_MAX_LBS:.1f} lb")

        load_health = self.load_cell.health()
        if not load_health.get("ok"):
            errors.append(load_health.get("last_error") or "load cell is not ready")
        actuator_health = self.actuator.health()
        if not actuator_health.get("ok"):
            errors.append(actuator_health.get("last_error") or "actuator is not ready")

        job = storage.get_job(test["job_id"])
        if not job:
            errors.append("job record not found")
            return errors

        job_form = job["form"]
        test_form = test["form"]
        today = dt.date.today()
        for field, label in [
            ("load_cell_calibration_date", "load cell calibration date"),
            ("ir_temp_gun_calibration_date", "IR temp gun calibration date"),
        ]:
            problem = _calibration_date_error(job_form.get(field, ""), today)
            if problem:
                errors.append(f"{label} {problem}")
        angle_value = test_form.get("angle_degrees")
        if not angle_value:
            errors.append("pull angle must be recorded")
        else:
            try:
                angle = float(angle_value)
                if angle < 80.0 or angle > 100.0:
                    errors.append("pull angle must be between 80 and 100 degrees")
            except (TypeError, ValueError):
                errors.append("pull angle must be a number")

        return errors

    def stop(self, reason="operator stop"):
        with self.lock:
            if self.state.get("auto_preload_running"):
                self.auto_preload_cancel_requested = True
                self._bump_actuator_epoch_locked()
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
                self.state["auto_preload_message"] = "Check tension"
                self._record_auto_preload_trace_locked(
                    "cancel_requested",
                    load=self.state.get("current_load"),
                    reason=reason,
                )
                return True
            if self.state.get("test_running"):
                self._begin_stop_locked(reason)
            else:
                self._finish_stop_locked(reason)
            return True

    def _scan_loop(self):
        interval = 1.0 / max(1.0, SAMPLE_RATE_HZ)
        while self.running:
            started = time.monotonic()
            try:
                self._scan_once()
            except Exception as exc:
                with self.lock:
                    self.state["last_error"] = str(exc)
                    self._finish_stop_locked("control loop fault")
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval - elapsed))

    def _scan_once(self):
        with self.lock:
            self._update_mock_force_locked()
            # While Auto Tension owns the load cell it drives its own reads and
            # state updates; a second reader here only adds GPIO contention and
            # halves the effective sample rate the controller sees.
            if self.state.get("auto_preload_running"):
                return

        load = self.load_cell.get_force()
        raw_counts = getattr(self.load_cell, "last_raw_counts", None)
        if raw_counts is None:
            raw_counts = getattr(self.load_cell, "last_raw_lbs", load)

        with self.lock:
            previous_load = float(self.state.get("current_load") or 0.0)
            if (
                not self.state["test_running"]
                and self._auto_preload_should_ignore_drop_after_near_band(previous_load, load)
            ):
                self._record_auto_preload_trace_locked(
                    "scan_load_drop_ignored_after_near_band",
                    previous_load=previous_load,
                    load=load,
                    raw_counts=raw_counts,
                    zero_counts=self.load_cell.health().get("zero_counts"),
                )
                load = previous_load
            self._record_scan_load_locked(load)
            self._set_load_state_locked(load, raw_counts)

            if not self.state["test_running"]:
                return

            test_id = self.state["active_test_id"]
            start_time = self.state["started_at_monotonic"] or time.monotonic()
            elapsed_s = time.monotonic() - start_time
            self.state["elapsed_s"] = elapsed_s
            self.state["peak_load"] = max(self.state["peak_load"], load)
            sample_count = storage.add_sample(test_id, elapsed_s, load, raw_counts)
            self.state["sample_count"] = sample_count

            if self.state.get("stop_pending"):
                pending_for = time.monotonic() - (self.state.get("stop_pending_started_at") or time.monotonic())
                if self._load_stable_locked() or pending_for >= POST_STOP_LOG_MAX_SECONDS:
                    self._finish_stop_locked(self.state.get("stop_reason") or "test stopped")
                return

            stop_reason = self._stop_reason_locked(load, elapsed_s)
            if stop_reason:
                self._begin_stop_locked(stop_reason)

    def _update_mock_force_locked(self):
        if not self.use_mock or not self.state["test_running"]:
            return

        start_time = self.state["started_at_monotonic"] or time.monotonic()
        elapsed_s = time.monotonic() - start_time
        if elapsed_s < 4.5:
            force = PRELOAD_TARGET_LBS + elapsed_s * 6.0
        elif elapsed_s < 6.0:
            force = PRELOAD_TARGET_LBS + 27.0
        else:
            force = max(0.0, self.state["peak_load"] - FAILURE_DROP_LBS - 0.8)
        self.load_cell.set_mock_force(force)

    def _stop_reason_locked(self, load, elapsed_s):
        if time.monotonic() - self.last_client_poll > DISCONNECT_STOP_SECONDS:
            return "phone/app disconnected"
        if self.load_cell.last_error:
            return "load cell fault"
        if self.state["peak_load"] >= MAX_FORCE_LBS:
            return "maximum force limit"
        if elapsed_s >= MAX_TEST_SECONDS:
            return "maximum run time/end of travel timeout"

        peak = float(self.state["peak_load"] or 0.0)
        required_drop = max(FAILURE_DROP_LBS, peak * FAILURE_DROP_PERCENT)
        if peak >= FAILURE_MIN_PEAK_LBS and peak - load >= required_drop:
            self.failure_drop_samples += 1
        else:
            self.failure_drop_samples = 0
        if self.failure_drop_samples >= max(1, FAILURE_CONFIRM_SAMPLES):
            return "confirmed load drop/failure"
        return ""

    def _auto_preload_loop(self):
        if PRELOAD_AUTO_MODE == "glide":
            self._auto_preload_glide_loop()
            return
        if PRELOAD_AUTO_MODE == "continuous":
            self._auto_preload_continuous_loop()
            return
        self._auto_preload_pulse_loop()

    def _glide_read(self):
        """One low-latency load-cell read for the glide loop (motor keeps moving)."""
        samples = max(1, int(PRELOAD_GLIDE_READ_SAMPLES))
        try:
            raw = self.load_cell.get_control_force(samples=samples)
        except TypeError:
            raw = self.load_cell.get_control_force()
        raw_counts = getattr(self.load_cell, "last_raw_counts", None)
        if raw_counts is None:
            raw_counts = getattr(self.load_cell, "last_raw_lbs", raw)
        return float(raw), raw_counts

    def _auto_preload_glide_loop(self):
        """Smooth velocity Auto Tension for the compliant rig.

        Never stops to read (stopping rings the spring-mass-damper). Trusts
        moving reads through a light EMA, commands velocity proportional to the
        remaining force error (so it glides slower as it closes), slews the
        command smoothly, and eases to neutral before target so the compliant
        string relaxes into band. Overshoot is limited by the velocity cap
        (max_pct) chosen so cap x feedback-lag stays under the band.
        """
        target = float(PRELOAD_GLIDE_TARGET_LBS)
        seated_hi = float(PRELOAD_GLIDE_READY_CEILING_LBS)
        seated_lo = float(PRELOAD_GLIDE_SEATED_FLOOR_LBS)
        overshoot_lbs = float(PRELOAD_GLIDE_OVERSHOOT_LBS)
        wall_latch_enabled = bool(PRELOAD_GLIDE_WALL_LATCH)
        ease_margin = max(0.0, float(PRELOAD_GLIDE_EASE_MARGIN_LBS))
        kp = max(0.0, float(PRELOAD_GLIDE_KP_PCT_PER_LB))
        min_move = max(1.0, float(PRELOAD_GLIDE_MIN_MOVE_PCT))
        max_pct = max(min_move, float(PRELOAD_GLIDE_MAX_PCT))
        ramp_up = max(1.0, float(PRELOAD_GLIDE_RAMP_PCT_PER_S))
        ramp_down = max(1.0, float(PRELOAD_GLIDE_RAMP_DOWN_PCT_PER_S))
        crawl_pct = max(1.0, float(PRELOAD_GLIDE_CRAWL_PCT))
        rate_slow = max(0.05, float(PRELOAD_GLIDE_RATE_SLOW_LBS_PER_S))
        rate_crawl = max(rate_slow + 0.05, float(PRELOAD_GLIDE_RATE_CRAWL_LBS_PER_S))
        rate_window = max(0.1, float(PRELOAD_GLIDE_RATE_WINDOW_S))
        lookahead = max(0.0, float(PRELOAD_GLIDE_LOOKAHEAD_S))
        alpha = max(0.0, min(1.0, float(PRELOAD_GLIDE_EMA_ALPHA)))
        poll = max(0.005, float(PRELOAD_GLIDE_POLL_S))
        abort_lbs = float(PRELOAD_GLIDE_ABORT_LBS)
        max_lbs = float(PRELOAD_GLIDE_MAX_LBS)
        stable_s = max(0.0, float(PRELOAD_GLIDE_STABLE_S))
        stable_lbs = max(0.0, float(PRELOAD_GLIDE_STABLE_LBS))
        relax_s = max(0.0, float(PRELOAD_GLIDE_RELAX_S))
        deadline = time.monotonic() + max(1.0, float(PRELOAD_GLIDE_TIMEOUT_S))

        ema = None
        vel = 0.0
        moving = False
        last_update = time.monotonic()
        in_band_since = None
        over_since = None
        wall_latched = False
        hold_should_start = False
        recent = deque()
        raw_hist = deque()

        with self.lock:
            self._record_auto_preload_trace_locked(
                "glide_start",
                load=self.state.get("current_load"),
                target_lbs=target,
                seated_lo=seated_lo,
                seated_hi=seated_hi,
                ease_margin_lbs=ease_margin,
                kp=kp,
                max_pct=max_pct,
                crawl_pct=crawl_pct,
            )
        try:
            while time.monotonic() < deadline:
                raw, raw_counts = self._glide_read()
                now = time.monotonic()
                ema = raw if ema is None else (alpha * raw + (1.0 - alpha) * ema)
                load = ema
                stop_loop = False

                with self.lock:
                    # A stuck/disconnected load cell (liveness) or a read failure
                    # must stop the moving actuator, not be trusted as a real force.
                    if self.load_cell.last_error:
                        self.state["auto_preload_sensor_fault"] = True
                    if self.state.get("auto_preload_sensor_fault"):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("sensor_fault_stop", load=load)
                        break
                    if self.auto_preload_cancel_requested or not self.state.get("auto_preload_running") or self.state["test_running"] or not self._owns_actuator_locked(self.auto_preload_epoch):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("cancelled", load=load)
                        break

                    self._set_load_state_locked(load, raw_counts)
                    recent.append((now, load))
                    while recent and recent[0][0] < now - max(stable_s, 0.5):
                        recent.popleft()

                    if load > abort_lbs:
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("abort", load=load, abort_lbs=abort_lbs)
                        break

                    # Rate of rise from RAW readings (responsive; the EMA would
                    # lag the taut wall). Predict past feedback latency so we ease
                    # before the real force blows through the band.
                    raw_hist.append((now, raw))
                    while raw_hist and raw_hist[0][0] < now - rate_window:
                        raw_hist.popleft()
                    rate = 0.0
                    if len(raw_hist) >= 2:
                        rt = raw_hist[-1][0] - raw_hist[0][0]
                        if rt > 0:
                            rate = (raw_hist[-1][1] - raw_hist[0][1]) / rt
                    predicted = raw + max(0.0, rate) * lookahead

                    error = target - load
                    at_rest = (not moving) and vel <= min_move * 0.5

                    if load > overshoot_lbs:
                        # Genuinely above 0 (past the noise band): overshoot. Ease
                        # and let the compliant string relax back down; if it can't
                        # within relax_s, fail so a ruined pull is flagged.
                        in_band_since = None
                        desired = 0.0
                        if over_since is None:
                            over_since = now
                            self._record_auto_preload_trace_locked(
                                "glide_overshoot", load=load, raw=raw, overshoot_lbs=overshoot_lbs
                            )
                        if now - over_since >= relax_s:
                            self._auto_preload_stop_actuator_locked()
                            self.state["auto_preload_message"] = "Check tension"
                            self._record_auto_preload_trace_locked(
                                "glide_overshoot_fail", load=load, overshoot_lbs=overshoot_lbs
                            )
                            break
                        self.state["auto_preload_message"] = "Settling"
                    elif load >= seated_lo:
                        # Seated band (slack removed, at/just below 0). Come to
                        # rest, confirm stable, then latch Ready = pull can start.
                        # Latch on the window MEAN (not a single noisy sample) and
                        # only if that mean is at/below 0.
                        over_since = None
                        desired = 0.0
                        if in_band_since is None:
                            in_band_since = now
                        band_vals = [v for t, v in recent if t >= in_band_since]
                        stable_ok = len(band_vals) >= 3 and (max(band_vals) - min(band_vals)) <= stable_lbs
                        window_mean = sum(band_vals) / len(band_vals) if band_vals else load
                        if at_rest and stable_ok and now - in_band_since >= stable_s and window_mean <= seated_hi:
                            self._set_preload_ready_latch_locked(load)
                            self.state["auto_preload_message"] = "Ready"
                            hold_should_start = bool(PRELOAD_GLIDE_HOLD_AFTER)
                            self._record_auto_preload_trace_locked(
                                "glide_ready", load=load, seconds=now - in_band_since,
                                seated_lo=seated_lo, seated_hi=seated_hi,
                            )
                            stop_loop = True
                        else:
                            self.state["auto_preload_message"] = "Settling"
                    else:
                        # Below the band: still slack -> drive up. Governed by how
                        # fast force rises (proximity to the wall) and eased on the
                        # latency-predicted reading so it never blows through 0.
                        in_band_since = None
                        over_since = None
                        if wall_latch_enabled and rate >= rate_slow:
                            wall_latched = True
                        # While below the seated band, only stop/coast when the
                        # predicted load reaches the seated floor. This prevents
                        # target/ease tuning from creating a dead zone where the
                        # actuator stops below the Ready band and times out.
                        if predicted >= seated_lo:
                            desired = 0.0
                            self.state["auto_preload_message"] = "Settling"
                        else:
                            base = max(min_move, min(max_pct, kp * max(0.0, error)))
                            # Wall governor: the faster force is rising, the closer
                            # we are to taut -> cap speed down toward a crawl (and
                            # once latched, stay at crawl - never re-accelerate).
                            if wall_latched or rate >= rate_crawl:
                                cap = crawl_pct
                            elif rate <= rate_slow:
                                cap = max_pct
                            else:
                                frac = (rate - rate_slow) / (rate_crawl - rate_slow)
                                cap = max_pct + (crawl_pct - max_pct) * frac
                            desired = min(base, cap)
                            self.state["auto_preload_message"] = "Auto Tension"

                    # Decelerate faster than we accelerate: quick to back off the
                    # wall, gentle to spin up (smooth motion avoids exciting the
                    # resonance).
                    ramp = ramp_up if desired >= vel else ramp_down
                    max_step = ramp * max(0.0, now - last_update)
                    delta = desired - vel
                    if max_step <= 0 or abs(delta) <= max_step:
                        vel = desired
                    else:
                        vel = vel + (max_step if delta > 0 else -max_step)

                    applied_cmd = 0
                    if desired <= 0.0 and vel < min_move:
                        vel = 0.0
                        if moving:
                            self._auto_preload_stop_actuator_locked()
                            moving = False
                    else:
                        applied_cmd = max(1, min(100, int(round(vel))))
                        moving = self._move_preload_direction_locked(increase=True, speed_percent=applied_cmd)
                        if moving:
                            self.state["actuator_command"] = self.actuator.last_command

                    # Full per-cycle record: raw vs filtered load, error, desired
                    # vs commanded speed, and dt (also measures the true achieved
                    # sample interval on real hardware).
                    self._record_auto_preload_trace_locked(
                        "glide",
                        load=load,
                        raw=raw,
                        err=error,
                        rate=rate,
                        pred=predicted,
                        des=desired,
                        vel=vel,
                        cmd=applied_cmd,
                        wall=wall_latched,
                        pulse_us=self.actuator.last_pulse_us,
                        dt=now - last_update,
                    )

                last_update = now
                if stop_loop:
                    break
                time.sleep(poll)
            else:
                with self.lock:
                    self._auto_preload_stop_actuator_locked()
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "glide_timeout", load=self.state.get("current_load"),
                        seconds=PRELOAD_GLIDE_TIMEOUT_S,
                    )
        finally:
            with self.lock:
                self._auto_preload_stop_actuator_locked()
                self.load_cell.samples.clear()
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "") == "Ready":
                    self.state["auto_preload_message"] = ""
                # Don't spawn the post-tension hold if the operator pressed Stop
                # during the ready->finally hand-off (Stop must be absolute).
                if hold_should_start and not self.auto_preload_cancel_requested and self._owns_actuator_locked(self.auto_preload_epoch):
                    self._start_glide_hold_locked()
                self._record_auto_preload_trace_locked(
                    "finish", load=self.state.get("current_load"),
                    message=self.state.get("auto_preload_message"),
                )
                self._start_glide_post_monitor_locked()

    def _start_glide_hold_locked(self):
        if not PRELOAD_GLIDE_HOLD_AFTER or self.state.get("test_running"):
            return
        if self.preload_hold_active:
            return
        self.preload_hold_active = True
        epoch = self._bump_actuator_epoch_locked()
        self.preload_hold_thread = threading.Thread(
            target=self._glide_hold_loop, args=(epoch,), daemon=True
        )
        self.preload_hold_thread.start()
        self._record_auto_preload_trace_locked(
            "glide_hold_start", load=self.state.get("current_load"),
            settle_s=PRELOAD_GLIDE_HOLD_SETTLE_S,
            aim_lo=PRELOAD_GLIDE_HOLD_AIM_LO_LBS, aim_hi=PRELOAD_GLIDE_HOLD_AIM_HI_LBS,
            pulse_us=PRELOAD_GLIDE_HOLD_PULSE_US, pulse_ms=PRELOAD_GLIDE_HOLD_PULSE_MS,
        )

    def _glide_hold_loop(self, epoch):
        """Seat the tension with settle-then-verify (open-loop micro-pulses).

        The actuator back-drives (slack returns) after the glide stops. A
        continuous integral trim can't correct that on this stick-slip actuator:
        below the breakaway it does nothing, above it the slow load cell can't
        catch the motion before it runs away (windup -> lurch into over-tension).
        Instead: wait out the fast slack-return, then nudge the load into
        [AIM_LO, AIM_HI] with short OPEN-LOOP micro-pulses, re-measuring AT REST
        between each (so the slow sensor is an asset, not a liability). Pulse size
        adapts to the random stick-slip. Stopped by jog/tare/start-pull/cancel.
        """
        settle = max(0.0, float(PRELOAD_GLIDE_HOLD_SETTLE_S))
        aim_lo = float(PRELOAD_GLIDE_HOLD_AIM_LO_LBS)
        aim_hi = float(PRELOAD_GLIDE_HOLD_AIM_HI_LBS)
        gentle_gap = max(0.0, float(PRELOAD_GLIDE_HOLD_GENTLE_GAP_LBS))
        pulse_min = max(1, int(PRELOAD_GLIDE_HOLD_PULSE_MIN_US))
        pulse_max = max(pulse_min, int(PRELOAD_GLIDE_HOLD_PULSE_MAX_US))
        pulse_us = min(pulse_max, max(pulse_min, int(PRELOAD_GLIDE_HOLD_PULSE_US)))
        pulse_ms = max(10, int(PRELOAD_GLIDE_HOLD_PULSE_MS))
        pulse_ms_max = max(pulse_ms, int(PRELOAD_GLIDE_HOLD_PULSE_MS_MAX))
        rest_s = max(0.2, float(PRELOAD_GLIDE_HOLD_REST_S))
        max_iters = max(1, int(PRELOAD_GLIDE_HOLD_MAX_ITERS))
        abort_hi = float(PRELOAD_GLIDE_HOLD_ABORT_LBS)
        deadline = time.monotonic() + max(1.0, float(PRELOAD_GLIDE_HOLD_TIMEOUT_S))
        # Taking up slack (raising the load) is a pulse BELOW neutral on this
        # pull-up rig; derive the sign from the actuator config.
        physical_tension = self.actuator._maybe_invert(self.actuator.pull_direction)
        sign = 1 if physical_tension == "down" else -1

        def pull_or_lost_ownership_locked():
            # A pull owns the actuator (test_running), or ownership has moved on
            # (a jog/Stop/new-auto bumped the epoch, or the hold was cancelled).
            # In every case the hold must hand off and command NOTHING -- issuing
            # even a neutral/stop would stomp the new owner (the jog-stomp bug).
            return (
                self.state.get("test_running")
                or not self._owns_actuator_locked(epoch)
                or not self.preload_hold_active
                or self.state.get("auto_preload_running")
            )

        def sensor_fault_locked():
            # We still own the actuator but the load cell went bad: self-stop.
            return self.state.get("auto_preload_sensor_fault")

        def handoff_or_selfstop_locked():
            """Under lock: yield the hold if needed. Returns 'handoff' (command
            NOTHING -- a new owner has the actuator), 'selfstop' (we still own and
            stopped it for a sensor fault), or None to keep holding."""
            if pull_or_lost_ownership_locked():
                self.preload_hold_trim_us = 0
                self.preload_hold_active = False
                return "handoff"
            if sensor_fault_locked():
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
                self.preload_hold_trim_us = 0
                self.preload_hold_active = False
                return "selfstop"
            return None

        def sleep_checked(seconds):
            """Sleep in slices; yield (return True) if ownership changed / fault."""
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                time.sleep(min(0.2, max(0.01, end - time.monotonic())))
                with self.lock:
                    if handoff_or_selfstop_locked():
                        return True
            return False

        def settled_load():
            """Median of a few at-rest scan reads (the slow sensor is fine here)."""
            vals = []
            for _ in range(5):
                time.sleep(0.15)
                with self.lock:
                    vals.append(float(self.state.get("current_load") or 0.0))
            vals.sort()
            return vals[len(vals) // 2]

        # 1) Settle: sit at neutral while the fast slack-return / ring-down decays.
        if sleep_checked(settle):
            return
        with self.lock:
            self._record_auto_preload_trace_locked(
                "hold_settle_done", load=self.state.get("current_load")
            )

        # 2) Verify: discrete open-loop micro-pulses, re-measuring at rest.
        for _ in range(max_iters):
            if time.monotonic() > deadline:
                break
            with self.lock:
                if handoff_or_selfstop_locked():
                    return
            m = settled_load()
            if m > abort_hi:
                with self.lock:
                    # A jog/Stop/pull may have taken over during settled_load();
                    # only act on the over-tension while we still own the actuator.
                    if pull_or_lost_ownership_locked():
                        self.preload_hold_trim_us = 0
                        self.preload_hold_active = False
                        return
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    # Real over-tension: invalidate the seat so a pull can't start on
                    # a pre-tensioned specimen, and tell the operator to check tension.
                    self._clear_preload_ready_latch_locked()
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked("hold_abort_high", load=m)
                break
            if aim_lo <= m <= aim_hi:
                with self.lock:
                    self._record_auto_preload_trace_locked("hold_in_aim", load=m)
                break
            take_up = m < aim_lo  # True -> raise the load (reduce slack)
            gap = (aim_lo - m) if take_up else (m - aim_hi)
            this_ms = pulse_ms if gap >= gentle_gap else max(30, pulse_ms // 2)
            # below neutral raises load (take up slack); above neutral lowers it.
            pulse_dir = sign if take_up else -sign
            pulse_val = VICTOR_NEUTRAL_US + pulse_dir * pulse_us
            with self.lock:
                if handoff_or_selfstop_locked():
                    return
                self.actuator.set_pulse_us(pulse_val, command="hold_pulse")
                self.state["actuator_command"] = self.actuator.last_command
                self.preload_hold_trim_us = pulse_dir * pulse_us
                self._record_auto_preload_trace_locked(
                    "hold_pulse", load=m, dir=("up" if take_up else "down"),
                    pulse_us=pulse_val, amp_us=pulse_us, ms=this_ms,
                )
            time.sleep(this_ms / 1000.0)  # OPEN-LOOP fixed-duration pulse (no lock)
            with self.lock:
                # If a pull/jog/Stop/cancel landed during the open-loop pulse,
                # hand off WITHOUT commanding -- a neutral here would stomp the new
                # owner's command. This is the jog-stomp (BUG2) fix.
                if handoff_or_selfstop_locked():
                    return
                self.actuator.set_pulse_us(VICTOR_NEUTRAL_US, command="neutral")
                self.state["actuator_command"] = self.actuator.last_command
                self.preload_hold_trim_us = 0
            if sleep_checked(rest_s):
                return
            after = settled_load()
            moved = after - m
            with self.lock:
                self._record_auto_preload_trace_locked(
                    "hold_pulse_result", before=m, after=after, moved=round(moved, 3),
                )
            if abs(moved) < 0.03:
                # stiction didn't break (stochastic): bump amplitude, grow duration a little (capped)
                pulse_us = min(pulse_max, pulse_us + 4)
                pulse_ms = min(pulse_ms_max, pulse_ms + 15)
            elif abs(moved) > 0.30:
                # lurch: shrink hard so the next correction can't run away
                pulse_ms = max(40, pulse_ms // 2)
                pulse_us = max(pulse_min, pulse_us - 4)

        with self.lock:
            # Finished on our own terms: neutral the actuator only if we still own
            # it and no pull has taken over; otherwise hand off silently.
            if not pull_or_lost_ownership_locked():
                self.actuator.set_pulse_us(VICTOR_NEUTRAL_US, command="neutral")
                self.state["actuator_command"] = self.actuator.last_command
            self.preload_hold_trim_us = 0
            self.preload_hold_active = False
            self._record_auto_preload_trace_locked("hold_done", load=self.state.get("current_load"))

    def _start_glide_post_monitor_locked(self):
        """Keep logging load/actuator state to the trace after Auto Tension ends,
        to reveal post-tension drift, creep, gravity, or hold-trim behavior."""
        post_s = max(0.0, float(PRELOAD_GLIDE_POST_LOG_S))
        if post_s <= 0 or self.auto_preload_trace_file is None:
            return
        trace_file = self.auto_preload_trace_file
        deadline = time.monotonic() + post_s
        self._record_auto_preload_trace_locked(
            "post_start", load=self.state.get("current_load"), seconds=post_s
        )
        thread = threading.Thread(
            target=self._glide_post_monitor, args=(trace_file, deadline), daemon=True
        )
        self._glide_post_thread = thread
        thread.start()

    def _glide_post_monitor(self, trace_file, deadline):
        interval = max(0.05, float(PRELOAD_GLIDE_POST_LOG_INTERVAL_S))
        while time.monotonic() < deadline:
            time.sleep(interval)
            with self.lock:
                # Stop if a new Auto Tension rotated the trace file / is running,
                # or a pull test started.
                if self.auto_preload_trace_file is not trace_file:
                    return
                if self.state.get("auto_preload_running"):
                    return
                load = self.state.get("current_load")
                self._record_auto_preload_trace_locked(
                    "post",
                    load=load,
                    command=self.actuator.last_command,
                    pulse_us=self.actuator.last_pulse_us,
                    hold_active=self.preload_hold_active,
                    hold_trim_us=self.preload_hold_trim_us,
                )
                if self.state.get("test_running"):
                    self._record_auto_preload_trace_locked(
                        "post_end", load=load, reason="test_started"
                    )
                    return
        with self.lock:
            if self.auto_preload_trace_file is trace_file and not self.state.get("auto_preload_running"):
                self._record_auto_preload_trace_locked(
                    "post_end", load=self.state.get("current_load"), reason="timeout"
                )

    def _auto_preload_continuous_loop(self):
        deadline = time.monotonic() + PRELOAD_AUTO_TIMEOUT_SECONDS
        stable_since = None
        current_speed = 0.0
        command_direction = None
        last_speed_command = None
        last_update = time.monotonic()
        remembered_up_rate = 0.0
        remembered_up_rate_until = 0.0
        no_progress_since = None
        post_abort_recovery_until = 0.0
        post_abort_recovery_started = False
        hold_should_start = False
        try:
            while time.monotonic() < deadline:
                self._refresh_auto_preload_load(
                    control_speed_percent=current_speed,
                    control_direction=command_direction,
                )
                now = time.monotonic()
                direction = None
                with self.lock:
                    if self.state.get("auto_preload_sensor_fault"):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        command_direction = None
                        self._record_auto_preload_trace_locked(
                            "sensor_fault_stop",
                            load=self.state.get("current_load"),
                        )
                        break
                    if self.auto_preload_cancel_requested or not self.state.get("auto_preload_running") or not self._owns_actuator_locked(self.auto_preload_epoch):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        command_direction = None
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break
                    if self.state["test_running"]:
                        self.state["auto_preload_message"] = "Check tension"
                        command_direction = None
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break

                    load = float(self.state.get("current_load") or 0.0)
                    rate = self._auto_preload_load_rate_locked()
                    if rate >= PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND:
                        remembered_up_rate = max(remembered_up_rate, rate)
                        remembered_up_rate_until = now + self._auto_preload_up_rate_memory_seconds()
                    elif remembered_up_rate_until > now:
                        rate = max(rate, remembered_up_rate)
                    else:
                        remembered_up_rate = 0.0
                    if post_abort_recovery_until > 0:
                        self._auto_preload_stop_actuator_locked()
                        current_speed = 0.0
                        command_direction = None
                        last_speed_command = None
                        if PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS:
                            self._set_preload_ready_latch_locked(load)
                            hold_should_start = True
                            self.state["auto_preload_message"] = "Ready"
                            self._record_auto_preload_trace_locked(
                                "post_abort_recovery_ready",
                                load=load,
                                seconds=max(0.0, PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS - (post_abort_recovery_until - now)),
                            )
                            break
                        if load > PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS or now >= post_abort_recovery_until:
                            self.state["auto_preload_message"] = "Check tension"
                            self._record_auto_preload_trace_locked(
                                "post_abort_recovery_failed",
                                load=load,
                                recovery_max_lbs=PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS,
                                seconds=PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS,
                            )
                            break
                        self.state["auto_preload_message"] = "Settling"
                        if not post_abort_recovery_started:
                            self._record_auto_preload_trace_locked(
                                "post_abort_recovery_wait",
                                load=load,
                                seconds=PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS,
                            )
                            post_abort_recovery_started = True
                        time.sleep(self._auto_preload_continuous_poll_seconds())
                        continue
                    if self.auto_preload_near_band_seen and load > PRELOAD_MAX_LBS:
                        if load <= PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS:
                            self._auto_preload_stop_actuator_locked()
                            current_speed = 0.0
                            command_direction = None
                            last_speed_command = None
                            post_abort_recovery_until = now + max(0.0, float(PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS))
                            post_abort_recovery_started = False
                            self.state["auto_preload_message"] = "Settling"
                            self._record_auto_preload_trace_locked(
                                "post_band_settle_start",
                                load=load,
                                recovery_max_lbs=PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS,
                                seconds=PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS,
                            )
                            time.sleep(self._auto_preload_continuous_poll_seconds())
                            continue
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked(
                            "post_band_settle_failed",
                            load=load,
                            recovery_max_lbs=PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS,
                        )
                        break
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        if self._auto_preload_can_recover_post_band_locked(load):
                            self._auto_preload_stop_actuator_locked()
                            current_speed = 0.0
                            command_direction = None
                            last_speed_command = None
                            post_abort_recovery_until = now + max(0.0, float(PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS))
                            post_abort_recovery_started = False
                            self.state["auto_preload_message"] = "Settling"
                            self._record_auto_preload_trace_locked(
                                "post_abort_recovery_start",
                                load=load,
                                abort_lbs=PRELOAD_AUTO_ABORT_LBS,
                                recovery_max_lbs=PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS,
                                seconds=PRELOAD_AUTO_POST_ABORT_RECOVERY_SECONDS,
                            )
                            time.sleep(self._auto_preload_continuous_poll_seconds())
                            continue
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        command_direction = None
                        self._record_auto_preload_trace_locked("abort", load=load, abort_lbs=PRELOAD_AUTO_ABORT_LBS)
                        break

                    if self.auto_preload_control_hold_until > now:
                        self._auto_preload_stop_actuator_locked()
                        current_speed = 0.0
                        command_direction = None
                        last_speed_command = None
                        self.state["auto_preload_message"] = "Settling"
                        if not self.auto_preload_control_hold_logged:
                            self._record_auto_preload_trace_locked(
                                "control_settle_hold",
                                load=load,
                                remaining_s=self.auto_preload_control_hold_until - now,
                            )
                            self.auto_preload_control_hold_logged = True
                        last_update = now
                        time.sleep(self._auto_preload_continuous_poll_seconds())
                        continue
                    self.auto_preload_control_hold_logged = False

                    in_band = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
                    if in_band:
                        no_progress_since = None
                        self.auto_preload_near_band_seen = True
                        self._auto_preload_stop_actuator_locked()
                        current_speed = 0.0
                        command_direction = None
                        last_speed_command = None
                        if stable_since is None:
                            stable_since = now
                            self._hold_auto_preload_after_stop_locked(load, "target_band")
                            self._record_auto_preload_trace_locked(
                                "continuous_in_band",
                                load=load,
                                rate_lbs_per_s=rate,
                                min_lbs=PRELOAD_MIN_LBS,
                                max_lbs=PRELOAD_MAX_LBS,
                            )
                        scan_ready = self._auto_preload_scan_ready_locked()
                        ready = self._auto_preload_ready_locked() and scan_ready
                        if now - stable_since >= PRELOAD_AUTO_IN_BAND_END_SECONDS:
                            self.state["auto_preload_message"] = "Ready" if ready else ""
                            if ready:
                                self._set_preload_ready_latch_locked(load)
                            self._record_auto_preload_trace_locked(
                                "in_band_complete",
                                load=load,
                                seconds=now - stable_since,
                                ready=ready,
                                short_stable=self.state.get("auto_preload_short_stable"),
                                drift_stable=self.state.get("auto_preload_drift_stable"),
                                drift_drop_lbs=self.state.get("auto_preload_drift_drop_lbs"),
                                scan_ready=scan_ready,
                                scan_load=self.state.get("scan_load"),
                                scan_window_s=self.state.get("scan_load_window_s"),
                            )
                            if ready:
                                hold_should_start = True
                                break
                            stable_since = now
                        self.state["auto_preload_message"] = "Settling"
                    else:
                        stable_since = None
                        predicted_load = self._auto_preload_continuous_predicted_load_locked(load, rate, current_speed)
                        if load < PRELOAD_MIN_LBS:
                            if self._auto_preload_continuous_should_brake_locked(load, rate, predicted_load):
                                self._auto_preload_stop_actuator_locked()
                                current_speed = 0.0
                                command_direction = None
                                last_speed_command = None
                                self.state["auto_preload_message"] = "Settling"
                                self._hold_auto_preload_after_stop_locked(load, "predictive_brake")
                                self._record_auto_preload_trace_locked(
                                    "continuous_brake",
                                    load=load,
                                    predicted_load=predicted_load,
                                    rate_lbs_per_s=rate,
                                )
                            else:
                                direction = True
                        elif load > PRELOAD_MAX_LBS:
                            direction = False

                        if direction is not None:
                            no_progress_boost = 0.0
                            if direction:
                                if self._auto_preload_no_progress_locked(load, rate):
                                    if no_progress_since is None:
                                        no_progress_since = now
                                    elif now - no_progress_since >= PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_SECONDS:
                                        no_progress_boost = self._auto_preload_no_progress_floor_speed_locked(load)
                                else:
                                    no_progress_since = None
                            else:
                                no_progress_since = None
                            desired_speed = self._auto_preload_continuous_speed_locked(
                                load,
                                rate,
                                direction,
                                max_speed_override=no_progress_boost,
                                min_speed_override=no_progress_boost,
                            )
                            current_speed = self._auto_preload_slew_speed(
                                current_speed,
                                desired_speed,
                                now - last_update,
                            )
                            if direction:
                                current_speed = min(
                                    current_speed,
                                    self._auto_preload_progressive_max_speed_locked(
                                        load,
                                        rate,
                                        max_speed_override=no_progress_boost,
                                    ),
                                )
                            if current_speed < max(0.0, float(PRELOAD_AUTO_CONTINUOUS_CRAWL_STOP_SPEED_PERCENT)):
                                self._auto_preload_stop_actuator_locked()
                                current_speed = 0.0
                                command_direction = None
                                last_speed_command = None
                                self.state["auto_preload_message"] = "Settling"
                                self._hold_auto_preload_after_stop_locked(load, "near_band_crawl_stop")
                                self._record_auto_preload_trace_locked(
                                    "near_band_crawl_stop",
                                    load=load,
                                    rate_lbs_per_s=rate,
                                    predicted_load=predicted_load,
                                    desired_speed=desired_speed,
                                )
                                last_update = now
                                time.sleep(self._auto_preload_continuous_poll_seconds())
                                continue
                            command_speed = max(1, min(100, int(round(current_speed))))
                            if self._move_preload_direction_locked(direction, command_speed):
                                command_direction = direction
                                self.state["actuator_command"] = self.actuator.last_command
                            self.state["auto_preload_message"] = "Auto Tension"
                            if last_speed_command != command_speed:
                                self._record_auto_preload_trace_locked(
                                    "continuous_speed",
                                    load=load,
                                    rate_lbs_per_s=rate,
                                    predicted_load=predicted_load,
                                    increase=direction,
                                    desired_speed=desired_speed,
                                    speed_percent=command_speed,
                                    no_progress_boost=no_progress_boost,
                                )
                                last_speed_command = command_speed
                last_update = now
                time.sleep(self._auto_preload_continuous_poll_seconds())
            else:
                with self.lock:
                    self._auto_preload_stop_actuator_locked()
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "timeout",
                        load=self.state.get("current_load"),
                        seconds=PRELOAD_AUTO_TIMEOUT_SECONDS,
                    )
        finally:
            with self.lock:
                self._auto_preload_stop_actuator_locked()
                self.load_cell.samples.clear()
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "") == "Ready":
                    self.state["auto_preload_message"] = ""
                if hold_should_start and not self.auto_preload_cancel_requested and self._owns_actuator_locked(self.auto_preload_epoch):
                    self._start_preload_hold_locked()
                self._record_auto_preload_trace_locked(
                    "finish",
                    load=self.state.get("current_load"),
                    message=self.state.get("auto_preload_message"),
                )

    def _auto_preload_continuous_poll_seconds(self):
        return max(0.01, float(PRELOAD_AUTO_CONTINUOUS_POLL_SECONDS))

    def _auto_preload_pulse_loop(self):
        deadline = time.monotonic() + PRELOAD_AUTO_TIMEOUT_SECONDS
        stable_since = None
        hold_should_start = False
        try:
            while time.monotonic() < deadline:
                direction = None
                pulse_seconds = 0.0
                self._refresh_auto_preload_load()
                with self.lock:
                    if self.state.get("auto_preload_sensor_fault"):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked(
                            "sensor_fault_stop",
                            load=self.state.get("current_load"),
                        )
                        break
                    if self.auto_preload_cancel_requested or not self.state.get("auto_preload_running") or not self._owns_actuator_locked(self.auto_preload_epoch):
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break
                    if self.state["test_running"]:
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break

                    load = float(self.state.get("current_load") or 0.0)
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("abort", load=load, abort_lbs=PRELOAD_AUTO_ABORT_LBS)
                        break

                    direction = self._auto_preload_direction_for_load(load)
                    if direction is None:
                        self._auto_preload_stop_actuator_locked()
                        now = time.monotonic()
                        in_band = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
                        near_band_hold = self._auto_preload_near_band_hold_locked(load)
                        if in_band:
                            self.auto_preload_near_band_seen = True
                        scan_ready = self._auto_preload_scan_ready_locked()
                        ready = in_band and self._auto_preload_ready_locked() and scan_ready
                        if in_band:
                            if stable_since is None:
                                stable_since = now
                            if now - stable_since >= PRELOAD_AUTO_IN_BAND_END_SECONDS:
                                self.state["auto_preload_message"] = "Ready" if ready else ""
                                if ready:
                                    self._set_preload_ready_latch_locked(load)
                                self._record_auto_preload_trace_locked(
                                    "in_band_complete",
                                    load=load,
                                    seconds=now - stable_since,
                                    ready=ready,
                                    short_stable=self.state.get("auto_preload_short_stable"),
                                    drift_stable=self.state.get("auto_preload_drift_stable"),
                                    drift_drop_lbs=self.state.get("auto_preload_drift_drop_lbs"),
                                    scan_ready=scan_ready,
                                    scan_load=self.state.get("scan_load"),
                                    scan_window_s=self.state.get("scan_load_window_s"),
                                )
                                if ready:
                                    hold_should_start = True
                                    break
                                stable_since = now
                            self.state["auto_preload_message"] = "Settling"
                        elif near_band_hold:
                            stable_since = None
                            self.state["auto_preload_message"] = "Settling"
                            self._record_auto_preload_trace_locked(
                                "near_band_hold",
                                load=load,
                                min_lbs=PRELOAD_MIN_LBS,
                                margin_lbs=PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS,
                            )
                        else:
                            stable_since = None
                            self.state["auto_preload_message"] = "Settling"
                    elif self._auto_preload_should_wait_for_settle_locked(load, direction):
                        predicted_load = self._auto_preload_predicted_load_locked(load, direction)
                        direction = None
                        stable_since = None
                        self._auto_preload_stop_actuator_locked()
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "waiting_load_stable",
                            load=load,
                            rate_lbs_per_s=self._auto_preload_load_rate_locked(),
                            predicted_load=predicted_load,
                        )
                    else:
                        stage = self._auto_preload_stage_for_load(load, direction)
                        stage = self._auto_preload_adjust_stage_for_slope_locked(stage, load, direction)
                        pulse_seconds = stage["pulse_seconds"]
                        self._move_preload_direction_locked(
                            increase=direction, speed_percent=stage["speed_percent"]
                        )
                        if not self.state.get("test_running"):
                            self.state["actuator_command"] = self.actuator.last_command
                        stable_since = None
                        self.state["auto_preload_message"] = stage["message"]

                if direction is None:
                    time.sleep(0.1)
                    continue

                if not self._run_auto_preload_pulse(direction, stage, deadline):
                    break
                self._wait_for_auto_preload_settle(
                    deadline,
                    coarse=stage.get("coarse", False),
                    approach=stage.get("approach_settle", False),
                    fast_contact=stage.get("fast_settle", False),
                )
            else:
                with self.lock:
                    self._auto_preload_stop_actuator_locked()
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "timeout",
                        load=self.state.get("current_load"),
                        seconds=PRELOAD_AUTO_TIMEOUT_SECONDS,
                    )
        finally:
            with self.lock:
                self._auto_preload_stop_actuator_locked()
                self.load_cell.samples.clear()
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "") == "Ready":
                    self.state["auto_preload_message"] = ""
                if hold_should_start and not self.auto_preload_cancel_requested and self._owns_actuator_locked(self.auto_preload_epoch):
                    self._start_preload_hold_locked()
                self._record_auto_preload_trace_locked(
                    "finish",
                    load=self.state.get("current_load"),
                    message=self.state.get("auto_preload_message"),
                )

    def _reset_auto_preload_control_locked(self):
        self.auto_preload_coast_lbs = 0.0
        self.auto_preload_last_stop_load = None
        self.auto_preload_last_stop_increase = None
        self.auto_preload_contact_detected = False
        self.auto_preload_near_band_seen = False
        self.auto_preload_initial_stop_seen = False
        self.auto_preload_final_approach_stop_seen = False
        self.auto_preload_control_rejects = 0
        self.auto_preload_control_hold_until = 0.0
        self.auto_preload_control_hold_logged = False
        self.auto_preload_control_last_load = None
        self.auto_preload_control_last_time = None

    def _auto_preload_stop_actuator_locked(self):
        if self.state.get("test_running"):
            self._record_auto_preload_trace_locked(
                "auto_stop_ignored_during_pull",
                load=self.state.get("current_load"),
                command=self.actuator.last_command,
                pulse_us=self.actuator.last_pulse_us,
            )
            return False
        if not self._owns_actuator_locked(self.auto_preload_epoch):
            # A jog/Stop/new run took the actuator (bumped the epoch) after this
            # auto run started: don't command it -- the new owner already has it.
            self._record_auto_preload_trace_locked(
                "auto_stop_ignored_lost_ownership",
                load=self.state.get("current_load"),
                command=self.actuator.last_command,
            )
            return False
        ok = self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command
        return ok

    def _clear_auto_preload_status_locked(self):
        self.state["auto_preload_running"] = False
        self.state["auto_preload_message"] = ""
        self.state["auto_preload_sensor_fault"] = False
        self.state["auto_preload_short_stable"] = False
        self.state["auto_preload_drift_stable"] = False
        self.state["auto_preload_drift_drop_lbs"] = 0.0
        self.state["auto_preload_drift_window_s"] = 0.0

    def _start_preload_hold_locked(self):
        if not PRELOAD_HOLD_TRIM_ENABLED or self.state.get("test_running"):
            return
        if self.preload_hold_active:
            return
        self.preload_hold_active = True
        self.preload_hold_trim_us = 0
        epoch = self._bump_actuator_epoch_locked()
        self.preload_hold_thread = threading.Thread(
            target=self._preload_hold_loop, args=(epoch,), daemon=True
        )
        self.preload_hold_thread.start()
        self._record_auto_preload_trace_locked(
            "hold_start",
            load=self.state.get("current_load"),
            neutral_us=VICTOR_NEUTRAL_US,
        )

    def _stop_preload_hold_locked(self):
        if self.preload_hold_active:
            self._record_auto_preload_trace_locked(
                "hold_stop",
                load=self.state.get("current_load"),
                trim_us=self.preload_hold_trim_us,
            )
        self.preload_hold_active = False
        self.preload_hold_trim_us = 0
        self._bump_actuator_epoch_locked()
        self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command

    def _preload_hold_loop(self, epoch):
        while True:
            time.sleep(max(0.05, PRELOAD_HOLD_TRIM_INTERVAL_SECONDS))
            with self.lock:
                # Pull owns the actuator, or ownership moved on (jog/Stop/new-auto
                # bumped the epoch, or the hold was cancelled): hand off, command
                # NOTHING -- a stop here would stomp the new owner (jog-stomp bug).
                if (
                    self.state.get("test_running")
                    or not self._owns_actuator_locked(epoch)
                    or not self.preload_hold_active
                    or self.state.get("auto_preload_running")
                ):
                    self.preload_hold_trim_us = 0
                    self.preload_hold_active = False
                    return
                # We still own it but the load cell went bad: self-stop.
                if self.state.get("auto_preload_sensor_fault"):
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    self.preload_hold_trim_us = 0
                    self.preload_hold_active = False
                    return
                self._preload_hold_update_locked()

    def _preload_hold_update_locked(self):
        load = float(self.state.get("current_load") or 0.0)
        rate = self._auto_preload_signed_load_rate_locked()
        if self.state.get("preload_ready_latched"):
            recovery_min = PRELOAD_MIN_LBS - max(0.0, float(PRELOAD_READY_LATCH_MARGIN_LBS))
            recovery_max = PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS
        else:
            recovery_min = PRELOAD_MIN_LBS
            recovery_max = PRELOAD_MAX_LBS
        if load < recovery_min or load > recovery_max:
            self.preload_hold_trim_us = 0
            self.preload_hold_active = False
            self.actuator.stop()
            self.state["actuator_command"] = self.actuator.last_command
            if not self.state.get("auto_preload_running"):
                self.state["auto_preload_message"] = ""
            self._record_auto_preload_trace_locked(
                "hold_out_of_band",
                load=load,
            )
            return

        previous_trim = self.preload_hold_trim_us
        hold_target = min(PRELOAD_TARGET_LBS, PRELOAD_AUTO_TARGET_LBS)
        if load > PRELOAD_MAX_LBS:
            self.preload_hold_trim_us = max(
                -max(0, int(PRELOAD_HOLD_TRIM_MAX_US)),
                self.preload_hold_trim_us - max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
            )
        elif PRELOAD_MIN_LBS <= load < hold_target:
            if rate <= -PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND or self.preload_hold_trim_us > 0:
                self.preload_hold_trim_us = min(
                    max(0, int(PRELOAD_HOLD_TRIM_MAX_US)),
                    self.preload_hold_trim_us + max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
                )
        else:
            self.preload_hold_trim_us = max(
                0,
                self.preload_hold_trim_us - max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
            ) if self.preload_hold_trim_us >= 0 else min(
                0,
                self.preload_hold_trim_us + max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
            )

        hold_us = VICTOR_NEUTRAL_US + self.preload_hold_trim_us
        self.actuator.set_pulse_us(hold_us, command="hold_trim" if self.preload_hold_trim_us else "neutral")
        self.state["actuator_command"] = self.actuator.last_command
        if self.preload_hold_trim_us != previous_trim:
            self._record_auto_preload_trace_locked(
                "hold_trim",
                load=load,
                rate_lbs_per_s=rate,
                trim_us=self.preload_hold_trim_us,
                pulse_us=hold_us,
            )

    def _reset_test_session_locked(self):
        self.failure_drop_samples = 0
        self.state["test_running"] = False
        self.state["test_complete"] = False
        self.state["active_test_id"] = None
        self.state["started_at_monotonic"] = None
        self.state["elapsed_s"] = 0.0
        self.state["sample_count"] = 0
        self.state["stop_reason"] = ""
        self.state["stop_pending"] = False
        self.state["stop_pending_started_at"] = None

    def _auto_preload_direction_for_load(self, load):
        if self._auto_preload_near_band_hold_locked(load):
            return None
        if load < PRELOAD_MIN_LBS:
            return True
        if load > PRELOAD_MAX_LBS:
            return False
        return None

    def _auto_preload_stage_for_load(self, load, increase):
        if not increase:
            return {
                "coarse": False,
                "max_delta_lbs": PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
                "speed_percent": PRELOAD_AUTO_SPEED_PERCENT,
                "pulse_seconds": self._auto_preload_down_pulse_seconds(),
                "message": "Auto Tension",
            }

        for threshold, speed_percent, pulse_seconds in PRELOAD_AUTO_TENSION_STAGES:
            if load < threshold:
                coarse = self._auto_preload_coarse_active_locked(load, increase)
                if self._auto_preload_contact_mode_active_locked(load):
                    return {
                        "coarse": False,
                        "contact": True,
                        "fast_settle": load < PRELOAD_AUTO_COARSE_UNTIL_LBS,
                        "approach_settle": load < PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS,
                        "max_delta_lbs": PRELOAD_AUTO_CONTACT_MAX_DELTA_LBS,
                        "speed_percent": min(speed_percent, PRELOAD_AUTO_CONTACT_SPEED_PERCENT),
                        "pulse_seconds": max(
                            PRELOAD_AUTO_MIN_PULSE_SECONDS,
                            min(self._auto_preload_configured_pulse_seconds(pulse_seconds), PRELOAD_AUTO_CONTACT_PULSE_SECONDS),
                        ),
                        "message": "Auto Tension",
                    }
                if self._auto_preload_contact_coarse_active_locked(load, increase):
                    return {
                        "coarse": True,
                        "contact_coarse": True,
                        "fast_settle": True,
                        "approach_settle": load < PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS,
                        "max_delta_lbs": PRELOAD_AUTO_CONTACT_COARSE_MAX_DELTA_LBS,
                        "speed_percent": min(speed_percent, PRELOAD_AUTO_CONTACT_COARSE_SPEED_PERCENT),
                        "pulse_seconds": max(
                            PRELOAD_AUTO_MIN_PULSE_SECONDS,
                            min(
                                self._auto_preload_configured_pulse_seconds(pulse_seconds),
                                PRELOAD_AUTO_CONTACT_COARSE_PULSE_SECONDS,
                            ),
                        ),
                        "message": "Auto Tension",
                    }
                return {
                    "coarse": coarse,
                    "approach_settle": load < PRELOAD_AUTO_APPROACH_SETTLE_UNTIL_LBS,
                    "max_delta_lbs": self._auto_preload_max_delta_lbs(load, coarse),
                    "speed_percent": speed_percent,
                    "pulse_seconds": self._auto_preload_configured_pulse_seconds(pulse_seconds),
                    "message": "Auto Tension",
                }

        return {
            "coarse": False,
            "approach_settle": False,
            "max_delta_lbs": PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
            "speed_percent": PRELOAD_AUTO_SPEED_PERCENT,
            "pulse_seconds": self._auto_preload_pulse_seconds(),
            "message": "Auto Tension",
        }

    def _auto_preload_coarse_active_locked(self, load, increase):
        return bool(increase and load < PRELOAD_AUTO_COARSE_UNTIL_LBS)

    def _auto_preload_contact_mode_active_locked(self, load):
        return bool(self.auto_preload_contact_detected and load >= PRELOAD_AUTO_CONTACT_MODE_START_LBS)

    def _auto_preload_contact_coarse_active_locked(self, load, increase):
        return bool(
            increase
            and self.auto_preload_contact_detected
            and load < PRELOAD_AUTO_CONTACT_MODE_START_LBS
        )

    def _auto_preload_near_band_hold_locked(self, load):
        return bool(
            self.auto_preload_near_band_seen
            and PRELOAD_MIN_LBS - PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS <= load < PRELOAD_MIN_LBS
        )

    def _auto_preload_should_wait_for_settle_locked(self, load, increase):
        if self._auto_preload_coarse_active_locked(load, increase):
            return False
        if self._auto_preload_load_stable_locked():
            return False
        if not increase:
            return True
        if self._auto_preload_negative_jump_hold_locked(load):
            return True

        predicted_load = self._auto_preload_predicted_load_locked(load, increase)
        if predicted_load >= PRELOAD_MIN_LBS:
            self.auto_preload_near_band_seen = True
            self._record_auto_preload_trace_locked(
                "predicted_settle_hold",
                load=load,
                predicted_load=predicted_load,
                min_lbs=PRELOAD_MIN_LBS,
                rate_lbs_per_s=self._auto_preload_load_rate_locked(),
            )
            return True

        distance_to_band = PRELOAD_MIN_LBS - float(load)
        return bool(
            distance_to_band <= PRELOAD_AUTO_APPROACH_DISTANCE_LBS
            and self._auto_preload_load_rate_locked() >= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND
        )

    def _auto_preload_predicted_load_locked(self, load, increase=True):
        rate = self._auto_preload_load_rate_locked()
        stop_margin = self._auto_preload_stop_margin_locked() if increase else 0.0
        return float(load) + max(0.0, rate) * PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS + stop_margin

    def _auto_preload_continuous_predicted_load_locked(self, load, rate, speed_percent):
        speed_margin = (max(0.0, float(speed_percent)) / 100.0) * PRELOAD_AUTO_CONTINUOUS_BRAKE_MARGIN_LBS
        return float(load) + max(0.0, float(rate)) * PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS + speed_margin

    def _auto_preload_up_rate_memory_seconds(self):
        return max(
            PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS,
            PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS * 2.5,
        )

    def _auto_preload_continuous_should_brake_locked(self, load, rate, predicted_load):
        if float(load) < float(PRELOAD_AUTO_PREDICT_ENABLE_LBS):
            return False
        if self.auto_preload_final_approach_stop_seen and float(load) >= PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS:
            if predicted_load >= PRELOAD_MAX_LBS or rate >= PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND:
                self._record_auto_preload_trace_locked(
                    "final_crawl_brake",
                    load=load,
                    predicted_load=predicted_load,
                    rate_lbs_per_s=rate,
                    max_lbs=PRELOAD_MAX_LBS,
                )
                return True
            return False
        target_lbs = self._auto_preload_continuous_brake_target_locked()
        if predicted_load >= target_lbs:
            if self._auto_preload_should_creep_after_final_brake_locked(load, predicted_load, target_lbs):
                return False
            if self._auto_preload_final_prediction_gate_locked(load):
                self.auto_preload_initial_stop_seen = True
                self.auto_preload_final_approach_stop_seen = True
                self._record_auto_preload_trace_locked(
                    "final_approach_stop_target",
                    load=load,
                    predicted_load=predicted_load,
                    target_lbs=target_lbs,
                )
            else:
                self._record_auto_preload_trace_locked(
                    "prediction_brake_before_final_gate",
                    load=load,
                    predicted_load=predicted_load,
                    target_lbs=target_lbs,
                    gate_lbs=self._auto_preload_final_prediction_gate_lbs_locked(),
                )
                if not self._auto_preload_close_to_final_prediction_gate_locked(load):
                    return False
            return True
        if (
            load >= PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_START_LBS
            and rate >= PRELOAD_AUTO_CONTINUOUS_COAST_BRAKE_RATE_LBS_PER_SECOND
        ):
            return True
        if (
            load >= target_lbs - PRELOAD_AUTO_APPROACH_DISTANCE_LBS
            and rate >= PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND
        ):
            return True
        return False

    def _auto_preload_final_prediction_gate_lbs_locked(self):
        return min(float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS), float(PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS))

    def _auto_preload_final_prediction_gate_locked(self, load):
        return float(load) >= self._auto_preload_final_prediction_gate_lbs_locked()

    def _auto_preload_close_to_final_prediction_gate_locked(self, load):
        gate_lbs = self._auto_preload_final_prediction_gate_lbs_locked()
        margin_lbs = max(0.1, min(0.4, float(PRELOAD_AUTO_APPROACH_DISTANCE_LBS) * 0.5))
        return float(load) >= gate_lbs - margin_lbs

    def _auto_preload_should_creep_after_final_brake_locked(self, load, predicted_load, target_lbs):
        if not self.auto_preload_final_approach_stop_seen:
            return False
        rebrake_load = float(target_lbs) - max(0.0, float(PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS))
        return bool(float(load) < rebrake_load and float(predicted_load) < PRELOAD_MIN_LBS)

    def _auto_preload_continuous_brake_target_locked(self):
        return min(PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS, PRELOAD_MIN_LBS)

    def _auto_preload_continuous_speed_locked(self, load, rate, increase, max_speed_override=0.0, min_speed_override=0.0):
        target_lbs = self._auto_preload_continuous_brake_target_locked() if increase else PRELOAD_AUTO_TARGET_LBS
        if increase:
            control_target_lbs = PRELOAD_MIN_LBS if self.auto_preload_final_approach_stop_seen else target_lbs
            error_lbs = max(0.0, control_target_lbs - float(load))
            damping = max(0.0, float(rate)) * PRELOAD_AUTO_CONTINUOUS_KD
            raw_speed = (error_lbs * PRELOAD_AUTO_CONTINUOUS_KP) - damping
            if load >= PRELOAD_MIN_LBS - PRELOAD_AUTO_APPROACH_DISTANCE_LBS:
                distance_scale = max(0.0, min(1.0, error_lbs / max(0.05, PRELOAD_AUTO_APPROACH_DISTANCE_LBS)))
                raw_speed *= distance_scale
        else:
            error_lbs = max(0.0, float(load) - target_lbs)
            raw_speed = error_lbs * (PRELOAD_AUTO_CONTINUOUS_KP * 0.5)

        min_speed = max(1.0, float(PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT))
        max_speed = max(min_speed, float(PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT))
        if increase:
            slowdown_lbs = max(0.1, float(PRELOAD_AUTO_CONTINUOUS_SLOWDOWN_LBS))
            max_speed = max(min_speed, max_speed * max(0.0, min(1.0, error_lbs / slowdown_lbs)))
            if rate > 0:
                rate_window = max(0.05, float(PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND) * 4.0)
                rate_scale = max(0.25, 1.0 - min(1.0, float(rate) / rate_window))
                max_speed = max(min_speed, max_speed * rate_scale)
            max_speed = min(
                max_speed,
                self._auto_preload_progressive_max_speed_locked(load, rate, target_lbs, max_speed_override),
            )
            if max_speed_override:
                max_speed = max(max_speed, float(max_speed_override))
            if min_speed_override and load < PRELOAD_MIN_LBS:
                raw_speed = max(raw_speed, min(max_speed, float(min_speed_override)))
            min_speed = min(min_speed, max_speed)
            distance_to_band = max(0.0, PRELOAD_MIN_LBS - float(load))
            crawl_zone = max(0.0, float(PRELOAD_AUTO_CONTINUOUS_CRAWL_ZONE_LBS))
            if crawl_zone > 0 and distance_to_band <= crawl_zone:
                scale = max(0.0, min(1.0, distance_to_band / crawl_zone))
                raw_speed *= scale
                if raw_speed <= max(0.0, float(PRELOAD_AUTO_CONTINUOUS_CRAWL_STOP_SPEED_PERCENT)):
                    return 0.0
                crawl_min = max(0.0, float(PRELOAD_AUTO_CONTINUOUS_CRAWL_MIN_SPEED_PERCENT))
                crawl_max = max(crawl_min, float(PRELOAD_AUTO_CONTINUOUS_CRAWL_MAX_SPEED_PERCENT))
                max_speed = min(max_speed, crawl_max)
                min_speed = min(crawl_min, max_speed)
            final_floor = self._auto_preload_final_pull_floor_speed_locked(load)
            if final_floor > 0:
                max_speed = max(max_speed, final_floor)
                min_speed = min(max(min_speed, final_floor), max_speed)
                raw_speed = max(raw_speed, final_floor)
        return max(min_speed, min(max_speed, raw_speed))

    def _auto_preload_final_pull_floor_speed_locked(self, load):
        load = float(load)
        if load < float(PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_FLOOR_START_LBS):
            return 0.0
        if load >= PRELOAD_MIN_LBS - max(0.0, float(PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_STOP_MARGIN_LBS)):
            return 0.0
        return max(0.0, float(PRELOAD_AUTO_CONTINUOUS_FINAL_PULL_MIN_SPEED_PERCENT))

    def _auto_preload_progressive_max_speed_locked(self, load, rate, target_lbs=None, max_speed_override=0.0):
        target_lbs = self._auto_preload_continuous_brake_target_locked() if target_lbs is None else float(target_lbs)
        points = [
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT)),
            (float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS), float(PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT)),
        ]
        load = float(load)
        curve = max(0.1, float(PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_CURVE))
        early_threshold, early_speed = points[0]
        final_threshold, final_speed = points[-1]
        if load <= early_threshold:
            slack_span = max(0.5, abs(early_threshold - target_lbs) * 0.35)
            slack_start = early_threshold - slack_span
            fraction = max(0.0, min(1.0, (load - slack_start) / max(0.001, slack_span)))
            shaped = pow(fraction, curve)
            cap = float(PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT) + (
                (early_speed - float(PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT)) * shaped
            )
        elif load >= final_threshold:
            cap = final_speed
        else:
            cap = final_speed
            for (lower_threshold, lower_speed), (upper_threshold, upper_speed) in zip(points, points[1:]):
                if lower_threshold <= load <= upper_threshold:
                    span = max(0.001, upper_threshold - lower_threshold)
                    fraction = max(0.0, min(1.0, (load - lower_threshold) / span))
                    shaped = pow(fraction, curve)
                    cap = lower_speed + ((upper_speed - lower_speed) * shaped)
                    break
        if load < early_threshold:
            slack_span = max(0.1, abs(early_threshold - target_lbs))
            fraction = max(0.0, min(1.0, (target_lbs - load) / slack_span))
            cap = min(cap, early_speed + ((float(PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT) - early_speed) * fraction))
        if rate > 0:
            rate_scale = max(
                0.35,
                1.0 - min(0.65, (float(rate) / max(0.05, PRELOAD_AUTO_CONTINUOUS_PROGRESSIVE_RATE_SCALE)) * 0.25),
            )
            cap *= rate_scale
        return max(1.0, float(max(cap, float(max_speed_override or 0.0))))

    def _auto_preload_sensor_paced_max_speed_locked(self, load, max_speed_override=0.0):
        if load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINE_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_APPROACH_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_MID_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_START_MAX_SPEED_PERCENT
        elif load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_LBS:
            base = PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_EARLY_MAX_SPEED_PERCENT
        else:
            base = PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT
        return max(1.0, float(max(float(base), float(max_speed_override or 0.0))))

    def _auto_preload_no_progress_locked(self, load, rate):
        return bool(
            load < PRELOAD_MIN_LBS
            and load >= PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_FINAL_LBS
            and load < PRELOAD_AUTO_PREDICT_ENABLE_LBS
            and load < PRELOAD_AUTO_CONTINUOUS_SENSOR_PACE_CRAWL_LBS
            and load < PRELOAD_AUTO_FINAL_APPROACH_STOP_LBS - max(0.0, PRELOAD_AUTO_FINAL_REBRAKE_MARGIN_LBS)
            and abs(float(rate)) <= PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_RATE_LBS_PER_SECOND
        )

    def _auto_preload_no_progress_floor_speed_locked(self, load):
        final_floor = self._auto_preload_final_pull_floor_speed_locked(load)
        if final_floor > 0:
            return min(float(PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT), final_floor)
        safe_zone_speed = self._auto_preload_sensor_paced_max_speed_locked(load)
        crawl_escape_speed = float(PRELOAD_AUTO_CONTINUOUS_CRAWL_MAX_SPEED_PERCENT) + 1.5
        requested_speed = max(safe_zone_speed, crawl_escape_speed)
        return min(float(PRELOAD_AUTO_CONTINUOUS_NO_PROGRESS_BOOST_SPEED_PERCENT), requested_speed)

    def _auto_preload_slew_speed(self, current_speed, desired_speed, elapsed_s):
        max_step = max(0.0, PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND) * max(0.0, float(elapsed_s))
        if max_step <= 0:
            return float(desired_speed)
        delta = float(desired_speed) - float(current_speed)
        if abs(delta) <= max_step:
            return float(desired_speed)
        return float(current_speed) + (max_step if delta > 0 else -max_step)

    def _auto_preload_negative_jump_hold_locked(self, load):
        now = time.monotonic()
        cutoff = now - max(0.2, PRELOAD_AUTO_RATE_WINDOW_SECONDS)
        samples = [(sample_time, value) for sample_time, value in self.load_history if sample_time >= cutoff]
        if len(samples) < 3:
            return False

        previous_values = [value for _, value in samples[:-1]]
        if not previous_values:
            return False

        recent_best_load = max(previous_values)
        if recent_best_load < PRELOAD_AUTO_NEGATIVE_JUMP_GUARD_START_LBS:
            return False

        drop_lbs = recent_best_load - float(load)
        if drop_lbs < PRELOAD_AUTO_NEGATIVE_JUMP_DELTA_LBS:
            return False

        self._record_auto_preload_trace_locked(
            "negative_jump_hold",
            load=load,
            recent_best_load=recent_best_load,
            drop_lbs=drop_lbs,
        )
        return True

    def _auto_preload_max_delta_lbs(self, load, coarse):
        if coarse:
            return PRELOAD_AUTO_COARSE_MAX_DELTA_LBS
        if load < PRELOAD_MIN_LBS:
            return PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS
        return PRELOAD_AUTO_FINAL_MAX_DELTA_LBS

    def _auto_preload_adjust_stage_for_slope_locked(self, stage, load, increase):
        if not increase or stage.get("coarse"):
            return stage

        rate = max(0.0, self._auto_preload_load_rate_locked())
        stop_margin = self._auto_preload_stop_margin_locked()
        distance_to_band = max(0.0, PRELOAD_MIN_LBS - float(load))
        should_adapt = (
            rate >= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND
            or distance_to_band <= PRELOAD_AUTO_APPROACH_DISTANCE_LBS + stop_margin
            or self.auto_preload_coast_lbs > PRELOAD_AUTO_MIN_STOP_MARGIN_LBS
        )
        if not should_adapt:
            return stage

        adjusted = dict(stage)
        scale = 1.0
        if distance_to_band > 0:
            scale = min(scale, max(PRELOAD_AUTO_ADAPTIVE_PULSE_MIN_SCALE, distance_to_band / (distance_to_band + stop_margin)))
        if rate >= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND:
            scale = min(scale, 0.5)
        if self.auto_preload_coast_lbs > PRELOAD_AUTO_MIN_STOP_MARGIN_LBS:
            scale = min(scale, max(PRELOAD_AUTO_ADAPTIVE_PULSE_MIN_SCALE, 1.0 - (self.auto_preload_coast_lbs * 0.5)))

        adjusted["pulse_seconds"] = max(PRELOAD_AUTO_MIN_PULSE_SECONDS, float(stage["pulse_seconds"]) * scale)
        adjusted["speed_percent"] = max(
            PRELOAD_AUTO_ADAPTIVE_SPEED_MIN_PERCENT,
            int(round(float(stage["speed_percent"]) * max(0.5, scale))),
        )
        adjusted["max_delta_lbs"] = min(float(stage.get("max_delta_lbs") or PRELOAD_AUTO_FINAL_MAX_DELTA_LBS), PRELOAD_AUTO_FINAL_MAX_DELTA_LBS)
        adjusted["adapted"] = True
        adjusted["stop_margin_lbs"] = stop_margin
        adjusted["rate_lbs_per_s"] = rate
        adjusted["message"] = "Auto Tension"
        self._record_auto_preload_trace_locked(
            "stage_adapted",
            load=load,
            rate_lbs_per_s=rate,
            stop_margin_lbs=stop_margin,
            scale=scale,
            speed_percent=adjusted["speed_percent"],
            pulse_seconds=adjusted["pulse_seconds"],
            coast_lbs=self.auto_preload_coast_lbs,
        )
        return adjusted

    def _auto_preload_stop_margin_locked(self):
        learned_margin = max(0.0, self.auto_preload_coast_lbs) * PRELOAD_AUTO_COAST_MARGIN_SCALE
        return min(
            PRELOAD_AUTO_MAX_STOP_MARGIN_LBS,
            max(PRELOAD_AUTO_MIN_STOP_MARGIN_LBS, learned_margin),
        )

    def _auto_preload_configured_pulse_seconds(self, pulse_seconds):
        return max(PRELOAD_AUTO_MIN_PULSE_SECONDS, float(pulse_seconds))

    def _auto_preload_down_pulse_seconds(self):
        return max(PRELOAD_AUTO_MIN_PULSE_SECONDS, PRELOAD_AUTO_DOWN_PULSE_SECONDS)

    def _auto_preload_pulse_seconds(self):
        return max(PRELOAD_AUTO_MIN_PULSE_SECONDS, PRELOAD_AUTO_PULSE_SECONDS)

    def _run_auto_preload_pulse(self, increase, stage, deadline):
        pulse_seconds = stage["pulse_seconds"]
        max_delta_lbs = max(0.0, float(stage.get("max_delta_lbs") or 0.0))
        end_time = min(time.monotonic() + pulse_seconds, deadline)
        check_interval = max(0.005, PRELOAD_AUTO_PULSE_CHECK_SECONDS)
        with self.lock:
            start_load = float(self.state.get("current_load") or 0.0)
            self._record_auto_preload_trace_locked(
                "pulse_start",
                load=start_load,
                increase=increase,
                speed_percent=stage.get("speed_percent"),
                pulse_seconds=pulse_seconds,
                max_delta_lbs=max_delta_lbs,
                coarse=stage.get("coarse", False),
                contact=stage.get("contact", False),
                contact_coarse=stage.get("contact_coarse", False),
            )
        try:
            while time.monotonic() < end_time:
                with self.lock:
                    if self.state.get("test_running"):
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked(
                            "pulse_cancelled",
                            load=self.state.get("current_load"),
                        )
                        return False
                time.sleep(min(check_interval, max(0.0, end_time - time.monotonic())))

            with self.lock:
                self._auto_preload_stop_actuator_locked()
            self._refresh_auto_preload_load()

            with self.lock:
                if self.state.get("auto_preload_sensor_fault"):
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "pulse_sensor_fault",
                        load=self.state.get("current_load"),
                    )
                    return False
                load = float(self.state.get("current_load") or 0.0)
                rate = self._auto_preload_load_rate_locked()
                stop_margin = self._auto_preload_stop_margin_locked() if increase else 0.0
                predicted_load = load + max(0.0, rate) * PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS + stop_margin
                if load > PRELOAD_AUTO_ABORT_LBS:
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "pulse_abort",
                        load=load,
                        abort_lbs=PRELOAD_AUTO_ABORT_LBS,
                    )
                    return False
                if increase:
                    delta_lbs = load - start_load
                    self._auto_preload_note_contact_locked(delta_lbs, load)
                    if load > PRELOAD_MAX_LBS:
                        self.auto_preload_near_band_seen = True
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "pulse_stop_above_band",
                            load=load,
                            max_lbs=PRELOAD_MAX_LBS,
                            rate_lbs_per_s=rate,
                            predicted_load=predicted_load,
                        )
                        self._remember_auto_preload_stop_locked(load, increase)
                        return True
                    if load >= PRELOAD_MIN_LBS:
                        self.auto_preload_near_band_seen = True
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "pulse_stop_allowed_band",
                            load=load,
                            min_lbs=PRELOAD_MIN_LBS,
                            max_lbs=PRELOAD_MAX_LBS,
                            rate_lbs_per_s=rate,
                            predicted_load=predicted_load,
                        )
                        self._remember_auto_preload_stop_locked(load, increase)
                        return True
                    if predicted_load >= PRELOAD_AUTO_PREDICT_STOP_LBS:
                        self.auto_preload_near_band_seen = True
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "pulse_stop_predicted",
                            load=load,
                            rate_lbs_per_s=rate,
                            predicted_load=predicted_load,
                            predict_stop_lbs=PRELOAD_AUTO_PREDICT_STOP_LBS,
                        )
                        self._remember_auto_preload_stop_locked(load, increase)
                        return True
                    if not stage.get("coarse") and rate >= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND:
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "pulse_stop_fast_rise",
                            load=load,
                            rate_lbs_per_s=rate,
                            stop_margin_lbs=stop_margin,
                            predicted_load=predicted_load,
                        )
                        self._remember_auto_preload_stop_locked(load, increase)
                        return True
                    if max_delta_lbs and delta_lbs >= max_delta_lbs:
                        self.state["auto_preload_message"] = "Settling"
                        self._record_auto_preload_trace_locked(
                            "pulse_stop_delta",
                            load=load,
                            start_load=start_load,
                            delta_lbs=delta_lbs,
                            max_delta_lbs=max_delta_lbs,
                        )
                        self._remember_auto_preload_stop_locked(load, increase)
                        return True

                self._record_auto_preload_trace_locked(
                    "pulse_complete",
                    load=self.state.get("current_load"),
                    increase=increase,
                    pulse_seconds=pulse_seconds,
                )
            return True
        finally:
            with self.lock:
                self._auto_preload_stop_actuator_locked()

    def _auto_preload_note_contact_locked(self, delta_lbs, load):
        if self.auto_preload_contact_detected or delta_lbs < PRELOAD_AUTO_CONTACT_DELTA_LBS:
            return
        self.auto_preload_contact_detected = True
        self._record_auto_preload_trace_locked(
            "contact_detected",
            delta_lbs=delta_lbs,
            load=load,
        )

    def _refresh_auto_preload_load(self, control_speed_percent=0.0, control_direction=None):
        if not PRELOAD_AUTO_DIRECT_LOAD_READ:
            with self.lock:
                return float(self.state.get("current_load") or 0.0)

        with self.lock:
            previous_load = float(self.state.get("current_load") or 0.0)

        load, samples, needs_confirmation, rejected, trace_event = self._read_auto_preload_control_load(
            previous_load,
            control_speed_percent=control_speed_percent,
            control_direction=control_direction,
        )
        load, trace_event = self._apply_auto_preload_plausibility_gate(
            previous_load,
            load,
            samples,
            trace_event,
            control_speed_percent,
            control_direction,
        )

        raw_counts = getattr(self.load_cell, "last_raw_counts", None)
        if raw_counts is None:
            raw_counts = getattr(self.load_cell, "last_raw_lbs", load)
        zero_counts = self.load_cell.health().get("zero_counts")
        with self.lock:
            self.state["auto_preload_sensor_fault"] = bool(rejected)
            if needs_confirmation:
                self._record_auto_preload_trace_locked(
                    trace_event,
                    previous_load=previous_load,
                    first_load=samples[0],
                    load=load,
                    sample_count=len(samples),
                    sample_min=min(samples),
                    sample_max=max(samples),
                    raw_counts=raw_counts,
                    zero_counts=zero_counts,
                )
                if trace_event == "control_load_discarded":
                    self._hold_auto_preload_after_discard_locked(load)
            if rejected:
                self.state["auto_preload_message"] = "Check tension"
            self._set_load_state_locked(load, raw_counts)
        return load

    def _apply_auto_preload_plausibility_gate(
        self,
        previous_load,
        load,
        samples,
        trace_event,
        control_speed_percent=0.0,
        control_direction=None,
    ):
        if not PRELOAD_AUTO_PLAUSIBILITY_ENABLED:
            return load, trace_event
        if load > PRELOAD_AUTO_ABORT_LBS:
            return load, trace_event

        now = time.monotonic()
        with self.lock:
            last_load = self.auto_preload_control_last_load
            last_time = self.auto_preload_control_last_time
            if last_load is None or last_time is None:
                self.auto_preload_control_last_load = float(load)
                self.auto_preload_control_last_time = now
                return load, trace_event
            if self.auto_preload_control_hold_until > now and control_direction is None:
                if abs(float(load) - float(last_load)) > PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS:
                    self._record_auto_preload_trace_locked(
                        "control_load_jounce_ignored",
                        load=load,
                        accepted_load=float(last_load),
                        remaining_s=self.auto_preload_control_hold_until - now,
                    )
                return float(last_load), trace_event

        elapsed_s = max(0.0, now - float(last_time))
        max_delta = self._auto_preload_plausible_delta_locked(
            elapsed_s,
            control_speed_percent,
            control_direction,
        )
        delta = float(load) - float(last_load)
        if abs(delta) <= max_delta:
            with self.lock:
                self.auto_preload_control_last_load = float(load)
                self.auto_preload_control_last_time = now
            return load, trace_event

        with self.lock:
            self._record_auto_preload_trace_locked(
                "control_load_implausible",
                previous_load=previous_load,
                load=load,
                accepted_load=float(last_load),
                delta_lbs=delta,
                max_delta_lbs=max_delta,
                elapsed_s=elapsed_s,
                speed_percent=float(control_speed_percent or 0.0),
                direction=control_direction,
                sample_count=len(samples),
                sample_min=min(samples),
                sample_max=max(samples),
            )
            self._hold_auto_preload_after_discard_locked(float(last_load))
        return float(last_load), "control_load_discarded"

    def _auto_preload_plausible_delta_locked(self, elapsed_s, speed_percent=0.0, direction=None):
        base_delta = max(0.0, float(PRELOAD_AUTO_PLAUSIBILITY_BASE_DELTA_LBS))
        speed = max(0.0, min(100.0, float(speed_percent or 0.0)))
        if direction is None:
            speed = 0.0
        rate_lbs_per_s = 0.75 + ((speed / 100.0) * max(0.0, PRELOAD_AUTO_PLAUSIBILITY_LBS_PER_SECOND_AT_100))
        return base_delta + (max(0.0, float(elapsed_s)) * rate_lbs_per_s)

    def _read_auto_preload_control_load(self, previous_load, control_speed_percent=0.0, control_direction=None):
        samples = [
            self._get_auto_preload_control_force(
                control_speed_percent=control_speed_percent,
                control_direction=control_direction,
            )
        ]
        if not self._auto_preload_control_sample_valid(samples[0]):
            self.auto_preload_control_rejects += 1
            rejected = self.auto_preload_control_rejects > PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS
            trace_event = "control_load_rejected" if rejected else "control_load_invalid_ignored"
            with self.lock:
                self._record_auto_preload_trace_locked(
                    trace_event,
                    previous_load=previous_load,
                    first_load=samples[0],
                    min_valid_lbs=PRELOAD_AUTO_CONTROL_MIN_VALID_LBS,
                    max_valid_lbs=PRELOAD_AUTO_CONTROL_MAX_VALID_LBS,
                    reject_count=self.auto_preload_control_rejects,
                )
            return previous_load, samples, True, rejected, trace_event

        needs_confirmation = self._auto_preload_read_needs_confirmation(previous_load, samples[0])
        if not needs_confirmation:
            return samples[0], samples, False, False, "control_load_read"

        with self.lock:
            if self.actuator.last_command != "neutral" and PRELOAD_AUTO_STOP_DURING_LOAD_READ:
                self._auto_preload_stop_actuator_locked()
                self._record_auto_preload_trace_locked(
                    "control_read_stop",
                    previous_load=previous_load,
                    first_load=samples[0],
                )

        samples.extend(
            self.load_cell.get_control_force()
            for _ in range(max(0, int(PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES) - 1))
        )
        valid_samples = self._auto_preload_valid_control_samples(samples)
        load = self._median(valid_samples) if valid_samples else previous_load
        if self._auto_preload_control_samples_are_trustworthy(previous_load, valid_samples, load):
            self.auto_preload_control_rejects = 0
            if self._auto_preload_should_ignore_drop_after_near_band(previous_load, load):
                return previous_load, samples, True, False, "control_load_drop_ignored_after_near_band"
            return load, samples, True, False, "control_load_confirmed"

        self.load_cell.reset_hardware()
        if PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS > 0:
            time.sleep(PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS)

        retry_samples = [
            self.load_cell.get_control_force()
            for _ in range(max(1, int(PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES)))
        ]
        retry_valid_samples = self._auto_preload_valid_control_samples(retry_samples)
        retry_load = self._median(retry_valid_samples) if retry_valid_samples else previous_load
        all_samples = samples + retry_samples
        if self._auto_preload_control_samples_are_trustworthy(previous_load, retry_valid_samples, retry_load):
            self.auto_preload_control_rejects = 0
            if self._auto_preload_should_ignore_drop_after_near_band(previous_load, retry_load):
                return previous_load, all_samples, True, False, "control_load_drop_ignored_after_near_band"
            return retry_load, all_samples, True, False, "control_load_confirmed"
        if PRELOAD_MIN_LBS <= previous_load <= PRELOAD_MAX_LBS:
            self.auto_preload_control_rejects = 0
            return previous_load, all_samples, True, False, "control_load_spike_ignored_in_band"
        self.auto_preload_control_rejects += 1
        if self.auto_preload_control_rejects <= PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS:
            return previous_load, all_samples, True, False, "control_load_discarded"
        return previous_load, all_samples, True, True, "control_load_rejected"

    def _auto_preload_valid_control_samples(self, samples):
        return [float(sample) for sample in samples if self._auto_preload_control_sample_valid(sample)]

    def _get_auto_preload_control_force(self, control_speed_percent=0.0, control_direction=None):
        moving = control_direction is not None and float(control_speed_percent or 0.0) > 0.0
        if not moving:
            return self.load_cell.get_control_force()
        try:
            return self.load_cell.get_control_force(samples=PRELOAD_AUTO_MOVING_CONTROL_SAMPLES)
        except TypeError:
            return self.load_cell.get_control_force()

    def _hold_auto_preload_after_discard_locked(self, load):
        settle_seconds = max(0.0, float(PRELOAD_AUTO_CONTROL_DISCARD_SETTLE_SECONDS))
        if settle_seconds <= 0:
            return
        self._auto_preload_stop_actuator_locked()
        self.auto_preload_control_hold_until = max(
            self.auto_preload_control_hold_until,
            time.monotonic() + settle_seconds,
        )
        self.auto_preload_control_hold_logged = False
        self.state["auto_preload_message"] = "Settling"

    def _hold_auto_preload_after_stop_locked(self, load, reason):
        settle_seconds = max(0.0, float(PRELOAD_AUTO_STOP_JOUNCE_IGNORE_SECONDS))
        if settle_seconds <= 0:
            return
        self.auto_preload_control_last_load = float(load)
        self.auto_preload_control_last_time = time.monotonic()
        self.auto_preload_control_hold_until = max(
            self.auto_preload_control_hold_until,
            time.monotonic() + settle_seconds,
        )
        self.auto_preload_control_hold_logged = False
        self._record_auto_preload_trace_locked(
            "control_stop_jounce_hold",
            load=load,
            reason=reason,
            seconds=settle_seconds,
        )

    def _auto_preload_read_needs_confirmation(self, previous_load, load):
        return (
            not self._auto_preload_control_sample_valid(load)
            or abs(load - previous_load) >= PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS
            or abs(load) >= PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS
            or (load > PRELOAD_AUTO_ABORT_LBS and previous_load <= PRELOAD_AUTO_ABORT_LBS)
            or self._auto_preload_should_ignore_drop_after_near_band(previous_load, load)
        )

    def _auto_preload_control_sample_valid(self, load):
        return PRELOAD_AUTO_CONTROL_MIN_VALID_LBS <= float(load) <= PRELOAD_AUTO_CONTROL_MAX_VALID_LBS

    def _auto_preload_control_samples_are_trustworthy(self, previous_load, samples, load):
        if len(samples) < self._auto_preload_min_valid_control_samples_locked():
            return False
        sample_range = max(samples) - min(samples)
        if sample_range > PRELOAD_AUTO_CONTROL_CONFIRM_MAX_RANGE_LBS:
            return False
        if load > PRELOAD_AUTO_ABORT_LBS:
            return True
        return True

    def _auto_preload_min_valid_control_samples_locked(self):
        requested = max(1, int(PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES))
        return max(1, min(requested, (requested // 2) + 1))

    def _auto_preload_should_ignore_drop_after_near_band(self, previous_load, load):
        return bool(
            self.auto_preload_near_band_seen
            and float(previous_load) <= PRELOAD_MAX_LBS + PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS
            and float(previous_load) - float(load) >= PRELOAD_AUTO_NEAR_BAND_DROP_REJECT_LBS
            and float(load) < PRELOAD_MIN_LBS - PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS
        )

    def _median(self, values):
        ordered = sorted(values)
        return ordered[len(ordered) // 2]

    def _wait_for_auto_preload_settle(self, deadline, coarse=False, approach=False, fast_contact=False):
        if coarse:
            settle_seconds = PRELOAD_AUTO_COARSE_SETTLE_SECONDS
            max_seconds = PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS
            settle_delta = PRELOAD_AUTO_STABLE_DELTA_LBS
        elif approach:
            settle_seconds = PRELOAD_AUTO_APPROACH_SETTLE_SECONDS
            max_seconds = PRELOAD_AUTO_APPROACH_SETTLE_MAX_SECONDS
            settle_delta = PRELOAD_AUTO_APPROACH_SETTLE_DELTA_LBS
        elif fast_contact:
            settle_seconds = PRELOAD_AUTO_CONTACT_SETTLE_SECONDS
            max_seconds = PRELOAD_AUTO_CONTACT_SETTLE_MAX_SECONDS
            settle_delta = PRELOAD_AUTO_STABLE_DELTA_LBS
        else:
            settle_seconds = PRELOAD_AUTO_SETTLE_SECONDS
            max_seconds = PRELOAD_AUTO_SETTLE_MAX_SECONDS
            settle_delta = PRELOAD_AUTO_STABLE_DELTA_LBS
        started = time.monotonic()
        with self.lock:
            self._record_auto_preload_trace_locked(
                "settle_start",
                load=self.state.get("current_load"),
                coarse=coarse,
                approach=approach,
                fast_contact=fast_contact,
                settle_seconds=settle_seconds,
                max_seconds=max_seconds,
                settle_delta_lbs=settle_delta,
            )
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - started
            with self.lock:
                stable_window = settle_seconds if approach else None
                stable = self._auto_preload_load_stable_locked(delta_lbs=settle_delta, window_seconds=stable_window)
                rate = self._auto_preload_load_rate_locked()
            if (coarse or fast_contact) and elapsed >= max(0.0, settle_seconds):
                if rate <= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND:
                    with self.lock:
                        self._update_auto_preload_coast_locked()
                        self._record_auto_preload_trace_locked(
                            "settle_done",
                            load=self.state.get("current_load"),
                            coarse=coarse,
                            approach=approach,
                            fast_contact=fast_contact,
                            elapsed_s=elapsed,
                            stable=stable,
                            rate_lbs_per_s=rate,
                            reason="fast_rate",
                        )
                    return
            if elapsed >= settle_seconds and stable:
                with self.lock:
                    self._update_auto_preload_coast_locked()
                    self._record_auto_preload_trace_locked(
                        "settle_done",
                        load=self.state.get("current_load"),
                        coarse=coarse,
                        approach=approach,
                        fast_contact=fast_contact,
                        elapsed_s=elapsed,
                        stable=stable,
                        rate_lbs_per_s=rate,
                        reason="stable",
                    )
                return
            if elapsed >= max_seconds:
                with self.lock:
                    self._update_auto_preload_coast_locked()
                    self._record_auto_preload_trace_locked(
                        "settle_done",
                        load=self.state.get("current_load"),
                        coarse=coarse,
                        approach=approach,
                        fast_contact=fast_contact,
                        elapsed_s=elapsed,
                        stable=stable,
                        rate_lbs_per_s=rate,
                        reason="max_wait",
                    )
                return
            time.sleep(0.05)

    def _remember_auto_preload_stop_locked(self, load, increase):
        self.auto_preload_last_stop_load = float(load)
        self.auto_preload_last_stop_increase = bool(increase)

    def _update_auto_preload_coast_locked(self):
        if self.auto_preload_last_stop_load is None or not self.auto_preload_last_stop_increase:
            return 0.0
        load = float(self.state.get("current_load") or 0.0)
        coast = max(0.0, load - self.auto_preload_last_stop_load)
        self.auto_preload_coast_lbs = (self.auto_preload_coast_lbs * 0.5) + (coast * 0.5)
        self._record_auto_preload_trace_locked(
            "coast_measured",
            stop_load=self.auto_preload_last_stop_load,
            load=load,
            coast_lbs=coast,
            learned_coast_lbs=self.auto_preload_coast_lbs,
        )
        self.auto_preload_last_stop_load = None
        self.auto_preload_last_stop_increase = None
        return coast

    def _move_auto_preload_direction_locked(self, increase):
        return self._move_preload_direction_locked(
            increase=increase, speed_percent=PRELOAD_AUTO_SPEED_PERCENT
        )

    def _move_preload_direction_locked(self, increase, speed_percent):
        if self.state.get("test_running"):
            self._record_auto_preload_trace_locked(
                "auto_move_ignored_during_pull",
                load=self.state.get("current_load"),
                increase=bool(increase),
                speed_percent=speed_percent,
                command=self.actuator.last_command,
                pulse_us=self.actuator.last_pulse_us,
            )
            return False
        if not self._owns_actuator_locked(self.auto_preload_epoch):
            # A jog/Stop/new run took the actuator (bumped the epoch) after this
            # auto run started: don't move it -- the new owner already has it.
            self._record_auto_preload_trace_locked(
                "auto_move_ignored_lost_ownership",
                load=self.state.get("current_load"),
                increase=bool(increase),
                speed_percent=speed_percent,
                command=self.actuator.last_command,
            )
            return False
        pull_direction = self.actuator.pull_direction
        direction = pull_direction if increase else ("down" if pull_direction == "up" else "up")
        speed = max(1, min(100, int(float(speed_percent))))
        if direction == "up":
            return self.actuator.move_up(fast=True, speed_percent=speed)
        return self.actuator.move_down(fast=True, speed_percent=speed)

    def _record_load_locked(self, load):
        now = time.monotonic()
        self.load_history.append((now, float(load)))
        cutoff = now - max(
            0.2,
            LOAD_STABLE_WINDOW_SECONDS,
            PRELOAD_AUTO_STABLE_WINDOW_SECONDS,
            PRELOAD_AUTO_DRIFT_WINDOW_SECONDS,
        )
        while self.load_history and self.load_history[0][0] < cutoff:
            self.load_history.popleft()

    def _record_scan_load_locked(self, load):
        now = time.monotonic()
        load = round(float(load), 3)
        self.scan_load_history.append((now, load))
        cutoff = now - max(0.2, PRELOAD_AUTO_SCAN_VERIFY_SECONDS * 2.0)
        while self.scan_load_history and self.scan_load_history[0][0] < cutoff:
            self.scan_load_history.popleft()
        self.state["scan_load"] = load
        self.state["scan_load_window_s"] = self._scan_load_window_seconds_locked(now)

    def _scan_load_window_seconds_locked(self, now=None):
        if not self.scan_load_history:
            return 0.0
        now = time.monotonic() if now is None else now
        cutoff = now - max(0.2, PRELOAD_AUTO_SCAN_VERIFY_SECONDS)
        samples = [(sample_time, value) for sample_time, value in self.scan_load_history if sample_time >= cutoff]
        if len(samples) < 2:
            return 0.0
        return round(samples[-1][0] - samples[0][0], 3)

    def _auto_preload_scan_ready_locked(self):
        required_window = max(0.0, float(PRELOAD_AUTO_SCAN_VERIFY_SECONDS))
        if required_window <= 0:
            self.state["scan_load_window_s"] = 0.0
            return True
        now = time.monotonic()
        cutoff = now - required_window
        samples = [(sample_time, value) for sample_time, value in self.scan_load_history if sample_time >= cutoff]
        if len(samples) < 3:
            self.state["scan_load_window_s"] = self._scan_load_window_seconds_locked(now)
            current_load = float(self.state.get("current_load") or 0.0)
            scan_load = float(self.state.get("scan_load") or current_load)
            if (
                PRELOAD_MIN_LBS <= current_load <= PRELOAD_MAX_LBS
                and PRELOAD_MIN_LBS <= scan_load <= PRELOAD_MAX_LBS
                and self._auto_preload_load_stable_locked()
            ):
                return True
            return False
        window_s = samples[-1][0] - samples[0][0]
        self.state["scan_load_window_s"] = round(window_s, 3)
        if window_s < required_window * 0.8:
            return False
        return all(PRELOAD_MIN_LBS <= value <= PRELOAD_MAX_LBS for _, value in samples)

    def _set_load_state_locked(self, load, raw_counts):
        load = round(float(load), 3)
        self.state["current_load"] = load
        self.state["raw_load"] = raw_counts
        self.state["display_load"] = self._smooth_display_load_locked(load)
        self._record_load_locked(load)
        self.state["preload_ready"] = self._preload_start_allowed_locked(load)
        self.state["preload_stable"] = self.state["preload_ready"] and self._load_stable_locked()

    def _smooth_display_load_locked(self, load):
        previous = self.state.get("display_load")
        if previous is None:
            return round(float(load), 3)
        previous = float(previous)
        load = float(load)
        if abs(load - previous) >= max(0.0, LOADCELL_DISPLAY_SNAP_DELTA_LBS):
            return round(load, 3)
        alpha = max(0.0, min(1.0, float(LOADCELL_DISPLAY_ALPHA)))
        return round(previous + ((load - previous) * alpha), 3)

    def _preload_start_allowed_locked(self, load):
        load = float(load)
        if PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS:
            return True
        return self._preload_ready_latch_allows_load_locked(load)

    def _preload_ready_latch_allows_load_locked(self, load):
        if not self.state.get("preload_ready_latched"):
            return False
        negative_margin = max(0.0, float(PRELOAD_READY_LATCH_MARGIN_LBS))
        positive_margin = max(negative_margin, float(PRELOAD_READY_LATCH_POSITIVE_MARGIN_LBS))
        return PRELOAD_MIN_LBS - negative_margin <= float(load) <= PRELOAD_MAX_LBS + positive_margin

    def _set_preload_ready_latch_locked(self, load):
        self.state["preload_ready_latched"] = True
        self.state["preload_ready"] = self._preload_start_allowed_locked(load)
        self._record_auto_preload_trace_locked(
            "ready_latched",
            load=load,
            min_lbs=PRELOAD_MIN_LBS,
            max_lbs=PRELOAD_MAX_LBS,
            margin_lbs=PRELOAD_READY_LATCH_MARGIN_LBS,
            positive_margin_lbs=PRELOAD_READY_LATCH_POSITIVE_MARGIN_LBS,
        )

    def _clear_preload_ready_latch_locked(self):
        self.state["preload_ready_latched"] = False

    def _auto_preload_can_recover_post_band_locked(self, load):
        return bool(
            self.auto_preload_near_band_seen
            and PRELOAD_MAX_LBS < float(load) <= PRELOAD_AUTO_POST_BAND_RECOVERY_MAX_LBS
        )

    def _record_auto_preload_trace_locked(self, event, **data):
        entry = {"t": round(time.monotonic(), 4), "event": event}
        for key, value in data.items():
            if value is None:
                continue
            if isinstance(value, float):
                entry[key] = round(value, 4)
            else:
                entry[key] = value
        self.auto_preload_trace.append(entry)
        self._append_auto_preload_trace_file_locked(entry)

    def _start_auto_preload_trace_file_locked(self):
        try:
            PRELOAD_AUTO_TRACE_DIR.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
            self.auto_preload_trace_file = PRELOAD_AUTO_TRACE_DIR / f"auto_tension_{stamp}_{int(time.time() * 1000) % 1000:03d}.jsonl"
        except OSError:
            self.auto_preload_trace_file = None

    def _append_auto_preload_trace_file_locked(self, entry):
        if self.auto_preload_trace_file is None:
            return
        try:
            with self.auto_preload_trace_file.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, sort_keys=True) + "\n")
        except OSError:
            self.auto_preload_trace_file = None

    def _load_stable_locked(self):
        if len(self.load_history) < 3:
            return False
        values = [value for _, value in self.load_history]
        return max(values) - min(values) <= LOAD_STABLE_DELTA_LBS

    def _auto_preload_load_stable_locked(self, delta_lbs=None, window_seconds=None):
        now = time.monotonic()
        stable_window = PRELOAD_AUTO_STABLE_WINDOW_SECONDS if window_seconds is None else float(window_seconds)
        cutoff = now - max(0.2, stable_window)
        values = [value for sample_time, value in self.load_history if sample_time >= cutoff]
        if len(values) < 3:
            return False
        allowed_delta = PRELOAD_AUTO_STABLE_DELTA_LBS if delta_lbs is None else float(delta_lbs)
        return max(values) - min(values) <= allowed_delta

    def _auto_preload_recent_load_samples_locked(self):
        now = time.monotonic()
        cutoff = now - max(0.1, PRELOAD_AUTO_RATE_WINDOW_SECONDS)
        return [(sample_time, value) for sample_time, value in self.load_history if sample_time >= cutoff]

    def _auto_preload_signed_load_rate_locked(self):
        samples = self._auto_preload_recent_load_samples_locked()
        if len(samples) < 2:
            return 0.0
        first_time, first_value = samples[0]
        last_time, last_value = samples[-1]
        elapsed = last_time - first_time
        if elapsed <= 0:
            return 0.0
        return (last_value - first_value) / elapsed

    def _auto_preload_load_rate_locked(self):
        samples = self._auto_preload_recent_load_samples_locked()
        if len(samples) < 2:
            return 0.0
        window_rate = self._auto_preload_signed_load_rate_locked()

        # Use a robust upper slope instead of the single fastest adjacent
        # sample. One HX711/jounce spike can otherwise dominate prediction and
        # make the controller brake or enter final approach far from target.
        positive_slopes = []
        for (prev_time, prev_value), (sample_time, value) in zip(samples, samples[1:]):
            sample_elapsed = sample_time - prev_time
            if sample_elapsed <= 0:
                continue
            slope = (value - prev_value) / sample_elapsed
            if slope > 0:
                positive_slopes.append(slope)
        if not positive_slopes:
            return max(0.0, window_rate)
        positive_slopes.sort()
        robust_index = int((len(positive_slopes) - 1) * 0.75)
        robust_rise = positive_slopes[robust_index]
        return max(0.0, window_rate, robust_rise)

    def _auto_preload_ready_locked(self):
        short_stable = self._auto_preload_load_stable_locked()
        drift_stable, drop_lbs, window_s = self._auto_preload_drift_stable_locked()
        self.state["auto_preload_short_stable"] = short_stable
        self.state["auto_preload_drift_stable"] = drift_stable
        self.state["auto_preload_drift_drop_lbs"] = round(drop_lbs, 3)
        self.state["auto_preload_drift_window_s"] = round(window_s, 3)
        return short_stable and drift_stable

    def _auto_preload_drift_stable_locked(self):
        now = time.monotonic()
        required_window = max(0.2, PRELOAD_AUTO_DRIFT_WINDOW_SECONDS)
        cutoff = now - required_window
        samples = [(sample_time, value) for sample_time, value in self.load_history if sample_time >= cutoff]
        if len(samples) < 3:
            return False, 0.0, 0.0

        window_s = samples[-1][0] - samples[0][0]
        if window_s < required_window * 0.9:
            return False, 0.0, window_s

        edge_count = max(1, len(samples) // 4)
        early_avg = sum(value for _, value in samples[:edge_count]) / edge_count
        late_avg = sum(value for _, value in samples[-edge_count:]) / edge_count
        downward_drop = max(0.0, early_avg - late_avg)
        return downward_drop <= PRELOAD_AUTO_DRIFT_MAX_DROP_LBS, downward_drop, window_s

    def _begin_stop_locked(self, reason):
        if self.state.get("stop_pending"):
            return
        self._bump_actuator_epoch_locked()
        self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command
        self.state["stop_pending"] = True
        self.state["stop_pending_started_at"] = time.monotonic()
        self.state["stop_reason"] = reason

    def _finish_stop_locked(self, reason):
        self._stop_preload_hold_locked()
        self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command
        test_id = self.state.get("active_test_id")
        peak = round(float(self.state.get("peak_load") or 0.0), 3)
        sample_count = int(self.state.get("sample_count") or 0)
        was_running = bool(self.state.get("test_running") or self.state.get("stop_pending"))
        self.failure_drop_samples = 0

        self.state["test_running"] = False
        self.state["test_complete"] = True if test_id else False
        self.state["stop_pending"] = False
        self.state["stop_pending_started_at"] = None
        self.state["stop_reason"] = reason
        self.load_cell.resume_glitch_reject()
        self._clear_auto_preload_status_locked()
        self._reset_auto_preload_control_locked()

        if test_id and was_running:
            storage.update_test(
                test_id,
                status="complete",
                completed_at=storage.utc_now(),
                peak_load_lbs=peak,
                stop_reason=reason,
                sample_count=sample_count,
                software_version=APP_VERSION,
            )
            storage.add_event(
                "Pull stopped",
                test_id=test_id,
                data={"reason": reason, "peak_load_lbs": peak, "sample_count": sample_count},
            )


quadpod_engine = QuadpodEngine()
quadpod_engine.start()


def init_db():
    storage.init_db()


def hardware_scan_cycle():
    quadpod_engine.start()


def log_test_to_db(data_dict):
    storage.add_event("Legacy log call", data=data_dict)


quadpod_state = quadpod_engine.state


def _date_is_recorded(value):
    try:
        dt.date.fromisoformat(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _calibration_date_error(value, today):
    """Return a gate-error suffix for a calibration date, or None if it passes.

    Rejects only a blank/unparseable date (preserving the original "must be
    recorded" behavior) and a date in the future (a calibration can't happen
    later than today, so it's an operator typo). Age is never gated -- the
    recorded date is kept as entered no matter how old.
    """
    try:
        recorded = dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return "must be recorded"
    if recorded > today:
        return "cannot be in the future"
    return None
