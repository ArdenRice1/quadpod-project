import datetime as dt
import os
import secrets
import subprocess
import sys
import threading
import time
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

from config import (
    APP_VERSION,
    DATABASE_PATH,
    EMAIL_ENABLED,
    EMAIL_TO,
    EXPORT_DIR,
    HOTSPOT_IP,
    PHOTO_DIR,
    PUBLIC_URL,
    SECRET_KEY,
)
import storage

storage.init_db()

from engine import quadpod_engine  # noqa: E402
import email_queue  # noqa: E402
import exporter  # noqa: E402


app = Flask(__name__)
app.secret_key = SECRET_KEY

CHECKBOX_FIELDS = [
    "deviation_from_standard",
]

RESULT_CHECKBOX_FIELDS = [
    "deviation_from_standard",
]

NETWORK_COMMAND_LOCKOUT_SECONDS = 45
_network_command_lock = threading.Lock()
_network_command_until = 0.0

if EMAIL_ENABLED:
    email_queue.start_worker()


@app.context_processor
def inject_globals():
    return {
        "app_version": APP_VERSION,
        "active_job": storage.get_job(session.get("job_id")) if session.get("job_id") else None,
        "hotspot_ip": HOTSPOT_IP,
        "public_url": PUBLIC_URL,
        "csrf_token": _csrf_token(),
    }


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        form = _form_payload(storage.JOB_FIELDS)
        job_id = session.get("job_id")
        if job_id and storage.get_job(job_id):
            storage.update_job(job_id, form=form, status="active")
        else:
            job_id = storage.create_job(form)
        session["job_id"] = job_id
        session.pop("test_id", None)
        return redirect(url_for("pretest"))

    today = dt.date.today().isoformat()
    active = storage.get_job(session.get("job_id")) if session.get("job_id") else None
    defaults = dict(active["form"]) if active else {"date": today}
    defaults.setdefault("date", today)
    return render_template("home.html", defaults=defaults)


@app.route("/setup-check")
def setup_check():
    status = quadpod_engine.snapshot()
    power = _power_status()
    checks = [
        ("Open app", "good", "Use %s or fallback http://%s" % (PUBLIC_URL, HOTSPOT_IP)),
        ("Load cell", "good" if status["load_cell"]["ok"] else "bad", status["load_cell"]["last_error"] or "Ready"),
        ("Actuator", "good" if status["actuator"]["ok"] else "bad", status["actuator"]["last_error"] or "Ready"),
    ]
    if power["message"]:
        checks.append(("Pi power", power["kind"], power["message"]))
    paths = {
        "database": DATABASE_PATH,
        "exports": str(EXPORT_DIR),
    }
    return render_template(
        "setup_check.html",
        status=status,
        checks=checks,
        paths=paths,
    )


@app.route("/job/<int:job_id>/resume")
def resume_job(job_id):
    if not storage.get_job(job_id):
        return redirect(url_for("exports"))
    session["job_id"] = job_id
    current_test = _current_editable_test(job_id)
    if current_test:
        session["test_id"] = current_test["id"]
    else:
        session.pop("test_id", None)
    return redirect(url_for("pretest"))


@app.route("/pretest", methods=["GET", "POST"])
def pretest():
    job_id = session.get("job_id")
    job = storage.get_job(job_id) if job_id else None
    if not job:
        if request.method == "POST":
            return redirect(url_for("home"))
        return render_template(
            "pretest.html",
            defaults={
                "test_number": "",
                "air_temperature_f": "",
                "roof_temperature_f": "",
                "shingle_type": "",
            },
            tests=[],
            job_required=True,
        )

    if request.method == "POST":
        form = _form_payload(storage.TEST_FIELDS)
        photo = request.files.get("photo")
        if photo and photo.filename:
            form["photo_reference"] = _save_photo(job_id, form.get("test_number", ""), photo)
        current_test = _current_editable_test(job_id)
        if current_test:
            test_id = current_test["id"]
            storage.update_test(test_id, form=form, status=current_test["status"])
        else:
            test_id = storage.create_test(job_id, form)
        session["test_id"] = test_id
        return redirect(url_for("test"))

    tests = storage.list_tests(job_id)
    current_test = _current_editable_test(job_id)
    if current_test:
        session["test_id"] = current_test["id"]
        defaults = dict(current_test["form"])
    else:
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
        form = _form_payload(storage.TEST_FIELDS, checkbox_fields=RESULT_CHECKBOX_FIELDS)
        storage.update_test(test_id, form=form, status="complete")
        storage.add_event("Result reviewed", test_id=test_id)
        session.pop("test_id", None)
        return redirect(url_for("pretest"))

    return render_template("result.html", test=test_record, samples=storage.list_samples(test_id))


