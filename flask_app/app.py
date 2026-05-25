import datetime as dt
import os
import sys
from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import APP_VERSION, EMAIL_ENABLED, EMAIL_TO, HOTSPOT_IP, PHOTO_DIR, SECRET_KEY
import storage

storage.init_db()

from engine import quadpod_engine  # noqa: E402
import email_queue  # noqa: E402
import exporter  # noqa: E402


app = Flask(__name__)
app.secret_key = SECRET_KEY

if EMAIL_ENABLED:
    email_queue.start_worker()


@app.context_processor
def inject_globals():
    return {
        "app_version": APP_VERSION,
        "active_job": storage.get_job(session.get("job_id")) if session.get("job_id") else None,
        "hotspot_ip": HOTSPOT_IP,
    }


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        form = _form_payload(storage.JOB_FIELDS)
        job_id = storage.create_job(form)
        session["job_id"] = job_id
        session.pop("test_id", None)
        return redirect(url_for("pretest"))

    today = dt.date.today().isoformat()
    return render_template("home.html", defaults={"date": today})


@app.route("/job/<int:job_id>/resume")
def resume_job(job_id):
    if not storage.get_job(job_id):
        return redirect(url_for("exports"))
    session["job_id"] = job_id
    session.pop("test_id", None)
    return redirect(url_for("pretest"))


@app.route("/pretest", methods=["GET", "POST"])
def pretest():
    job_id = session.get("job_id")
    if not job_id or not storage.get_job(job_id):
        return redirect(url_for("home"))

    if request.method == "POST":
        form = _form_payload(storage.TEST_FIELDS)
        photo = request.files.get("photo")
        if photo and photo.filename:
            form["photo_reference"] = _save_photo(job_id, form.get("test_number", ""), photo)
        test_id = storage.create_test(job_id, form)
        session["test_id"] = test_id
        return redirect(url_for("test"))

    tests = storage.list_tests(job_id)
    defaults = {
        "test_number": str(len(tests) + 1),
        "air_temperature_f": "",
        "roof_temperature_f": "",
    }
    return render_template("pretest.html", defaults=defaults, tests=tests)


@app.route("/test")
def test():
    test_id = session.get("test_id")
    if not test_id or not storage.get_test(test_id):
        return redirect(url_for("pretest"))
    test_record = storage.get_test(test_id)
    job = storage.get_job(test_record["job_id"])
    return render_template("test.html", job=job, test=test_record)


@app.route("/result", methods=["GET", "POST"])
def result():
    test_id = session.get("test_id")
    if not test_id or not storage.get_test(test_id):
        return redirect(url_for("pretest"))

    test_record = storage.get_test(test_id)
    if request.method == "POST":
        form = _form_payload(storage.TEST_FIELDS)
        storage.update_test(test_id, form=form, status="complete")
        storage.add_event("Result reviewed", test_id=test_id)
        session.pop("test_id", None)
        return redirect(url_for("pretest"))

    return render_template("result.html", test=test_record, samples=storage.list_samples(test_id))


@app.route("/exports")
def exports():
    jobs = storage.list_jobs()
    queue = storage.list_email_queue()
    return render_template("exports.html", jobs=jobs, queue=queue, email_to=EMAIL_TO)


@app.route("/network")
def network():
    return render_template("network.html", status=quadpod_engine.snapshot())


@app.route("/job/<int:job_id>/complete", methods=["POST"])
def complete_job(job_id):
    form = {"end_time": dt.datetime.now().strftime("%H:%M")}
    storage.update_job(job_id, form=form, status="complete")
    session.pop("job_id", None)
    session.pop("test_id", None)
    return redirect(url_for("exports"))


@app.route("/job/<int:job_id>/summary.csv")
def download_summary(job_id):
    return send_file(exporter.export_job_summary_csv(job_id), as_attachment=True)


@app.route("/test/<int:test_id>/trace.csv")
def download_trace(test_id):
    return send_file(exporter.export_test_trace_csv(test_id), as_attachment=True)


@app.route("/job/<int:job_id>/bundle.zip")
def download_bundle(job_id):
    return send_file(exporter.export_job_bundle(job_id), as_attachment=True)


@app.route("/job/<int:job_id>/email", methods=["POST"])
def email_job(job_id):
    recipient = request.form.get("recipient", EMAIL_TO).strip()
    if not recipient:
        return redirect(url_for("exports"))
    bundle = exporter.export_job_bundle(job_id)
    subject = f"Quadpod job {job_id} export"
    body = "Attached is the Quadpod field export bundle. If the Pi was offline, this email may have been sent after the field work was completed."
    email_queue.queue_job_email(job_id, recipient, subject, body, bundle)
    return redirect(url_for("exports"))


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION, "status": quadpod_engine.snapshot()})


@app.route("/api/status")
def api_status():
    return jsonify(quadpod_engine.snapshot())


@app.route("/api/jog", methods=["POST"])
def api_jog():
    data = request.get_json(silent=True) or {}
    ok, message = quadpod_engine.jog(data.get("action", "stop"))
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/tare", methods=["POST"])
def api_tare():
    ok, message = quadpod_engine.tare()
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/start_pull", methods=["POST"])
def api_start_pull():
    test_id = session.get("test_id")
    if not test_id:
        data = request.get_json(silent=True) or {}
        test_id = data.get("test_id")
    ok, message = quadpod_engine.start_pull(int(test_id))
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.get_json(silent=True) or {}
    quadpod_engine.stop(data.get("reason", "operator stop"))
    return jsonify({"ok": True, "status": quadpod_engine.snapshot()})


@app.route("/api/email/process", methods=["POST"])
def api_process_email():
    return jsonify({"message": email_queue.process_once()})


def _form_payload(fields):
    payload = {}
    for field in fields:
        if field in request.form:
            payload[field] = request.form.get(field, "")
    for checkbox in [
        "calibration_verified",
        "weather_checked",
        "occupants_notified",
        "safety_acknowledged",
        "deviation_from_standard",
    ]:
        if checkbox in fields:
            payload[checkbox] = "yes" if checkbox in request.form else "no"
    return payload


def _save_photo(job_id, test_number, file_storage):
    photo_dir = Path(PHOTO_DIR)
    photo_dir.mkdir(parents=True, exist_ok=True)
    original = secure_filename(file_storage.filename)
    stem = secure_filename(f"job_{job_id}_test_{test_number}") or f"job_{job_id}"
    filename = f"{stem}_{int(dt.datetime.now().timestamp())}_{original}"
    path = photo_dir / filename
    file_storage.save(path)
    return filename


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
