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

    def test_start_pull_rejects_unarmed_session(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-token"
            session["test_id"] = 1
        response = self.client.post(
            "/api/start_pull",
            json={"test_id": 1},
            headers={"X-CSRF-Token": "test-token"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.get_json()["ok"])

    def test_start_pull_rejects_bad_test_id(self):
        with self.client.session_transaction() as session:
            session["csrf_token"] = "test-token"
            session["operator_armed"] = True
        response = self.client.post(
            "/api/start_pull",
            json={"test_id": "bad"},
            headers={"X-CSRF-Token": "test-token"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("test_id", response.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