@app.route("/exports")
def exports():
    return redirect(url_for("archive"))


@app.route("/archive")
def archive():
    query = request.args.get("q", "")
    jobs = storage.search_jobs(query)
    queue = storage.list_email_queue()
    return render_template(
        "archive.html",
        jobs=jobs,
        queue=queue,
        email_to=EMAIL_TO,
        email_status=email_queue.configuration_status(),
        query=query,
    )


@app.route("/network")
def network():
    return render_template("network.html", status=quadpod_engine.snapshot())


@app.route("/api/network/status")
def api_network_status():
    return jsonify(_network_status())


@app.route("/setup/network", methods=["POST"])
def setup_network():
    guard = _require_form_token()
    if guard:
        return guard
    ssid = request.form.get("ssid", "").strip()
    password = request.form.get("password", "")
    if not ssid:
        return redirect(url_for("setup_check"))
    command = _network_switch_command("wifi", "--ssid", ssid)
    if password:
        command.extend(["--password", password])
    scheduled = _schedule_network_command(command, "Wi-Fi connection", {"ssid": ssid})
    heading = "Switching to Wi-Fi" if scheduled else "Network Switch Already Running"
    message = (
        f"Quadpod is leaving its hotspot and joining {ssid}. Connect this device to {ssid} if needed."
        if scheduled
        else "Quadpod is already changing networks. Wait a moment before trying again."
    )
    return render_template(
        "network_transition.html",
        heading=heading,
        message=message,
        target_url=f"{PUBLIC_URL}/setup-check",
        fallback_url="http://quadpod.local:5000/setup-check",
        delay_seconds=10,
    )


@app.route("/setup/hotspot", methods=["POST"])
def setup_hotspot():
    guard = _require_form_token()
    if guard:
        return guard
    scheduled = _schedule_network_command(
        _network_switch_command("hotspot"),
        "Hotspot connection",
        {},
    )
    heading = "Starting Quadpod Hotspot" if scheduled else "Network Switch Already Running"
    message = (
        "Quadpod is leaving Wi-Fi and starting its hotspot. Join the Quadpod Wi-Fi network, then reopen the app."
        if scheduled
        else "Quadpod is already changing networks. Wait a moment before trying again."
    )
    return render_template(
        "network_transition.html",
        heading=heading,
        message=message,
        target_url=f"http://{HOTSPOT_IP}/setup-check",
        fallback_url=f"http://{HOTSPOT_IP}:5000/setup-check",
        delay_seconds=10,
    )


@app.route("/api/calibrate", methods=["POST"])
def api_calibrate():
    guard = _require_command_token()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    try:
        known_lbs = float(data.get("known_lbs", 0))
    except (TypeError, ValueError):
        known_lbs = 0
    if known_lbs <= 0:
        return jsonify({"ok": False, "message": "Known weight must be greater than zero."}), 400
    ok, message = quadpod_engine.calibrate_load_cell(known_lbs)
    if ok:
        storage.add_event("Runtime load-cell calibration updated", data={"known_lbs": known_lbs, "message": message})
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


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


@app.route("/job/<int:job_id>/job-and-tests.csv")
def download_job_report(job_id):
    return send_file(exporter.export_job_report_csv(job_id), as_attachment=True)


@app.route("/test/<int:test_id>/trace.csv")
def download_trace(test_id):
    return send_file(exporter.export_test_trace_csv(test_id), as_attachment=True)


@app.route("/test/<int:test_id>/force-time.svg")
def download_force_time_graph(test_id):
    return send_file(exporter.export_force_time_graph_svg(test_id), mimetype="image/svg+xml")


@app.route("/job/<int:job_id>/bundle.zip")
def download_bundle(job_id):
    return send_file(exporter.export_job_bundle(job_id), as_attachment=True)


@app.route("/job/<int:job_id>/copy-usb", methods=["POST"])
def copy_job_usb(job_id):
    try:
        folder = exporter.copy_job_to_usb(job_id)
        storage.add_event("Job copied to USB/export folder", job_id=job_id, data={"path": str(folder)})
    except Exception as exc:
        storage.add_event("USB/export copy failed", level="error", job_id=job_id, data={"error": str(exc)})
    return redirect(url_for("exports"))


@app.route("/job/<int:job_id>/email", methods=["POST"])
def email_job(job_id):
    email_status = email_queue.configuration_status()
    if not email_status["configured"]:
        storage.add_event("Email request rejected", level="error", job_id=job_id, data=email_status)
        return redirect(url_for("archive"))
    recipient = request.form.get("recipient", EMAIL_TO).strip()
    if not recipient:
        return redirect(url_for("exports"))
    bundle = exporter.export_job_bundle(job_id)
    subject = f"Quadpod job {job_id} export"
    body = "Attached is the Quadpod field export bundle. If the Pi was offline, this email may have been sent after the field work was completed."
    email_queue.queue_job_email(job_id, recipient, subject, body, bundle)
    threading.Thread(target=email_queue.process_once, daemon=True).start()
    return redirect(url_for("exports"))


