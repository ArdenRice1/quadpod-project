import csv
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

from config import (
    ACTUATOR_PULL_DIRECTION,
    APP_VERSION,
    EXPORT_DIR,
    FAILURE_CONFIRM_SAMPLES,
    FAILURE_DROP_LBS,
    FAILURE_DROP_PERCENT,
    FAILURE_MIN_PEAK_LBS,
    LOADCELL_REFERENCE_UNIT,
    PHOTO_DIR,
    PRELOAD_MAX_LBS,
    PRELOAD_MIN_LBS,
    PRELOAD_TARGET_LBS,
    PRELOAD_TOLERANCE_LBS,
    PULL_TARGET_IN_PER_MIN,
    USB_EXPORT_ROOT,
    VICTOR_PULL_US,
)
import storage


FIELD_LABELS = {
    "project_name": "Project Name",
    "project_address": "Address",
    "project_city_state_zip": "City, State, Zip",
    "contact_phone": "Contact Phone",
    "client_name": "Client",
    "client_address": "Client Address",
    "client_city_state_zip": "Client City, State, Zip",
    "client_phone": "Client Phone",
    "involved_party_1_name": "Involved Party",
    "involved_party_1_address": "Involved Party Address",
    "involved_party_1_city_state_zip": "Involved Party City, State, Zip",
    "involved_party_1_phone": "Involved Party Phone",
    "involved_party_2_name": "Involved Party 2",
    "involved_party_2_address": "Involved Party 2 Address",
    "involved_party_2_city_state_zip": "Involved Party 2 City, State, Zip",
    "involved_party_2_phone": "Involved Party 2 Phone",
    "date": "Date",
    "suspected_loss_date": "Date of Suspected Loss",
    "job_number": "Job #",
    "building_number": "Building #",
    "foreman": "Foreman",
    "tech_1": "Tech. 1",
    "tech_2": "Tech. 2",
    "start_time": "Start Time",
    "end_time": "End Time",
    "load_cell_id": "Load Cell #",
    "load_cell_calibration_date": "Load Cell Calibration Date",
    "ir_temp_gun_id": "IR Temp. Gun #",
    "ir_temp_gun_calibration_date": "IR Temp. Gun Calibration Date",
    "humidity_percent": "Humidity (%)",
    "barometric_pressure_inhg": "Barometric Pressure (inHg)",
    "weather_notes": "Weather Notes",
    "test_number": "Test #",
    "test_area": "Test Area",
    "roof_area": "Roof Area",
    "angle_degrees": "Angle",
    "air_temperature_f": "Air Temp. (F)",
    "roof_temperature_f": "Roof Temp. (F)",
    "wind_speed_direction": "Wind Speed & Direction",
    "shingle_type": "Shingle Type",
    "wind_lift_evidence": "Evidence of Wind Lift",
    "nail_observations": "Nail Size / Placement Notes",
    "started_at": "Started At",
    "completed_at": "Completed At",
    "initial_preload_lbs": "Initial Preload (lbs)",
    "peak_load_lbs": "Max Load Value (lbs)",
    "stop_reason": "Stop Reason",
    "sample_count": "Sample Count",
    "failure_type": "Failure Type",
    "operator_notes": "Notes",
    "deviation_from_standard": "Any deviations from standard method?",
    "deviation_description": "Description of Deviation",
    "effect_on_uncertainty": "Effect on Uncertainty",
    "approved_by": "Approved By",
    "approved_date": "Approved Date",
}

JOB_HEADER_FIELDS = [
    "project_name",
    "project_address",
    "project_city_state_zip",
    "contact_phone",
    "client_name",
    "client_address",
    "client_city_state_zip",
    "client_phone",
    "involved_party_1_name",
    "involved_party_1_address",
    "involved_party_1_city_state_zip",
    "involved_party_1_phone",
    "involved_party_2_name",
    "involved_party_2_address",
    "involved_party_2_city_state_zip",
    "involved_party_2_phone",
    "date",
    "suspected_loss_date",
    "job_number",
    "building_number",
    "foreman",
    "tech_1",
    "tech_2",
    "start_time",
    "end_time",
]

EQUIPMENT_FIELDS = [
    "load_cell_id",
    "load_cell_calibration_date",
    "ir_temp_gun_id",
    "ir_temp_gun_calibration_date",
]

CONDITION_FIELDS = [
    "humidity_percent",
    "barometric_pressure_inhg",
    "weather_notes",
]

TEST_DETAIL_FIELDS = [
    "test_number",
    "test_area",
    "roof_area",
    "angle_degrees",
    "shingle_type",
    "air_temperature_f",
    "roof_temperature_f",
    "wind_speed_direction",
    "wind_lift_evidence",
    "nail_observations",
]

