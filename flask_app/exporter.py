import json
import zipfile
from pathlib import Path

from config import APP_VERSION, EXPORT_DIR
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
    path = Path(EXPORT_DIR) / f"test_{test_id}_trace.csv"
    rows = storage.list_samples(test_id)
    fieldnames = ["timestamp", "elapsed_s", "force_lbs", "raw_lbs"]
    return storage.write_csv(path, rows, fieldnames)


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
            f"<td>{_h(row['test_completed_at'])}</td>"
            f"<td>{_h(row['roof_temperature_f'])}</td>"
            f"<td>{_h(row['wind_speed_direction'])}</td>"
            f"<td>{_h(row['operator_notes'])}</td>"
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
      <tr><th>Test #</th><th>Angle</th><th>Max Load (lbs)</th><th>Time</th><th>Roof Temp</th><th>Wind</th><th>Notes</th></tr>
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
    return bundle_path


def _h(value):
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
