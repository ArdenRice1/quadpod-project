import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

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
                "shingle_type": "Architectural",
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
        self.assertEqual(row["shingle_type"], "Architectural")
        self.assertEqual(row["max_load_lbs"], 34.25)
        self.assertEqual(row["operator_notes"], "Result notes")
        self.assertEqual(row["deviation_description"], "Minor angle shift")

    def test_bundle_contains_job_csv_audit_test_csv_and_optional_photo(self):
        job_id = storage.create_job({"project_name": "Bundle Job", "job_number": "B-100"})
        photo_dir = Path(exporter.PHOTO_DIR)
        photo_dir.mkdir(parents=True, exist_ok=True)
        photo_path = photo_dir / "field-photo.jpg"
        photo_path.write_bytes(b"photo")
        test_id = storage.create_test(
            job_id,
            {
                "test_number": "1",
                "photo_reference": "field-photo.jpg",
                "shingle_type": "Three tab",
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
            self.assertIn("Bundle_Job_B-100_ALL.csv", names)
            self.assertIn("audit.json", names)
            self.assertIn("tests/Bundle_Job_B-100_Test-1.csv", names)
            self.assertIn("graphs/Bundle_Job_B-100_Test-1_force_time.svg", names)
            self.assertIn("photos/field-photo.jpg", names)
            job_csv = zf.read("Bundle_Job_B-100_ALL.csv").decode("utf-8")
            trace = zf.read("tests/Bundle_Job_B-100_Test-1.csv").decode("utf-8")
            audit = zf.read("audit.json").decode("utf-8")
        self.assertIn("Shingle tear", job_csv)
        self.assertIn("Three tab", job_csv)
        self.assertIn("Effect on Uncertainty,Medium", trace)
        self.assertIn("Timestamp,Elapsed Seconds,Sample #,Force (lbs)", trace)
        self.assertIn("machine_settings", audit)

    def test_csv_export_sections_cover_all_saved_form_fields(self):
        job_export_fields = (
            exporter.JOB_HEADER_FIELDS
            + exporter.EQUIPMENT_FIELDS
            + exporter.WEATHER_SAFETY_FIELDS
            + exporter.CONDITION_FIELDS
        )
        test_export_fields = (
            exporter.TEST_DETAIL_FIELDS
            + exporter.SITE_CHECK_FIELDS
            + exporter.RESULT_DETAIL_FIELDS
            + exporter.DEVIATION_FIELDS
        )

        self.assertEqual([], [field for field in storage.JOB_FIELDS if field not in job_export_fields])
        self.assertEqual([], [field for field in storage.TEST_FIELDS if field not in test_export_fields])

    def test_human_csv_exports_include_production_checklist_fields(self):
        job_id = storage.create_job(
            {
                "project_name": "Production Job",
                "job_number": "P-100",
                "calibration_verified": "yes",
                "weather_checked": "yes",
                "unsafe_wind": "no",
                "weather_bypass_reason": "Engineer approved gust check",
                "occupants_notified": "yes",
                "safety_acknowledged": "yes",
            }
        )
        test_id = storage.create_test(
            job_id,
            {
                "test_number": "3",
                "photo_reference": "field-photo.jpg",
                "site_clear_of_hazards": "yes",
                "site_representative": "Jane Field",
                "site_free_of_blemishes": "yes",
                "test_board_visible": "yes",
                "initial_reading_photo": "yes",
                "final_reading_photo": "yes",
                "repair_needed": "no",
                "repair_completed": "yes",
                "sample_removed": "no",
                "maintenance_notified": "yes",
                "post_test_notes": "Sealant checked after pull",
            },
        )
        storage.add_sample(test_id, 0.0, 1.0)

        job_csv = Path(exporter.export_job_report_csv(job_id)).read_text(encoding="utf-8")
        trace_csv = Path(exporter.export_test_trace_csv(test_id)).read_text(encoding="utf-8")

        self.assertIn("Weather & Safety", job_csv)
        self.assertIn("Calibration Verified,yes", job_csv)
        self.assertIn("Weather Bypass Reason,Engineer approved gust check", job_csv)
        self.assertIn("Site / Photo Checklist", trace_csv)
        self.assertIn("Photo Reference,field-photo.jpg", trace_csv)
        self.assertIn("Site Representative,Jane Field", trace_csv)
        self.assertIn("Post-Test Notes,Sealant checked after pull", trace_csv)

    def test_job_folder_export_uses_same_csv_layout(self):
        job_id = storage.create_job({"project_name": "USB Job", "job_number": "USB-001"})
        test_id = storage.create_test(job_id, {"test_number": "1"})
        storage.add_sample(test_id, 0.0, 10.0)

        folder = exporter.export_job_folder(job_id, self.root / "usb")

        self.assertTrue((Path(folder) / "USB_Job_USB-001_ALL.csv").exists())
        self.assertTrue((Path(folder) / "audit.json").exists())
        self.assertTrue((Path(folder) / "tests" / "USB_Job_USB-001_Test-1.csv").exists())
        self.assertTrue((Path(folder) / "tests" / "USB_Job_USB-001_Test-1_force_time.svg").exists())

    def test_usb_root_auto_mounts_before_falling_back_to_local_exports(self):
        mounted = self.root / "mounted-usb"

        with (
            patch.object(exporter, "USB_EXPORT_ROOT", ""),
            patch.object(exporter, "_mounted_usb_root", side_effect=[None, mounted]) as mounted_root,
            patch.object(exporter, "_auto_mount_usb_root", return_value=mounted) as auto_mount,
        ):
            self.assertEqual(exporter._usb_root(), mounted)

        self.assertEqual(mounted_root.call_count, 1)
        auto_mount.assert_called_once()

    def test_usb_copy_syncs_after_export(self):
        job_id = storage.create_job({"project_name": "Sync Job", "job_number": "SYNC-1"})
        storage.create_test(job_id, {"test_number": "1"})

        with patch.object(exporter, "_usb_root", return_value=self.root / "usb"), patch.object(exporter, "_sync_path") as sync_path:
            folder = exporter.copy_job_to_usb(job_id)

        sync_path.assert_called_once_with(folder)

    def test_removable_flag_parsing_does_not_treat_zero_string_as_true(self):
        self.assertFalse(exporter._is_removable("0"))
        self.assertTrue(exporter._is_removable("1"))
        self.assertTrue(exporter._is_removable(True))


if __name__ == "__main__":
    unittest.main()