RESULT_DETAIL_FIELDS = [
    "started_at",
    "completed_at",
    "initial_preload_lbs",
    "peak_load_lbs",
    "stop_reason",
    "sample_count",
    "failure_type",
    "operator_notes",
]

DEVIATION_FIELDS = [
    "deviation_from_standard",
    "deviation_description",
    "effect_on_uncertainty",
    "approved_by",
    "approved_date",
]

JOB_TEST_TABLE = [
    ("test_number", "Test #"),
    ("angle_degrees", "Angle"),
    ("shingle_type", "Shingle Type"),
    ("peak_load_lbs", "Max Load Value (lbs)"),
    ("completed_at", "Time"),
    ("roof_temperature_f", "Temp."),
    ("wind_speed_direction", "Wind Speed & Direction"),
    ("failure_type", "Failure Type"),
    ("operator_notes", "Notes"),
]


def export_job_summary_csv(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    return export_job_report_csv(job_id)


def export_job_report_csv(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    tests = storage.list_tests(job_id)
    path = Path(EXPORT_DIR) / f"{_job_all_csv_name(job)}"
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["APEC Quadpod Job Record", ""])
        writer.writerow(["Software Version", APP_VERSION])
        writer.writerow(["Job ID", job["id"]])
        writer.writerow(["Status", job["status"]])
        writer.writerow([])
        _write_field_section(writer, "Job Information", job["form"], JOB_HEADER_FIELDS)
        _write_field_section(writer, "Equipment", job["form"], EQUIPMENT_FIELDS)
        _write_field_section(writer, "Conditions", job["form"], CONDITION_FIELDS)
        writer.writerow([])
        writer.writerow(["Test Summary"])
        writer.writerow([label for _, label in JOB_TEST_TABLE])
        for test in tests:
            row = _combined_row(job, test)
            writer.writerow([_format_value(row.get(field, "")) for field, _ in JOB_TEST_TABLE])
        writer.writerow([])
        writer.writerow(["Deviation Records"])
        writer.writerow(["Test #", "Any Deviations?", "Description of Deviation", "Effect on Uncertainty", "Approved By", "Approved Date"])
        for test in tests:
            row = _combined_row(job, test)
            writer.writerow(
                [
                    row.get("test_number", ""),
                    _yes_no(row.get("deviation_from_standard", "")),
                    row.get("deviation_description", ""),
                    row.get("effect_on_uncertainty", ""),
                    row.get("approved_by", ""),
                    row.get("approved_date", ""),
                ]
            )
        writer.writerow([])
        writer.writerow(["End Job Record", ""])
    return path


def export_test_trace_csv(test_id):
    test = storage.get_test(test_id)
    if not test:
        raise ValueError("Test not found")
    job = storage.get_job(test["job_id"])
    if not job:
        raise ValueError("Job not found")

    path = Path(EXPORT_DIR) / _test_csv_name(job, test)
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = storage.list_samples(test_id)
    row = _combined_row(job, test)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["APEC Quadpod Test Record", ""])
        writer.writerow(["Software Version", test.get("software_version") or APP_VERSION])
        writer.writerow(["Job ID", job["id"]])
        writer.writerow(["Test ID", test["id"]])
        writer.writerow([])
        _write_field_section(writer, "Job Information", job["form"], ["project_name", "job_number", "project_address", "date", "building_number", "foreman"])
        _write_field_section(writer, "Equipment", job["form"], EQUIPMENT_FIELDS)
        writer.writerow([])
        _write_field_section(writer, "Test Information", row, TEST_DETAIL_FIELDS)
        _write_field_section(writer, "Results", row, RESULT_DETAIL_FIELDS)
        writer.writerow(["Samples"])
        writer.writerow(["Timestamp", "Elapsed Seconds", "Sample #", "Force (lbs)"])
        for index, sample in enumerate(samples, start=1):
            writer.writerow(
                [
                    sample.get("timestamp", ""),
                    _value(sample.get("elapsed_s")),
                    index,
                    _value(sample.get("force_lbs")),
                ]
            )
        writer.writerow([])
        _write_field_section(writer, "Deviation Record", row, DEVIATION_FIELDS)
        writer.writerow([])
        writer.writerow(["Machine Settings"])
        for key, value in machine_settings().items():
            writer.writerow([_labelize(key), value])
    return path


def export_force_time_graph_svg(test_id):
    test = storage.get_test(test_id)
    if not test:
        raise ValueError("Test not found")
    job = storage.get_job(test["job_id"])
    if not job:
        raise ValueError("Job not found")

    graph_dir = Path(EXPORT_DIR) / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / f"{Path(_test_csv_name(job, test)).stem}_force_time.svg"
    samples = storage.list_samples(test_id)
    path.write_text(_force_time_svg(job, test, samples), encoding="utf-8")
    return path


