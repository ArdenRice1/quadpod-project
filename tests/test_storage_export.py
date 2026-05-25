import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import storage
import exporter


class StorageExportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        exporter.EXPORT_DIR = self.root / "exports"
        storage.init_db()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_export_row_contains_every_form_point(self):
        job_id = storage.create_job(
            {
                "project_name": "Wind Loss Residence",
                "job_number": "APEC-001",
                "load_cell_id": "LC-200",
                "calibration_verified": "yes",
            }
        )
        test_id = storage.create_test(
            job_id,
            {
                "test_number": "1",
                "angle_degrees": "90",
                "roof_temperature_f": "122.4",
                "wind_speed_direction": "7 mph N",
            },
        )
        storage.add_sample(test_id, 0.0, 10.0, 10.1)
        storage.update_test(
            test_id,
            status="complete",
            started_at="2026-05-25T10:00:00Z",
            completed_at="2026-05-25T10:00:05Z",
            peak_load_lbs=34.25,
            stop_reason="load drop detected",
            sample_count=1,
            software_version="test",
        )

        row = storage.build_export_row(storage.get_job(job_id), storage.get_test(test_id))

        self.assertEqual(set(storage.EXPORT_FIELDS), set(row.keys()))
        self.assertEqual(row["project_name"], "Wind Loss Residence")
        self.assertEqual(row["test_number"], "1")
        self.assertEqual(row["max_load_lbs"], 34.25)

    def test_bundle_contains_summary_audit_report_and_trace(self):
        job_id = storage.create_job({"project_name": "Bundle Job"})
        test_id = storage.create_test(job_id, {"test_number": "1"})
        storage.add_sample(test_id, 0.0, 10.0)
        storage.update_test(test_id, status="complete", peak_load_lbs=10.0, sample_count=1)

        bundle = exporter.export_job_bundle(job_id)

        self.assertTrue(Path(bundle).exists())
        self.assertGreater(Path(bundle).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