@app.route("/health")
def health():
    return jsonify({"ok": True, "version": APP_VERSION, "status": quadpod_engine.snapshot()})


@app.route("/api/status")
def api_status():
    return jsonify(quadpod_engine.snapshot())


@app.route("/api/jog", methods=["POST"])
def api_jog():
    guard = _require_command_token()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    ok, message = quadpod_engine.jog(data.get("action", "stop"), data.get("speed_percent"))
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/jog_speed", methods=["POST"])
def api_jog_speed():
    guard = _require_command_token()
    if guard:
        return guard
    data = request.get_json(silent=True) or {}
    try:
        speed = float(data.get("speed_percent", 100))
    except (TypeError, ValueError):
        speed = 100
    ok, message = quadpod_engine.set_jog_speed(speed)
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/auto_preload", methods=["POST"])
def api_auto_preload():
    guard = _require_command_token()
    if guard:
        return guard
    ok, message = quadpod_engine.auto_preload()
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/tare", methods=["POST"])
def api_tare():
    guard = _require_command_token()
    if guard:
        return guard
    ok, message = quadpod_engine.tare()
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/start_pull", methods=["POST"])
def api_start_pull():
    guard = _require_command_token()
    if guard:
        return guard
    test_id = session.get("test_id")
    if not test_id:
        data = request.get_json(silent=True) or {}
        test_id = data.get("test_id")
    try:
        test_id = int(test_id)
    except (TypeError, ValueError):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Valid test_id is required before starting a pull.",
                    "status": quadpod_engine.snapshot(),
                }
            ),
            400,
        )
    ok, message = quadpod_engine.start_pull(test_id)
    return jsonify({"ok": ok, "message": message, "status": quadpod_engine.snapshot()})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.get_json(silent=True) or {}
    quadpod_engine.stop(data.get("reason", "operator stop"))
    return jsonify({"ok": True, "status": quadpod_engine.snapshot()})


@app.route("/api/email/process", methods=["POST"])
def api_process_email():
    guard = _require_command_token()
    if guard:
        return guard
    return jsonify({"message": email_queue.process_once()})


def _form_payload(fields, checkbox_fields=None):
    payload = {}
    for field in fields:
        if field in request.form:
            payload[field] = request.form.get(field, "")
    if checkbox_fields is None:
        checkbox_fields = CHECKBOX_FIELDS
    for checkbox in checkbox_fields:
        if checkbox in fields:
            payload[checkbox] = "yes" if checkbox in request.form else "no"
    return payload


def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _require_command_token():
    token = request.headers.get("X-CSRF-Token", "")
    if not secrets.compare_digest(token, _csrf_token()):
        return jsonify({"ok": False, "message": "Session command token is invalid."}), 403
    return None


def _require_form_token():
    token = request.form.get("csrf_token", "")
    if not secrets.compare_digest(token, _csrf_token()):
        return render_template(
            "network_transition.html",
            heading="Network Change Not Started",
            message="This page session expired. Return to Setup Check and try again.",
            target_url=url_for("setup_check"),
            fallback_url=url_for("setup_check"),
            delay_seconds=3,
        ), 403
    return None


def _current_editable_test(job_id):
    test_id = session.get("test_id")
    if test_id:
        test = storage.get_test(test_id)
        if test and test["job_id"] == job_id and test["status"] in {"created", "running"}:
            return test
    for test in reversed(storage.list_tests(job_id)):
        if test["status"] in {"created", "running"}:
            return test
    return None


