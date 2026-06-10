import sys
import tempfile
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage

if importlib.util.find_spec("flask") is None:
    app = None
else:
    from app import app

@unittest.skipIf(app is None, "Flask is not installed in this Python environment")
class AppApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
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


if __name__ == "__main__":
    unittest.main()
