import threading
import time

from config import (
    APP_VERSION,
    DISCONNECT_STOP_SECONDS,
    FAILURE_CONFIRM_SAMPLES,
    FAILURE_DROP_LBS,
    FAILURE_DROP_PERCENT,
    FAILURE_MIN_PEAK_LBS,
    MAX_FORCE_LBS,
    MAX_TEST_SECONDS,
    PRELOAD_TARGET_LBS,
    PRELOAD_TOLERANCE_LBS,
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
        self.state = {
            "current_load": 0.0,
            "raw_load": 0.0,
            "peak_load": 0.0,
            "preload_ready": False,
            "test_running": False,
            "test_complete": False,
            "active_test_id": None,
            "started_at_monotonic": None,
            "elapsed_s": 0.0,
            "sample_count": 0,
            "stop_reason": "",
            "last_error": "",
            "actuator_command": "neutral",
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
            status["app_version"] = APP_VERSION
            self.last_client_poll = time.monotonic()
            return status

    def jog(self, action):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot jog while a pull test is running."
            if action == "up":
                ok = self.actuator.move_up(fast=True)
            elif action == "down":
                ok = self.actuator.move_down(fast=True)
            elif action == "stop":
                ok = self.actuator.stop()
            else:
                return False, "Unknown jog action."
            self.state["actuator_command"] = self.actuator.last_command
            return ok, self.actuator.last_error

    def tare(self):
        with self.lock:
            if self.state["test_running"]:
                return False, "Cannot tare while a pull test is running."
            ok = self.load_cell.tare()
            return ok, self.load_cell.last_error

    def start_pull(self, test_id):
        with self.lock:
            if self.state["test_running"]:
                return False, "A pull test is already running."
            test = storage.get_test(test_id)
            if not test:
                return False, "Test record not found."

            load = float(self.state["current_load"])
            self.failure_drop_samples = 0
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
                    "last_error": "",
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
            storage.add_event("Pull started", test_id=test_id, data={"initial_load_lbs": load})
            ok = self.actuator.pull()
            self.state["actuator_command"] = self.actuator.last_command
            if not ok:
                self._stop_locked("actuator fault")
                return False, self.actuator.last_error
            return True, "Pull started."

    def stop(self, reason="operator stop"):
        with self.lock:
            self._stop_locked(reason)
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
                    self._stop_locked("control loop fault")
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
            self.state["preload_ready"] = load >= (PRELOAD_TARGET_LBS - PRELOAD_TOLERANCE_LBS)

            if not self.state["test_running"]:
                return

            test_id = self.state["active_test_id"]
            start_time = self.state["started_at_monotonic"] or time.monotonic()
            elapsed_s = time.monotonic() - start_time
            self.state["elapsed_s"] = elapsed_s
            self.state["peak_load"] = max(self.state["peak_load"], load)
            sample_count = storage.add_sample(test_id, elapsed_s, load, raw_counts)
            self.state["sample_count"] = sample_count

            stop_reason = self._stop_reason_locked(load, elapsed_s)
            if stop_reason:
                self._stop_locked(stop_reason)

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

    def _stop_locked(self, reason):
        self.actuator.stop()
        self.state["actuator_command"] = self.actuator.last_command
        test_id = self.state.get("active_test_id")
        peak = round(float(self.state.get("peak_load") or 0.0), 3)
        sample_count = int(self.state.get("sample_count") or 0)
        was_running = bool(self.state.get("test_running"))
        self.failure_drop_samples = 0

        self.state["test_running"] = False
        self.state["test_complete"] = True if test_id else False
        self.state["stop_reason"] = reason

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
