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
    PRELOAD_AUTO_COARSE_MAX_DELTA_LBS,
    PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
    PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND,
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
    PRELOAD_MAX_LBS,
    PRELOAD_MIN_LBS,
    PRELOAD_STABILITY_SECONDS,
    PRELOAD_TARGET_LBS,
    PRELOAD_TOLERANCE_LBS,
    PULL_TARGET_IN_PER_MIN,
    SAMPLE_RATE_HZ,
    USE_MOCK_HARDWARE,
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
        self.auto_preload_thread = None
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

    def jog(self, action, speed_percent=None):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot jog while a pull test is running."
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
            self.state["auto_preload_running"] = True
            self.state["auto_preload_message"] = "Auto tension started."
            self.auto_preload_thread = threading.Thread(target=self._auto_preload_loop, daemon=True)
            self.auto_preload_thread.start()
            return True, self.state["auto_preload_message"]

    def tare(self):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot tare while a pull test is running."
            ok = self.load_cell.tare()
            return ok, self.load_cell.last_error

    def calibrate_load_cell(self, known_lbs):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot calibrate while a pull test is running."
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
            test = storage.get_test(test_id)
            if not test:
                return False, "Test record not found."

            load = float(self.state["current_load"])
            gate_errors = self._start_gate_errors_locked(test, load)
            if gate_errors:
                return False, "Cannot start pull: " + "; ".join(gate_errors)

            self.failure_drop_samples = 0
            self.load_history.clear()
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
                    "auto_preload_running": False,
                    "auto_preload_message": "",
                }
            )
            self.last_client_poll = time.monotonic()
            storage.update_test(
                test_id,
                status="running",
                started_at=storage.utc_now(),
                initial_preload_lbs=round(load, 3),
                peak_load_lbs=round(load, 3),
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
        deadline = time.monotonic() + PRELOAD_AUTO_TIMEOUT_SECONDS
        stable_since = None
        in_band_since = None
        try:
            while time.monotonic() < deadline:
                direction = None
                pulse_seconds = 0.0
                with self.lock:
                    if self.state["test_running"]:
                        self.state["auto_preload_message"] = "Auto tension cancelled because a pull test started."
                        break

                    load = float(self.state.get("current_load") or 0.0)
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = (
                            f"Auto tension exceeded {PRELOAD_AUTO_ABORT_LBS:.1f} lb at {load:.1f} lb. Reset before testing."
                        )
                        break

                    direction = self._auto_preload_direction_for_load(load)
                    if direction is None:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        now = time.monotonic()
                        in_band = PRELOAD_MIN_LBS <= load <= PRELOAD_MAX_LBS
                        ready = in_band and self._auto_preload_ready_locked()
                        if ready:
                            if stable_since is None:
                                stable_since = now
                            if now - stable_since >= PRELOAD_STABILITY_SECONDS:
                                self.state["auto_preload_message"] = (
                                    f"Tension stable at {load:.1f} lb. Ready to test."
                                )
                                break
                        else:
                            stable_since = None
                            if in_band:
                                if in_band_since is None:
                                    in_band_since = now
                                if now - in_band_since >= PRELOAD_AUTO_DRIFT_WARN_SECONDS:
                                    self.state["auto_preload_message"] = (
                                        "Tension is still settling. Check attachment if it keeps drifting."
                                    )
                                else:
                                    self.state["auto_preload_message"] = "Waiting for tension to settle."
                            else:
                                in_band_since = None
                                self.state["auto_preload_message"] = "Waiting for tension to stabilize."
                    elif not self._auto_preload_coarse_active_locked(load, direction) and not self._auto_preload_load_stable_locked():
                        direction = None
                        stable_since = None
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = (
                            "Waiting for load cell to stabilize before the next tension pulse."
                        )
                    else:
                        stage = self._auto_preload_stage_for_load(load, direction)
                        pulse_seconds = stage["pulse_seconds"]
                        self._move_preload_direction_locked(
                            increase=direction, speed_percent=stage["speed_percent"]
                        )
                        self.state["actuator_command"] = self.actuator.last_command
                        stable_since = None
                        in_band_since = None
                        self.state["auto_preload_message"] = stage["message"]

                if direction is None:
                    time.sleep(0.1)
                    continue

                if not self._run_auto_preload_pulse(direction, stage, deadline):
                    break
                self._wait_for_auto_preload_settle(deadline, coarse=stage.get("coarse", False))
            else:
                with self.lock:
                    self.actuator.stop()
                    self.state["actuator_command"] = self.actuator.last_command
                    self.state["auto_preload_message"] = "Auto tension timed out. Use jog controls and try again."
        finally:
            with self.lock:
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command
                self.state["auto_preload_running"] = False
                if self.state.get("auto_preload_message", "").startswith("Tension stable"):
                    self.state["auto_preload_message"] = ""

    def _auto_preload_direction_for_load(self, load):
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
                "message": "Auto tension easing down; waiting for load cell.",
            }

        for threshold, speed_percent, pulse_seconds in PRELOAD_AUTO_TENSION_STAGES:
            if load < threshold:
                coarse = self._auto_preload_coarse_active_locked(load, increase)
                return {
                    "coarse": coarse,
                    "max_delta_lbs": self._auto_preload_max_delta_lbs(load, coarse),
                    "speed_percent": speed_percent,
                    "pulse_seconds": self._auto_preload_configured_pulse_seconds(pulse_seconds),
                    "message": "Auto tensioning; waiting for load cell.",
                }

        return {
            "coarse": False,
            "max_delta_lbs": PRELOAD_AUTO_FINAL_MAX_DELTA_LBS,
            "speed_percent": PRELOAD_AUTO_SPEED_PERCENT,
            "pulse_seconds": self._auto_preload_pulse_seconds(),
            "message": "Final auto tension tap; waiting for load cell.",
        }

    def _auto_preload_coarse_active_locked(self, load, increase):
        return bool(increase and load < PRELOAD_AUTO_COARSE_UNTIL_LBS)

    def _auto_preload_max_delta_lbs(self, load, coarse):
        if coarse:
            return PRELOAD_AUTO_COARSE_MAX_DELTA_LBS
        if load < PRELOAD_MIN_LBS:
            return PRELOAD_AUTO_APPROACH_MAX_DELTA_LBS
        return PRELOAD_AUTO_FINAL_MAX_DELTA_LBS

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
        try:
            while time.monotonic() < end_time:
                time.sleep(min(check_interval, max(0.0, end_time - time.monotonic())))
                with self.lock:
                    load = float(self.state.get("current_load") or 0.0)
                    rate = self._auto_preload_load_rate_locked()
                    predicted_load = load + max(0.0, rate) * PRELOAD_AUTO_PREDICT_LOOKAHEAD_SECONDS
                    if self.state.get("test_running"):
                        self.state["auto_preload_message"] = "Auto tension cancelled because a pull test started."
                        return False
                    if load > PRELOAD_AUTO_ABORT_LBS:
                        self.actuator.stop()
                        self.state["actuator_command"] = self.actuator.last_command
                        self.state["auto_preload_message"] = (
                            f"Auto tension exceeded {PRELOAD_AUTO_ABORT_LBS:.1f} lb at {load:.1f} lb. Reset before testing."
                        )
                        return False
                    if increase:
                        if load >= PRELOAD_MIN_LBS:
                            self.actuator.stop()
                            self.state["actuator_command"] = self.actuator.last_command
                            self.state["auto_preload_message"] = "Auto tension paused inside the allowed band."
                            return True
                        if predicted_load >= PRELOAD_AUTO_PREDICT_STOP_LBS:
                            self.actuator.stop()
                            self.state["actuator_command"] = self.actuator.last_command
                            self.state["auto_preload_message"] = "Auto tension paused before predicted overshoot."
                            return True
                        if max_delta_lbs and load - start_load >= max_delta_lbs:
                            self.actuator.stop()
                            self.state["actuator_command"] = self.actuator.last_command
                            self.state["auto_preload_message"] = "Auto tension paused after load changed quickly."
                            return True
                        if load >= PRELOAD_MAX_LBS:
                            self.actuator.stop()
                            self.state["actuator_command"] = self.actuator.last_command
                            return True
            return True
        finally:
            with self.lock:
                self.actuator.stop()
                self.state["actuator_command"] = self.actuator.last_command

    def _wait_for_auto_preload_settle(self, deadline, coarse=False):
        settle_seconds = PRELOAD_AUTO_COARSE_SETTLE_SECONDS if coarse else PRELOAD_AUTO_SETTLE_SECONDS
        max_seconds = PRELOAD_AUTO_COARSE_SETTLE_MAX_SECONDS if coarse else PRELOAD_AUTO_SETTLE_MAX_SECONDS
        started = time.monotonic()
        while time.monotonic() < deadline:
            elapsed = time.monotonic() - started
            with self.lock:
                stable = self._auto_preload_load_stable_locked()
                rate = self._auto_preload_load_rate_locked()
            if coarse and elapsed >= max(0.0, settle_seconds):
                if rate <= PRELOAD_AUTO_MAX_RISE_RATE_LBS_PER_SECOND:
                    return
            if elapsed >= settle_seconds and stable:
                return
            if elapsed >= max_seconds:
                return
            time.sleep(0.05)

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

    def _load_stable_locked(self):
        if len(self.load_history) < 3:
            return False
        values = [value for _, value in self.load_history]
        return max(values) - min(values) <= LOAD_STABLE_DELTA_LBS

    def _auto_preload_load_stable_locked(self):
        now = time.monotonic()
        cutoff = now - max(0.2, PRELOAD_AUTO_STABLE_WINDOW_SECONDS)
        values = [value for sample_time, value in self.load_history if sample_time >= cutoff]
        if len(values) < 3:
            return False
        return max(values) - min(values) <= PRELOAD_AUTO_STABLE_DELTA_LBS

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
        self.state["stop_reason"] = f"{reason}; logging until load stabilizes"

    def _finish_stop_locked(self, reason):
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
        self.state["auto_preload_running"] = False
        self.state["auto_preload_message"] = ""

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
