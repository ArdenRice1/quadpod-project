import sys
import tempfile
import unittest
import zipfile
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
        exporter.PHOTO_DIR = self.root / "photos"
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
                "failure_type": "Glue gave way",
                "operator_notes": "Result notes",
                "deviation_from_standard": "yes",
                "deviation_description": "Minor angle shift",
                "effect_on_uncertainty": "Low",
                "approved_by": "Engineer",
                "approved_date": "2026-05-25",
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
        self.assertEqual(row["operator_notes"], "Result notes")
        self.assertEqual(row["deviation_description"], "Minor angle shift")

    def test_bundle_contains_job_csv_audit_test_csv_and_optional_photo(self):
        job_id = storage.create_job({"project_name": "Bundle Job"})
        photo_dir = Path(exporter.PHOTO_DIR)
        photo_dir.mkdir(parents=True, exist_ok=True)
        photo_path = photo_dir / "field-photo.jpg"
        photo_path.write_bytes(b"photo")
        test_id = storage.create_test(
            job_id,
            {
                "test_number": "1",
                "photo_reference": "field-photo.jpg",
                "failure_type": "Shingle tear",
                "deviation_from_standard": "yes",
                "effect_on_uncertainty": "Medium",
                "approved_by": "Engineer",
            },
        )
        storage.add_sample(test_id, 0.0, 10.0)
        storage.update_test(test_id, status="complete", peak_load_lbs=10.0, sample_count=1)

        bundle = exporter.export_job_bundle(job_id)

        self.assertTrue(Path(bundle).exists())
        self.assertGreater(Path(bundle).stat().st_size, 0)
        with zipfile.ZipFile(bundle) as zf:
            names = set(zf.namelist())
            self.assertIn("job_and_tests.csv", names)
            self.assertIn("audit.json", names)
            self.assertIn(f"tests/test_{test_id}.csv", names)
            self.assertIn("photos/field-photo.jpg", names)
            job_csv = zf.read("job_and_tests.csv").decode("utf-8")
            trace = zf.read(f"tests/test_{test_id}.csv").decode("utf-8")
            audit = zf.read("audit.json").decode("utf-8")
        self.assertIn("Shingle tear", job_csv)
        self.assertIn("effect_on_uncertainty,Medium", trace)
        self.assertIn("machine_settings", audit)

    def test_job_folder_export_uses_same_csv_layout(self):
        job_id = storage.create_job({"project_name": "USB Job", "job_number": "USB-001"})
        test_id = storage.create_test(job_id, {"test_number": "1"})
        storage.add_sample(test_id, 0.0, 10.0)

        folder = exporter.export_job_folder(job_id, self.root / "usb")

        self.assertTrue((Path(folder) / "job_and_tests.csv").exists())
        self.assertTrue((Path(folder) / "audit.json").exists())
        self.assertTrue((Path(folder) / "tests" / f"test_{test_id}.csv").exists())


if __name__ == "__main__":
    unittest.main()
