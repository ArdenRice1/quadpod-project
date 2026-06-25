import mimetypes
import smtplib
import threading
import time
from email.message import EmailMessage
from pathlib import Path

from config import (
    EMAIL_ENABLED,
    EMAIL_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USERNAME,
)
import storage


def configuration_status():
    if not EMAIL_ENABLED:
        return {
            "configured": False,
            "message": "Email sending is disabled. Configure SMTP environment values to enable it.",
        }
    missing = []
    if not SMTP_HOST:
        missing.append("SMTP host")
    if not EMAIL_FROM:
        missing.append("from address")
    if missing:
        return {
            "configured": False,
            "message": "Email settings are incomplete: " + ", ".join(missing),
        }
    return {"configured": True, "message": "Email sending is configured."}


def queue_job_email(job_id, recipient, subject, body, attachment_path):
    return storage.queue_email(job_id, recipient, subject, body, str(attachment_path))


def process_once():
    status = configuration_status()
    if not status["configured"]:
        return status["message"]
    item = storage.next_queued_email()
    if not item:
        return "No queued email"

    try:
        _send(item)
        storage.mark_email_sent(item["id"])
        return f"Sent queue item {item['id']}"
    except Exception as exc:
        storage.mark_email_failed(item["id"], exc)
        return f"Email queue item {item['id']} failed: {exc}"


def start_worker(interval_s=300):
    thread = threading.Thread(target=_worker_loop, args=(interval_s,), daemon=True)
    thread.start()
    return thread


def _worker_loop(interval_s):
    while True:
        process_once()
        time.sleep(interval_s)


def _send(item):
    if not SMTP_HOST or not EMAIL_FROM:
        raise RuntimeError("SMTP settings are incomplete")

    attachment_path = Path(item["attachment_path"])
    if not attachment_path.exists():
        raise FileNotFoundError(attachment_path)

    msg = EmailMessage()
    msg["From"] = EMAIL_FROM
    msg["To"] = item["recipient"]
    msg["Subject"] = item["subject"]
    msg.set_content(item["body"])

    mime_type, _ = mimetypes.guess_type(attachment_path.name)
    maintype, subtype = (mime_type or "application/zip").split("/", 1)
    msg.add_attachment(
        attachment_path.read_bytes(),
        maintype=maintype,
        subtype=subtype,
        filename=attachment_path.name,
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(msg)
