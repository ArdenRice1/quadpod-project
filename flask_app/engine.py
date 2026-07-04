import datetime as dt
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
    PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS,
    PRELOAD_AUTO_CONTROL_MAX_TRANSIENT_REJECTS,
    PRELOAD_AUTO_CONTROL_SPIKE_RETRY_SECONDS,
    PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS,
    PRELOAD_AUTO_CONTINUOUS_BRAKE_MARGIN_LBS,
    PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS,
    PRELOAD_AUTO_CONTINUOUS_KD,
    PRELOAD_AUTO_CONTINUOUS_KP,
    PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT,
    PRELOAD_AUTO_CONTINUOUS_RAMP_PERCENT_PER_SECOND,
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
    PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
    PRELOAD_AUTO_IN_BAND_END_SECONDS,
    PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND,
    PRELOAD_AUTO_MAX_STOP_MARGIN_LBS,
    PRELOAD_AUTO_MIN_STOP_MARGIN_LBS,
    PRELOAD_AUTO_MODE,
    PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS,
    PRELOAD_AUTO_NEGATIVE_JUMP_DELTA_LBS,
    PRELOAD_AUTO_NEGATIVE_JUMP_GUARD_START_LBS,
    PRELOAD_AUTO_PULSE_SECONDS,
    PRELOAD_AUTO_PULSE_CHECK_SECONDS,
    PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS,
    PRELOAD_AUTO_PREDICT_STOP_LBS,
    PRELOAD_AUTO_RATE_WINDOW_SECONDS,
    PRELOAD_AUTO_SPEED_PERCENT,
    PRELOAD_AUTO_STABLE_DELTA_LBS,
    PRELOAD_AUTO_STABLE_WINDOW_SECONDS,
    PRELOAD_AUTO_SETTLE_MAX_SECONDS,
    PRELOAD_AUTO_SETTLE_SECONDS,
    PRELOAD_AUTO_TIMEOUT_SECONDS,
    PRELOAD_AUTO_TENSION_STAGES,
    PRELOAD_AUTO_TRACE_MAX_ENTRIES,
    PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND,
    PRELOAD_HOLD_TRIM_ENABLED,
    PRELOAD_HOLD_TRIM_INTERVAL_SECONDS,
    PRELOAD_HOLD_TRIM_MAX_US,
    PRELOAD_HOLD_TRIM_STEP_US,
    PRELOAD_MAX_LBS,
    PRELOAD_MIN_LBS,
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
        self.auto_preload_trace = deque(maxlen=max(1, int(PRELOAD_AUTO_TRACE_MAX_ENTRIES)))
        self.auto_preload_coast_lbs = 0.0
        self.auto_preload_last_stop_load = None
        self.auto_preload_last_stop_increase = None
        self.auto_preload_contact_detected = False
        self.auto_preload_near_band_seen = False
        self.auto_preload_control_rejects = 0
        self.auto_preload_thread = None
        self.preload_hold_thread = None
        self.preload_hold_active = False
        self.preload_hold_trim_us = 0
        self.state = {
            "current_load": 0.0,
            "raw_load": 0.0,
            "peak_load": 0.0,
            "preload_ready": False,
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

    def jog(self, action, speed_percent=None):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot jog while a pull test is running."
            self._stop_preload_hold_locked()
            if speed_percent is not None:
                self.state["jog_speed_percent"] = max(1, min(100, int(float(speed_percent))))
            speed = self.state["jog_speed_percent"]
            if action == "up":
                ok = self.actuator.move_up(fast=True, speed_percent=speed)
            elif action == "down":
                ok = self.actuator.move_down(fast=True, speed_percent=speed)
            elif action == "stop":
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
            self.auto_preload_trace.clear()
            self._reset_auto_preload_control_locked()
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
            self.auto_preload_thread = threading.Thread(target=self._auto_preload_loop, daemon=True)
            self.auto_preload_thread.start()
            return True, self.state["auto_preload_message"]

    def tare(self):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot tare while a pull test is running."
            self._stop_preload_hold_locked()
            ok = self.load_cell.tare()
            return ok, self.load_cell.last_error

    def calibrate_load_cell(self, known_lbs):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot calibrate while a pull test is running."
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
            storage.clear_samples(test_id)
            self.failure_drop_samples = 0
            self.load_history.clear()
            self._reset_auto_preload_control_locked()
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
        if load < PRELOAD_MIN_LBS or load > PRELOAD_MAX_LBS:
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
        for field, label in [
            ("load_cell_calibration_date", "load cell calibration date"),
            ("ir_temp_gun_calibration_date", "IR temp gun calibration date"),
        ]:
            if not _date_is_recorded(job_form.get(field, "")):
                errors.append(f"{label} must be recorded")
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

        load = self.load_cell.get_force()
        raw_counts = getattr(self.load_cell, "last_raw_counts", None)
        if raw_counts is None:
            raw_counts = getattr(self.load_cell, "last_raw_lbs", load)

        with self.lock:
            self.state["current_load"] = load
            self.state["raw_load"] = raw_counts
            self._record_load_locked(load)
            self.state["preload_ready"] = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
            self.state["preload_stable"] = self.state["preload_ready"] and self._load_stable_locked()

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
        if PRELOAD_AUTO_MODE == "continuous":
            self._auto_preload_continuous_loop()
            return
        self._auto_preload_pulse_loop()

    def _auto_preload_continuous_loop(self):
        deadline = time.monotonic() + PRELOAD_AUTO_TIMEOUT_SECONDS
        stable_since = None
        current_speed = 0.0
        last_speed_command = None
        last_update = time.monotonic()
        hold_should_start = False
        try:
            while time.monotonic() < deadline:
                self._refresh_auto_preload_load()
                now = time.monotonic()
                direction = None
                with self.lock:
                    if self.state.get("auto_preload_sensor_fault"):
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked(
                            "sensor_fault_stop",
                            load=self.state.get("current_load"),
                        )
                        break
                    if self.state["test_running"]:
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break

                    load = float(self.state.get("current_load") or 0.0)
                    rate = self._auto_preload_load_rate_locked()
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("abort", load=load, abort_lbs=PRELOAD_AUTO_ABORT_LBS)
                        break

                    in_band = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
                    if in_band:
                        self.auto_preload_near_band_seen = True
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        current_speed = 0.0
                        last_speed_command = None
                        if stable_since is None:
                            stable_since = now
                            self._record_auto_preload_trace_locked(
                                "continuous_in_band",
                                load=load,
                                rate_lbs_per_s=rate,
                                min_lbs=PRELOAD_MIN_LBS,
                                max_lbs=PRELOAD_MAX_LBS,
                            )
                        ready = self._auto_preload_ready_locked()
                        if now - stable_since >= PRELOAD_AUTO_IN_BAND_END_SECONDS:
                            self.state["auto_preload_message"] = "Ready" if ready else ""
                            self._record_auto_preload_trace_locked(
                                "in_band_complete",
                                load=load,
                                seconds=now - stable_since,
                                ready=ready,
                                short_stable=self.state.get("auto_preload_short_stable"),
                                drift_stable=self.state.get("auto_preload_drift_stable"),
                                drift_drop_lbs=self.state.get("auto_preload_drift_drop_lbs"),
                            )
                            hold_should_start = True
                            break
                        self.state["auto_preload_message"] = "Settling"
                    else:
                        stable_since = None
                        predicted_load = self._auto_preload_continuous_predicted_load_locked(load, rate, current_speed)
                        if load < PRELOAD_MIN_LBS:
                            if self._auto_preload_continuous_should_brake_locked(load, rate, predicted_load):
                                self.actuator.stop()
                                self.state["actuator_command"] = self.actuator.last_command
                                current_speed = 0.0
                                last_speed_command = None
                                self.state["auto_preload_message"] = "Settling"
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
                            desired_speed = self._auto_preload_continuous_speed_locked(load, rate, direction)
                            current_speed = self._auto_preload_slew_speed(
                                current_speed,
                                desired_speed,
                                now - last_update,
                            )
                            command_speed = max(1, min(100, int(round(current_speed))))
                            self._move_preload_direction_locked(direction, command_speed)
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
                                )
                                last_speed_command = command_speed
                last_update = now
                time.sleep(max(0.01, PRELOAD_AUTO_CONTINUOUS_INTERVAL_SECONDS))
            else:
                with self.lock:
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "timeout",
                        load=self.state.get("current_load"),
                        seconds=PRELOAD_AUTO_TIMEOUT_SECONDS,
                    )
        finally:
            with self.lock:
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "") == "Ready":
                    self.state["auto_preload_message"] = ""
                if hold_should_start:
                    self._start_preload_hold_locked()
                self._record_auto_preload_trace_locked(
                    "finish",
                    load=self.state.get("current_load"),
                    message=self.state.get("auto_preload_message"),
                )

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
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked(
                            "sensor_fault_stop",
                            load=self.state.get("current_load"),
                        )
                        break
                    if self.state["test_running"]:
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("cancelled", load=self.state.get("current_load"))
                        break

                    load = float(self.state.get("current_load") or 0.0)
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = "Check tension"
                        self._record_auto_preload_trace_locked("abort", load=load, abort_lbs=PRELOAD_AUTO_ABORT_LBS)
                        break

                    direction = self._auto_preload_direction_for_load(load)
                    if direction is None:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        now = time.monotonic()
                        in_band = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
                        near_band_hold = self._auto_preload_near_band_hold_locked(load)
                        if in_band:
                            self.auto_preload_near_band_seen = True
                        ready = in_band and self._auto_preload_ready_locked()
                        if in_band:
                            if stable_since is None:
                                stable_since = now
                            if now - stable_since >= PRELOAD_AUTO_IN_BAND_END_SECONDS:
                                self.state["auto_preload_message"] = "Ready" if ready else ""
                                self._record_auto_preload_trace_locked(
                                    "in_band_complete",
                                    load=load,
                                    seconds=now - stable_since,
                                    ready=ready,
                                    short_stable=self.state.get("auto_preload_short_stable"),
                                    drift_stable=self.state.get("auto_preload_drift_stable"),
                                    drift_drop_lbs=self.state.get("auto_preload_drift_drop_lbs"),
                                )
                                hold_should_start = True
                                break
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
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
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
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    self.state["auto_preload_message"] = "Check tension"
                    self._record_auto_preload_trace_locked(
                        "timeout",
                        load=self.state.get("current_load"),
                        seconds=PRELOAD_AUTO_TIMEOUT_SECONDS,
                    )
        finally:
            with self.lock:
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "") == "Ready":
                    self.state["auto_preload_message"] = ""
                if hold_should_start:
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
        self.auto_preload_control_rejects = 0

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
        self.preload_hold_thread = threading.Thread(target=self._preload_hold_loop, daemon=True)
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
        self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command

    def _preload_hold_loop(self):
        while True:
            time.sleep(max(0.05, PRELOAD_HOLD_TRIM_INTERVAL_SECONDS))
            self._refresh_auto_preload_load()
            with self.lock:
                if (
                    not self.preload_hold_active
                    or self.state.get("test_running")
                    or self.state.get("auto_preload_running")
                    or self.state.get("auto_preload_sensor_fault")
                ):
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    self.preload_hold_active = False
                    return
                self._preload_hold_update_locked()

    def _preload_hold_update_locked(self):
        load = float(self.state.get("current_load") or 0.0)
        rate = self._auto_preload_load_rate_locked()
        if load < PRELOAD_MIN_LBS or load > PRELOAD_MAX_LBS:
            self.preload_hold_trim_us = 0
            self.actuator.stop()
            self.state["actuator_command"] = self.actuator.last_command
            self._record_auto_preload_trace_locked(
                "hold_out_of_band",
                load=load,
            )
            return

        previous_trim = self.preload_hold_trim_us
        if PRELOAD_MIN_LBS <= load < PRELOAD_TARGET_LBS:
            if rate <= -PRELOAD_HOLD_TRIM_DROP_RATE_LBS_PER_SECOND or self.preload_hold_trim_us > 0:
                self.preload_hold_trim_us = min(
                    max(0, int(PRELOAD_HOLD_TRIM_MAX_US)),
                    self.preload_hold_trim_us + max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
                )
        else:
            self.preload_hold_trim_us = max(
                0,
                self.preload_hold_trim_us - max(1, int(PRELOAD_HOLD_TRIM_STEP_US)),
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

    def _auto_preload_continuous_should_brake_locked(self, load, rate, predicted_load):
        if predicted_load >= PRELOAD_MIN_LBS:
            self.auto_preload_near_band_seen = True
            return True
        if (
            load >= PRELOAD_MIN_LBS - PRELOAD_AUTO_APPROACH_DISTANCE_LBS
            and rate >= PRELOAD_AUTO_CONTINUOUS_MAX_UP_RATE_LBS_PER_SECOND
        ):
            return True
        return False

    def _auto_preload_continuous_speed_locked(self, load, rate, increase):
        if increase:
            error_lbs = max(0.0, PRELOAD_TARGET_LBS - float(load))
            damping = max(0.0, float(rate)) * PRELOAD_AUTO_CONTINUOUS_KD
            raw_speed = (error_lbs * PRELOAD_AUTO_CONTINUOUS_KP) - damping
        else:
            error_lbs = max(0.0, float(load) - PRELOAD_TARGET_LBS)
            raw_speed = error_lbs * (PRELOAD_AUTO_CONTINUOUS_KP * 0.5)

        min_speed = max(1.0, float(PRELOAD_AUTO_CONTINUOUS_MIN_SPEED_PERCENT))
        max_speed = max(min_speed, float(PRELOAD_AUTO_CONTINUOUS_MAX_SPEED_PERCENT))
        return max(min_speed, min(max_speed, raw_speed))

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
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
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
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command

    def _auto_preload_note_contact_locked(self, delta_lbs, load):
        if self.auto_preload_contact_detected or delta_lbs < PRELOAD_AUTO_CONTACT_DELTA_LBS:
            return
        self.auto_preload_contact_detected = True
        self._record_auto_preload_trace_locked(
            "contact_detected",
            delta_lbs=delta_lbs,
            load=load,
        )

    def _refresh_auto_preload_load(self):
        if not PRELOAD_AUTO_DIRECT_LOAD_READ:
            with self.lock:
                return float(self.state.get("current_load") or 0.0)

        with self.lock:
            previous_load = float(self.state.get("current_load") or 0.0)

        load, samples, needs_confirmation, rejected, trace_event = self._read_auto_preload_control_load(previous_load)

        raw_counts = getattr(self.load_cell, "last_raw_counts", None)
        if raw_counts is None:
            raw_counts = getattr(self.load_cell, "last_raw_lbs", load)
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
                )
            if rejected:
                self.state["auto_preload_message"] = "Check tension"
            self.state["current_load"] = load
            self.state["raw_load"] = raw_counts
            self._record_load_locked(load)
            self.state["preload_ready"] = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
            self.state["preload_stable"] = self.state["preload_ready"] and self._load_stable_locked()
        return load

    def _read_auto_preload_control_load(self, previous_load):
        samples = [self.load_cell.get_control_force()]
        needs_confirmation = self._auto_preload_read_needs_confirmation(previous_load, samples[0])
        if not needs_confirmation:
            return samples[0], samples, False, False, "control_load_read"

        samples.extend(
            self.load_cell.get_control_force()
            for _ in range(max(0, int(PRELOAD_AUTO_CONTROL_CONFIRM_SAMPLES) - 1))
        )
        load = self._median(samples)
        if self._auto_preload_control_samples_are_trustworthy(previous_load, samples, load):
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
        retry_load = self._median(retry_samples)
        all_samples = samples + retry_samples
        if self._auto_preload_control_samples_are_trustworthy(previous_load, retry_samples, retry_load):
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

    def _auto_preload_read_needs_confirmation(self, previous_load, load):
        return (
            abs(load - previous_load) >= PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS
            or abs(load) >= PRELOAD_AUTO_CONTROL_HARD_SPIKE_LBS
            or (load > PRELOAD_AUTO_ABORT_LBS and previous_load <= PRELOAD_AUTO_ABORT_LBS)
            or self._auto_preload_should_ignore_drop_after_near_band(previous_load, load)
        )

    def _auto_preload_control_samples_are_trustworthy(self, previous_load, samples, load):
        sample_range = max(samples) - min(samples)
        if sample_range > PRELOAD_AUTO_CONTROL_CONFIRM_MAX_RANGE_LBS:
            return False
        if load > PRELOAD_AUTO_ABORT_LBS:
            return True
        if abs(load - previous_load) >= PRELOAD_AUTO_CONTROL_SPIKE_DELTA_LBS:
            return False
        return True

    def _auto_preload_should_ignore_drop_after_near_band(self, previous_load, load):
        return bool(
            self.auto_preload_near_band_seen
            and previous_load >= PRELOAD_MIN_LBS - PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS
            and load < PRELOAD_MIN_LBS - PRELOAD_AUTO_NEAR_BAND_HOLD_MARGIN_LBS
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

    def _auto_preload_load_rate_locked(self):
        now = time.monotonic()
        cutoff = now - max(0.1, PRELOAD_AUTO_RATE_WINDOW_SECONDS)
        samples = [(sample_time, value) for sample_time, value in self.load_history if sample_time >= cutoff]
        if len(samples) < 2:
            return 0.0
        first_time, first_value = samples[0]
        last_time, last_value = samples[-1]
        elapsed = last_time - first_time
        if elapsed <= 0:
            return 0.0
        return (last_value - first_value) / elapsed

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