def _network_status():
    status = {
        "active": "Unavailable",
        "internet": "Unknown",
        "wifi": [],
        "message": "",
    }
    try:
        active = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if active.returncode == 0:
            status["active"] = active.stdout.strip() or "No active connection"
        else:
            status["message"] = active.stderr.strip() or "NetworkManager status unavailable"

        wifi = subprocess.run(
            ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list", "--rescan", "no"],
            check=False,
            capture_output=True,
            text=True,
            timeout=4,
        )
        if wifi.returncode == 0:
            seen = set()
            for line in wifi.stdout.splitlines():
                parts = line.split(":")
                ssid = parts[0].strip()
                if not ssid or ssid in seen:
                    continue
                seen.add(ssid)
                signal = parts[1].strip() if len(parts) > 1 else ""
                security = parts[2].strip() if len(parts) > 2 else ""
                status["wifi"].append({"ssid": ssid, "signal": signal, "security": security})
    except (OSError, subprocess.SubprocessError) as exc:
        status["message"] = f"Network tools unavailable: {exc}"

    try:
        internet = subprocess.run(
            [sys.executable, "-c", "import socket; socket.create_connection(('1.1.1.1', 53), 1).close()"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        status["internet"] = "Online" if internet.returncode == 0 else "Offline"
    except (OSError, subprocess.SubprocessError):
        status["internet"] = "Unknown"
    return status


def _power_status():
    try:
        result = subprocess.run(
            ["vcgencmd", "get_throttled"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return {"kind": "", "message": "", "flags": 0}
    match = result.stdout.strip().split("=")
    if len(match) != 2:
        return {"kind": "", "message": "", "flags": 0}
    try:
        flags = int(match[1], 16)
    except ValueError:
        return {"kind": "", "message": "", "flags": 0}

    current = []
    history = []
    labels = [
        (0, "undervoltage"),
        (1, "frequency capped"),
        (2, "throttling"),
        (3, "temperature limit"),
    ]
    for bit, label in labels:
        if flags & (1 << bit):
            current.append(label)
        if flags & (1 << (bit + 16)):
            history.append(label)
    if current:
        return {"kind": "bad", "message": "Current power warning: " + ", ".join(current), "flags": flags}
    if history:
        return {
            "kind": "warn",
            "message": "Power warning occurred since boot: " + ", ".join(history),
            "flags": flags,
        }
    return {"kind": "good", "message": "No Pi throttling or undervoltage flags", "flags": flags}


def _startup_power_alert():
    time.sleep(8)
    email_status = email_queue.configuration_status()
    if not email_status["configured"] or not EMAIL_TO:
        return
    power = _power_status()
    if power["kind"] not in {"warn", "bad"}:
        return

    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    except OSError:
        boot_id = "unknown-boot"
    marker = Path(DATABASE_PATH).parent / f".power-alert-{boot_id}-{power['flags']:x}"
    if marker.exists():
        return

    try:
        email_queue.send_alert(
            EMAIL_TO,
            f"Quadpod 003 power alert: {power['message']}",
            (
                "Quadpod 003 reported a Raspberry Pi power fault.\n\n"
                f"{power['message']}\n"
                f"Raw flags: 0x{power['flags']:x}\n\n"
                "Replace or reseat the Pi power supply and cable, reboot, and confirm "
                "`vcgencmd get_throttled` returns `throttled=0x0` before relying on "
                "network, USB, storage, or sensor behavior."
            ),
        )
        marker.touch()
        storage.add_event("Automatic Pi power alert emailed", data={"flags": power["flags"]})
    except Exception as exc:
        storage.add_event(
            "Automatic Pi power alert failed",
            level="error",
            data={"flags": power["flags"], "error": str(exc)},
        )


def _schedule_network_command(command, label, event_data):
    global _network_command_until
    now = time.monotonic()
    with _network_command_lock:
        if now < _network_command_until:
            storage.add_event(
                f"{label} ignored",
                level="warn",
                data={**event_data, "ok": False, "message": "Network switch already running"},
            )
            return False
        _network_command_until = now + NETWORK_COMMAND_LOCKOUT_SECONDS
    thread = threading.Thread(
        target=_run_network_command,
        args=(command, label, event_data),
        daemon=True,
    )
    thread.start()
    return True


def _run_network_command(command, label, event_data):
    global _network_command_until
    time.sleep(1.5)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=35,
        )
        message = (result.stdout or result.stderr).strip()
        storage.add_event(
            label,
            level="info" if result.returncode == 0 else "error",
            data={**event_data, "ok": result.returncode == 0, "message": message},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        storage.add_event(
            label,
            level="error",
            data={**event_data, "ok": False, "message": str(exc)},
        )
    finally:
        with _network_command_lock:
            _network_command_until = 0.0


def _network_switch_command(mode, *extra):
    script = Path(__file__).resolve().parents[1] / "scripts" / "switch_network.py"
    return [sys.executable, str(script), "--delay", "0", mode, *extra]


def _save_photo(job_id, test_number, file_storage):
    photo_dir = Path(PHOTO_DIR)
    photo_dir.mkdir(parents=True, exist_ok=True)
    original = secure_filename(file_storage.filename)
    stem = secure_filename(f"job_{job_id}_test_{test_number}") or f"job_{job_id}"
    filename = f"{stem}_{int(dt.datetime.now().timestamp())}_{original}"
    path = photo_dir / filename
    file_storage.save(path)
    return filename


if EMAIL_ENABLED:
    threading.Thread(target=_startup_power_alert, daemon=True).start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