def build_audit_payload(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    tests = storage.list_tests(job_id)
    return {
        "app": "Quadpod",
        "software_version": APP_VERSION,
        "job": job,
        "tests": tests,
        "field_policy": {
            "compliance_target": "field ASTM-aligned",
            "strict_astm_certification": False,
            "all_form_points_exported_per_test": True,
        },
        "machine_settings": machine_settings(),
    }


def export_job_bundle(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    export_dir = Path(EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)

    composite_path = Path(export_job_report_csv(job_id))
    audit_path = export_dir / f"job_{job_id}_audit.json"
    audit_path.write_text(json.dumps(build_audit_payload(job_id), indent=2), encoding="utf-8")

    tests = storage.list_tests(job_id)
    trace_paths = [Path(export_test_trace_csv(test["id"])) for test in tests]
    graph_paths = [Path(export_force_time_graph_svg(test["id"])) for test in tests]

    bundle_path = export_dir / f"{_job_export_zip_name(job)}"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(composite_path, composite_path.name)
        zf.write(audit_path, "audit.json")
        for path in trace_paths:
            zf.write(path, f"tests/{path.name}")
        for path in graph_paths:
            zf.write(path, f"graphs/{path.name}")
        for photo_path in _job_photo_paths(job_id):
            zf.write(photo_path, f"photos/{photo_path.name}")
    return bundle_path


def export_job_folder(job_id, root_dir):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    root = Path(root_dir)
    folder = root / _job_folder_name(job)
    tests_dir = folder / "tests"
    photos_dir = folder / "photos"
    tests_dir.mkdir(parents=True, exist_ok=True)
    photos_dir.mkdir(parents=True, exist_ok=True)

    composite_path = Path(export_job_report_csv(job_id))
    audit_path = Path(EXPORT_DIR) / f"job_{job_id}_audit.json"
    audit_path.write_text(json.dumps(build_audit_payload(job_id), indent=2), encoding="utf-8")
    shutil.copy2(composite_path, folder / composite_path.name)
    shutil.copy2(audit_path, folder / "audit.json")
    for test in storage.list_tests(job_id):
        trace_path = Path(export_test_trace_csv(test["id"]))
        graph_path = Path(export_force_time_graph_svg(test["id"]))
        shutil.copy2(trace_path, tests_dir / trace_path.name)
        shutil.copy2(graph_path, tests_dir / graph_path.name)
    for photo_path in _job_photo_paths(job_id):
        shutil.copy2(photo_path, photos_dir / photo_path.name)
    return folder


def copy_job_to_usb(job_id):
    return export_job_folder(job_id, _usb_root())


def machine_settings():
    return {
        "app_version": APP_VERSION,
        "victor_pull_us": VICTOR_PULL_US,
        "pull_direction": ACTUATOR_PULL_DIRECTION,
        "pull_target_in_per_min": PULL_TARGET_IN_PER_MIN,
        "preload_target_lbs": PRELOAD_TARGET_LBS,
        "preload_min_lbs": PRELOAD_MIN_LBS,
        "preload_max_lbs": PRELOAD_MAX_LBS,
        "preload_tolerance_lbs": PRELOAD_TOLERANCE_LBS,
        "loadcell_reference_unit": LOADCELL_REFERENCE_UNIT,
        "failure_drop_lbs": FAILURE_DROP_LBS,
        "failure_drop_percent": FAILURE_DROP_PERCENT,
        "failure_confirm_samples": FAILURE_CONFIRM_SAMPLES,
        "failure_min_peak_lbs": FAILURE_MIN_PEAK_LBS,
    }


def _job_photo_paths(job_id):
    paths = []
    photo_dir = Path(PHOTO_DIR)
    for test in storage.list_tests(job_id):
        reference = test["form"].get("photo_reference", "")
        if not reference:
            continue
        candidate = photo_dir / Path(reference).name
        if candidate.is_file():
            paths.append(candidate)
    return paths


def _job_folder_name(job):
    return _slug(_job_base_name(job) or f"job_{job['id']}")


def _job_all_csv_name(job):
    return f"{_job_base_name(job)}_ALL.csv"


def _job_export_zip_name(job):
    return f"{_job_base_name(job)}_EXPORT.zip"


def _test_csv_name(job, test):
    test_number = test["form"].get("test_number") or test["id"]
    return f"{_job_base_name(job)}_Test-{_slug(test_number)}.csv"


def _job_base_name(job):
    project = job["form"].get("project_name") or "Project"
    job_number = job["form"].get("job_number") or f"Job-{job['id']}"
    return _slug(f"{project}_{job_number}")


def _usb_root():
    if USB_EXPORT_ROOT:
        return Path(USB_EXPORT_ROOT)
    candidates = []
    for base in [Path("/media"), Path("/mnt")]:
        if not base.exists():
            continue
        candidates.extend(path for path in base.glob("*/*") if path.is_dir())
        candidates.extend(path for path in base.glob("*") if path.is_dir())
    writable = [path for path in candidates if _is_writable_dir(path)]
    if writable:
        return writable[0]
    return Path(EXPORT_DIR) / "usb_copy"


def _is_writable_dir(path):
    try:
        probe = path / ".quadpod_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _slug(value):
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return text.strip("_") or "quadpod_job"


def _combined_row(job, test):
    row = {}
    row.update(job["form"])
    row.update(test["form"])
    row.update(
        {
            "started_at": test.get("started_at") or "",
            "completed_at": test.get("completed_at") or "",
            "initial_preload_lbs": _value(test.get("initial_preload_lbs")),
            "peak_load_lbs": _value(test.get("peak_load_lbs")),
            "stop_reason": test.get("stop_reason") or "",
            "sample_count": test.get("sample_count") or 0,
        }
    )
    return row


def _force_time_svg(job, test, samples):
    width = 900
    height = 420
    left = 64
    right = 24
    top = 46
    bottom = 58
    plot_w = width - left - right
    plot_h = height - top - bottom
    test_number = test["form"].get("test_number") or test["id"]
    title = f"Quadpod Force-Time - Test {test_number}"
    subtitle = f"{job['form'].get('project_name') or 'Project'} / {job['form'].get('job_number') or 'Job'}"

    if samples:
        max_t = max(float(sample.get("elapsed_s") or 0.0) for sample in samples) or 1.0
        max_f = max(float(sample.get("force_lbs") or 0.0) for sample in samples) or 1.0
    else:
        max_t = 1.0
        max_f = 1.0
    max_f = max(10.0, max_f * 1.1)

    def x(elapsed):
        return left + (float(elapsed or 0.0) / max_t) * plot_w

    def y(force):
        return top + plot_h - (float(force or 0.0) / max_f) * plot_h

    points = " ".join(
        f"{x(sample.get('elapsed_s')):.1f},{y(sample.get('force_lbs')):.1f}" for sample in samples
    )
    if not points:
        points = f"{left},{top + plot_h}"

    y_ticks = []
    for index in range(5):
        value = (max_f / 4) * index
        yy = y(value)
        y_ticks.append(
            f'<line x1="{left}" y1="{yy:.1f}" x2="{width - right}" y2="{yy:.1f}" stroke="#e1e6eb"/>'
            f'<text x="{left - 10}" y="{yy + 4:.1f}" text-anchor="end">{value:.0f}</text>'
        )

    x_ticks = []
    for index in range(5):
        value = (max_t / 4) * index
        xx = x(value)
        x_ticks.append(
            f'<line x1="{xx:.1f}" y1="{top}" x2="{xx:.1f}" y2="{top + plot_h}" stroke="#eef2f5"/>'
            f'<text x="{xx:.1f}" y="{height - 22}" text-anchor="middle">{value:.1f}</text>'
        )

    peak = max((float(sample.get("force_lbs") or 0.0) for sample in samples), default=0.0)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <text x="{left}" y="24" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#15191d">{html.escape(title)}</text>
  <text x="{left}" y="42" font-family="Arial, sans-serif" font-size="12" fill="#66727f">{html.escape(subtitle)} - peak {peak:.2f} lb - samples {len(samples)}</text>
  <g font-family="Arial, sans-serif" font-size="11" fill="#66727f">
    {''.join(y_ticks)}
    {''.join(x_ticks)}
  </g>
  <rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="none" stroke="#9aa7b2"/>
  <polyline fill="none" stroke="#136f63" stroke-width="3" points="{points}"/>
  <text x="{left + plot_w / 2:.1f}" y="{height - 6}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#66727f">Elapsed seconds</text>
  <text transform="translate(18 {top + plot_h / 2:.1f}) rotate(-90)" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#66727f">Force (lbs)</text>
</svg>
'''


def _write_field_section(writer, title, data, fields):
    writer.writerow([title, ""])
    writer.writerow(["Field", "Value"])
    for field in fields:
        value = _format_value(data.get(field, ""))
        if value != "":
            writer.writerow([FIELD_LABELS.get(field, _labelize(field)), value])
    writer.writerow([])


def _format_value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def _yes_no(value):
    return "Yes" if str(value).strip().lower() == "yes" else "No"


def _labelize(value):
    return str(value).replace("_", " ").strip().title()


def _value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value
