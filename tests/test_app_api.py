import sys
import tempfile
import unittest
import importlib.util
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage

if importlib.util.find_spec("flask") is None:
    app = None
else:
    import app as app_module
    from app import app

@unittest.skipIf(app is None, "Flask is not installed in this Python environment")
class AppApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()
        self.original_export_dir = app_module.exporter.EXPORT_DIR
        app_module.exporter.EXPORT_DIR = self.root / "exports"
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        if app is not None:
            app_module.exporter.EXPORT_DIR = self.original_export_dir
        self.tempdir.cleanup()

    def test_start_pull_rejects_missing_session_token(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-token"
            session["test_id"] = 1
        response = self.client.post(
            "/api/start_pull",
            json={"test_id": 1},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["ok"])

    def test_start_pull_rejects_bad_test_id(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-token"
        response = self.client.post(
            "/api/start_pull",
            json={"test_id": "bad"},
            headers={"X-CSRF-Token": "test-token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("test_id", response.get_json()["message"])

    def test_result_save_preserves_pretest_checklist_fields(self):
        job_id = storage.create_job(
            {
                "project_name": "Result Preserve Job",
                "job_number": "RP-001",
                "load_cell_id": "LC-1",
                "load_cell_calibration_date": "2099-01-01",
                "ir_temp_gun_id": "IR-1",
                "ir_temp_gun_calibration_date": "2099-01-01",
            }
        )
        test_id = storage.create_test(
            job_id,
            {
                "test_number": "1",
                "angle_degrees": "90",
            },
        )
        with self.client.session_transaction() as session:
            session["test_id"] = test_id

        response = self.client.post(
            "/result",
            data={
                "failure_type": "Operator stop",
                "operator_notes": "Saved result notes",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        form = storage.get_test(test_id)["form"]
        self.assertEqual(form["failure_type"], "Operator stop")
        self.assertEqual(form["operator_notes"], "Saved result notes")

    def test_home_post_updates_active_job_instead_of_creating_new_one(self):
        first = {
            "project_name": "Original Project",
            "project_address": "1 Main",
            "date": "2026-06-06",
            "job_number": "J-1",
            "foreman": "Foreman",
            "load_cell_id": "LC-1",
            "load_cell_calibration_date": "2024-01-01",
            "ir_temp_gun_id": "IR-1",
            "ir_temp_gun_calibration_date": "2024-01-01",
        }
        second = dict(first, project_name="Updated Project")

        self.client.post("/", data=first)
        self.client.post("/", data=second)

        jobs = storage.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["form"]["project_name"], "Updated Project")

    def test_home_remembers_equipment_defaults_for_new_jobs(self):
        first = {
            "project_name": "Equipment Project",
            "project_address": "1 Main",
            "date": "2026-06-06",
            "job_number": "J-1",
            "foreman": "Foreman",
            "load_cell_id": "LC-200",
            "load_cell_calibration_date": "2026-01-02",
            "ir_temp_gun_id": "IR-77",
            "ir_temp_gun_calibration_date": "2026-02-03",
        }
        self.client.post("/", data=first)
        with self.client.session_transaction() as session:
            session.pop("job_id", None)
            session.pop("test_id", None)

        response = self.client.get("/")
        text = response.get_data(as_text=True)

        self.assertIn('name="load_cell_id" value="LC-200"', text)
        self.assertIn('name="load_cell_calibration_date" type="date" value="2026-01-02"', text)
        self.assertIn('name="ir_temp_gun_id" value="IR-77"', text)
        self.assertIn('name="ir_temp_gun_calibration_date" type="date" value="2026-02-03"', text)

    def test_pretest_post_updates_current_unstarted_test(self):
        job_id = storage.create_job(
            {
                "project_name": "Setup Preserve Job",
                "project_address": "1 Main",
                "date": "2026-06-06",
                "job_number": "SP-1",
                "foreman": "Foreman",
                "load_cell_id": "LC-1",
                "load_cell_calibration_date": "2024-01-01",
                "ir_temp_gun_id": "IR-1",
                "ir_temp_gun_calibration_date": "2024-01-01",
            }
        )
        with self.client.session_transaction() as session:
            session["job_id"] = job_id

        base_form = {
            "test_number": "1",
            "test_area": "Area A",
            "angle_degrees": "90",
        }
        self.client.post("/pretest", data=base_form)
        edited = dict(base_form, test_area="Area B")
        self.client.post("/pretest", data=edited)

        tests = storage.list_tests(job_id)
        self.assertEqual(len(tests), 1)
        self.assertEqual(tests[0]["form"]["test_area"], "Area B")

    def test_archive_search_filters_jobs(self):
        storage.create_job({"project_name": "Alpha Roof", "job_number": "A-1"})
        storage.create_job({"project_name": "Beta Roof", "job_number": "B-1"})

        response = self.client.get("/archive?q=Alpha")

        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn("Alpha Roof", text)
        self.assertNotIn("Beta Roof", text)

    def test_setup_tools_are_collapsed_by_default(self):
        response = self.client.get("/setup-check")

        self.assertEqual(response.status_code, 200)
        text = response.get_data(as_text=True)
        self.assertIn('<details class="tool-panel" id="networkPanel">', text)
        self.assertIn('<details class="tool-panel" id="calibrationPanel">', text)
        self.assertNotIn('id="networkPanel" open', text)
        self.assertNotIn('id="calibrationPanel" open', text)

    def test_operator_pages_hide_internal_tension_config(self):
        job_id = storage.create_job(
            {
                "project_name": "UI Gate Job",
                "job_number": "UI-1",
                "load_cell_id": "LC-1",
                "load_cell_calibration_date": "2024-01-01",
                "ir_temp_gun_id": "IR-1",
                "ir_temp_gun_calibration_date": "2024-01-01",
            }
        )
        test_id = storage.create_test(job_id, {"test_number": "1", "angle_degrees": "90"})
        with self.client.session_transaction() as session:
            session["job_id"] = job_id
            session["test_id"] = test_id

        pretest_text = self.client.get("/pretest").get_data(as_text=True)
        test_text = self.client.get("/test").get_data(as_text=True)
        combined = pretest_text + test_text

        for hidden in [
            "preload_min_lbs",
            "preload_max_lbs",
            "preload_target_lbs",
            "auto_preload_drift_drop_lbs",
            "auto_preload_short_stable",
            "auto_preload_drift_stable",
            "last_pulse_us",
        ]:
            self.assertNotIn(hidden, combined)
        self.assertNotIn("Settling.", combined)
        self.assertNotIn(" us)", combined)

    def test_archive_hides_email_feature_by_default(self):
        storage.create_job({"project_name": "No Email Job", "job_number": "NE-1"})

        text = self.client.get("/archive").get_data(as_text=True)

        self.assertNotIn("Email Queue", text)
        self.assertNotIn("Queue Email", text)
        self.assertNotIn("Try Sending Now", text)

    def test_copy_job_usb_redirects_with_visible_success(self):
        job_id = storage.create_job({"project_name": "USB Job", "job_number": "USB-001"})
        test_id = storage.create_test(job_id, {"test_number": "1"})
        storage.add_sample(test_id, 0.0, 10.0)

        copied_path = self.root / "exports" / "usb_copy" / "USB_Job_USB-001"
        with patch.object(app_module.exporter, "copy_job_to_usb", return_value=copied_path):
            response = self.client.post(f"/job/{job_id}/copy-usb", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertIn("copy_status=ok", response.headers["Location"])

        final = self.client.get(response.headers["Location"])
        text = final.get_data(as_text=True)
        self.assertIn("Job folder copied to", text)

    def test_wifi_switch_returns_transition_before_scheduling_command(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "network-test-token"
        with patch.object(app_module, "_schedule_network_command") as schedule:
            response = self.client.post(
                "/setup/network",
                data={
                    "ssid": "Office WiFi",
                    "password": "secret-password",
                    "csrf_token": "network-test-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Switching to Wi-Fi", response.get_data(as_text=True))
        schedule.assert_called_once()
        command = schedule.call_args.args[0]
        self.assertIn("switch_network.py", command[1])
        self.assertEqual(command[-5:], ["wifi", "--ssid", "Office WiFi", "--password", "secret-password"])

    def test_network_status_includes_saved_wifi_profiles(self):
        def fake_run(command, **kwargs):
            joined = " ".join(command)
            if "connection show --active" in joined:
                return SimpleNamespace(returncode=0, stdout="Office WiFi:802-11-wireless:wlan0\n", stderr="")
            if "connection show" in joined:
                return SimpleNamespace(
                    returncode=0,
                    stdout="Office WiFi:802-11-wireless\nquadpod-hotspot:802-11-wireless\n",
                    stderr="",
                )
            if "dev wifi list" in joined:
                return SimpleNamespace(returncode=0, stdout="Office WiFi:88:WPA2\nGuest:55:WPA2\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(app_module.subprocess, "run", side_effect=fake_run):
            status = app_module._network_status()

        self.assertEqual(status["saved_wifi"], [{"ssid": "Office WiFi"}])
        office = next(wifi for wifi in status["wifi"] if wifi["ssid"] == "Office WiFi")
        guest = next(wifi for wifi in status["wifi"] if wifi["ssid"] == "Guest")
        self.assertTrue(office["saved"])
        self.assertFalse(guest["saved"])

    def test_hotspot_switch_returns_transition_before_scheduling_command(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "network-test-token"
        with patch.object(app_module, "_schedule_network_command") as schedule:
            response = self.client.post(
                "/setup/hotspot",
                data={"csrf_token": "network-test-token"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Starting Quadpod Hotspot", response.get_data(as_text=True))
        schedule.assert_called_once()
        command, label, event_data = schedule.call_args.args
        self.assertIn("switch_network.py", command[1])
        self.assertEqual(command[-1], "hotspot")
        self.assertEqual(label, "Hotspot connection")
        self.assertEqual(event_data, {})

    def test_network_switch_rejects_missing_session_token(self):
        with patch.object(app_module, "_schedule_network_command") as schedule:
            response = self.client.post("/setup/hotspot")

        self.assertEqual(response.status_code, 403)
        self.assertIn("Network Change Not Started", response.get_data(as_text=True))
        schedule.assert_not_called()

    def test_network_switch_scheduler_blocks_duplicate_requests(self):
        class FakeThread:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                pass

        app_module._network_command_until = 0.0
        try:
            with patch.object(app_module.threading, "Thread", FakeThread):
                first = app_module._schedule_network_command(["true"], "Wi-Fi connection", {})
                second = app_module._schedule_network_command(["true"], "Wi-Fi connection", {})

            self.assertTrue(first)
            self.assertFalse(second)
        finally:
            app_module._network_command_until = 0.0

    def test_power_status_decodes_undervoltage_history(self):
        completed = SimpleNamespace(stdout="throttled=0x50000\n", returncode=0)
        with patch.object(app_module.subprocess, "run", return_value=completed):
            status = app_module._power_status()

        self.assertEqual(status["kind"], "warn")
        self.assertIn("undervoltage", status["message"])
        self.assertIn("throttling", status["message"])


if __name__ == "__main__":
    unittest.main()
