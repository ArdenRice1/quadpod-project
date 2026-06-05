import csv
import json
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
    PRELOAD_TARGET_LBS,
    PRELOAD_TOLERANCE_LBS,
    PULL_TARGET_IN_PER_MIN,
    VICTOR_PULL_US,
)
import storage


def export_job_summary_csv(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    rows = [storage.build_export_row(job, test) for test in storage.list_tests(job_id)]
    path = Path(EXPORT_DIR) / f"job_{job_id}_summary.csv"
    return storage.write_csv(path, rows, storage.EXPORT_FIELDS)


def export_test_trace_csv(test_id):
    test = storage.get_test(test_id)
    if not test:
        raise ValueError("Test not found")
    job = storage.get_job(test["job_id"])
    if not job:
        raise ValueError("Job not found")

    path = Path(EXPORT_DIR) / f"test_{test_id}_trace.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = storage.list_samples(test_id)

    metadata = [
        ("Quadpod Test Trace", ""),
        ("software_version", test.get("software_version") or APP_VERSION),
        ("job_id", job["id"]),
        ("project_name", job["form"].get("project_name", "")),
        ("project_address", job["form"].get("project_address", "")),
        ("job_number", job["form"].get("job_number", "")),
        ("test_id", test["id"]),
        ("test_number", test["form"].get("test_number", "")),
        ("test_area", test["form"].get("test_area", "")),
        ("roof_area", test["form"].get("roof_area", "")),
        ("angle_degrees", test["form"].get("angle_degrees", "")),
        ("shingle_manufacturer", test["form"].get("shingle_manufacturer", "")),
        ("shingle_product", test["form"].get("shingle_product", "")),
        ("air_temperature_f", test["form"].get("air_temperature_f", "")),
        ("roof_temperature_f", test["form"].get("roof_temperature_f", "")),
        ("wind_speed_direction", test["form"].get("wind_speed_direction", "")),
        ("started_at", test.get("started_at") or ""),
        ("completed_at", test.get("completed_at") or ""),
        ("initial_preload_lbs", _value(test.get("initial_preload_lbs"))),
        ("peak_load_lbs", _value(test.get("peak_load_lbs"))),
        ("stop_reason", test.get("stop_reason") or ""),
        ("sample_count", test.get("sample_count") or 0),
        ("failure_type", test["form"].get("failure_type", "")),
        ("operator_notes", test["form"].get("operator_notes", "")),
        ("deviation_from_standard", test["form"].get("deviation_from_standard", "")),
        ("deviation_description", test["form"].get("deviation_description", "")),
        ("effect_on_uncertainty", test["form"].get("effect_on_uncertainty", "")),
        ("approved_by", test["form"].get("approved_by", "")),
        ("approved_date", test["form"].get("approved_date", "")),
        ("photo_reference", test["form"].get("photo_reference", "")),
        ("final_reading_photo", test["form"].get("final_reading_photo", "")),
        ("repair_needed", test["form"].get("repair_needed", "")),
        ("repair_completed", test["form"].get("repair_completed", "")),
        ("sample_removed", test["form"].get("sample_removed", "")),
        ("maintenance_notified", test["form"].get("maintenance_notified", "")),
        ("pull_target_in_per_min", PULL_TARGET_IN_PER_MIN),
        ("victor_pull_us", VICTOR_PULL_US),
        ("pull_direction", ACTUATOR_PULL_DIRECTION),
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for key, value in metadata:
            writer.writerow([key, value])
        writer.writerow([])
        writer.writerow(["Samples"])
        writer.writerow(["timestamp", "elapsed_s", "force_lbs", "raw_counts"])
        for sample in samples:
            writer.writerow(
                [
                    sample.get("timestamp", ""),
                    _value(sample.get("elapsed_s")),
                    _value(sample.get("force_lbs")),
                    _value(sample.get("raw_lbs")),
                ]
            )
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


def render_report_html(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    tests = storage.list_tests(job_id)
    rows = [storage.build_export_row(job, test) for test in tests]
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f"<td>{_h(row['test_number'])}</td>"
            f"<td>{_h(row['angle_degrees'])}</td>"
            f"<td>{_h(row['max_load_lbs'])}</td>"
            f"<td>{_h(row['failure_type'])}</td>"
            f"<td>{_h(row['test_completed_at'])}</td>"
            f"<td>{_h(row['roof_temperature_f'])}</td>"
            f"<td>{_h(row['wind_speed_direction'])}</td>"
            f"<td>{_h(row['deviation_from_standard'])}</td>"
            f"<td>{_h(row['operator_notes'])}</td>"
            "</tr>"
            "<tr>"
            f"<td colspan=\"9\">"
            f"<strong>Deviation:</strong> {_h(row['deviation_description'])} "
            f"<strong>Uncertainty:</strong> {_h(row['effect_on_uncertainty'])} "
            f"<strong>Approved:</strong> {_h(row['approved_by'])} {_h(row['approved_date'])} "
            f"<strong>Photo:</strong> {_h(row['photo_reference'])} "
            f"<strong>Closeout:</strong> repair needed {_h(row['repair_needed'])}, "
            f"repair completed {_h(row['repair_completed'])}, sample removed {_h(row['sample_removed'])}, "
            f"maintenance notified {_h(row['maintenance_notified'])}. {_h(row['post_test_notes'])}"
            "</td>"
            "</tr>"
        )
    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Quadpod Job {job_id} Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #111; }}
    h1, h2 {{ margin: 0 0 12px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #555; padding: 6px 8px; text-align: left; }}
    th {{ background: #eee; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 24px; }}
    .label {{ font-weight: bold; }}
  </style>
</head>
<body>
  <h1>APEC Quadpod Field Report</h1>
  <p>Field ASTM-aligned shingle uplift resistance record. Strict ASTM certification requires APEC review of the licensed standard and apparatus validation.</p>
  <h2>Job</h2>
  <div class="grid">
    <div><span class="label">Project:</span> {_h(job['form'].get('project_name'))}</div>
    <div><span class="label">Job #:</span> {_h(job['form'].get('job_number'))}</div>
    <div><span class="label">Address:</span> {_h(job['form'].get('project_address'))}</div>
    <div><span class="label">Date:</span> {_h(job['form'].get('date'))}</div>
    <div><span class="label">Foreman:</span> {_h(job['form'].get('foreman'))}</div>
    <div><span class="label">Building #:</span> {_h(job['form'].get('building_number'))}</div>
  </div>
  <h2>Tests</h2>
  <table>
    <thead>
      <tr><th>Test #</th><th>Angle</th><th>Max Load (lbs)</th><th>Failure</th><th>Time</th><th>Roof Temp</th><th>Wind</th><th>Deviation</th><th>Notes</th></tr>
    </thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
</body>
</html>"""
    path = Path(EXPORT_DIR) / f"job_{job_id}_report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def export_job_bundle(job_id):
    job = storage.get_job(job_id)
    if not job:
        raise ValueError("Job not found")
    export_dir = Path(EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)

    summary_path = Path(export_job_summary_csv(job_id))
    report_path = Path(render_report_html(job_id))
    audit_path = export_dir / f"job_{job_id}_audit.json"
    audit_path.write_text(json.dumps(build_audit_payload(job_id), indent=2), encoding="utf-8")

    trace_paths = [Path(export_test_trace_csv(test["id"])) for test in storage.list_tests(job_id)]

    bundle_path = export_dir / f"quadpod_job_{job_id}_bundle.zip"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(summary_path, "summary.csv")
        zf.write(report_path, "report.html")
        zf.write(audit_path, "audit.json")
        for path in trace_paths:
            zf.write(path, f"traces/{path.name}")
        for photo_path in _job_photo_paths(job_id):
            zf.write(photo_path, f"photos/{photo_path.name}")
    return bundle_path


def machine_settings():
    return {
        "app_version": APP_VERSION,
        "victor_pull_us": VICTOR_PULL_US,
        "pull_direction": ACTUATOR_PULL_DIRECTION,
        "pull_target_in_per_min": PULL_TARGET_IN_PER_MIN,
        "preload_target_lbs": PRELOAD_TARGET_LBS,
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


def _value(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def _h(value):
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
