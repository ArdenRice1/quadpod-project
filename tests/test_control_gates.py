import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage
from engine import QuadpodEngine


class ControlGateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()
        self.engine = QuadpodEngine(use_mock=True)
        self.job_id = storage.create_job(self._job_form())
        self.test_id = storage.create_test(self.job_id, self._test_form())

    def tearDown(self):
        self.engine.stop("test cleanup")
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

    def test_start_rejects_low_preload(self):
        self._set_load(9.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("preload", message)

    def test_start_rejects_high_preload(self):
        self._set_load(11.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("preload", message)

    def test_start_rejects_load_cell_fault(self):
        self._set_load(10.0)
        self.engine.load_cell.last_error = "load cell test fault"
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("load cell test fault", message)

    def test_start_rejects_actuator_fault(self):
        self._set_load(10.0)
        self.engine.actuator.last_error = "actuator test fault"
        ok, message = self.engine.start_pull(self.test_id)
        self.assertFalse(ok)
        self.assertIn("actuator test fault", message)

    def test_start_succeeds_when_all_gates_pass(self):
        self._set_load(10.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)
        self.assertTrue(self.engine.state["test_running"])

    def test_start_accepts_recorded_past_calibration_dates(self):
        storage.update_job(
            self.job_id,
            form={
                "load_cell_calibration_date": "2024-01-01",
                "ir_temp_gun_calibration_date": "2024-01-01",
            },
        )
        self._set_load(10.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)

    def test_start_does_not_require_photo_reference(self):
        storage.update_test(self.test_id, form={"photo_reference": ""})
        self._set_load(10.0)
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
        self._set_load(10.0)
        ok, message = self.engine.start_pull(self.test_id)
        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()
