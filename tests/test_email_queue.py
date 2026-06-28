import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "flask_app"))

import email_queue
import storage


class EmailQueueTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        storage.DATA_DIR = self.root
        storage.DATABASE_PATH = str(self.root / "quadpod.db")
        storage.init_db()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_smtp_message_targets_requested_recipient_with_attachment(self):
        attachment = self.root / "Project_Job_EXPORT.zip"
        attachment.write_bytes(b"quadpod export")
        item = {
            "recipient": "aydenreese1430@gmail.com",
            "subject": "Quadpod email verification",
            "body": "Attached is a Quadpod test export.",
            "attachment_path": str(attachment),
        }
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with (
            patch.object(email_queue, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_queue, "SMTP_PORT", 587),
            patch.object(email_queue, "SMTP_USE_TLS", True),
            patch.object(email_queue, "SMTP_USERNAME", "quadpod@example.com"),
            patch.object(email_queue, "SMTP_PASSWORD", "app-password"),
            patch.object(email_queue, "EMAIL_FROM", "quadpod@example.com"),
            patch.object(email_queue.smtplib, "SMTP", return_value=smtp),
        ):
            email_queue._send(item)

        smtp.starttls.assert_called_once()
        smtp.login.assert_called_once_with("quadpod@example.com", "app-password")
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "aydenreese1430@gmail.com")
        self.assertEqual(message["Subject"], "Quadpod email verification")
        self.assertEqual(message.get_payload()[1].get_filename(), "Project_Job_EXPORT.zip")

    def test_alert_email_does_not_require_attachment(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with (
            patch.object(email_queue, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_queue, "SMTP_PORT", 587),
            patch.object(email_queue, "SMTP_USE_TLS", True),
            patch.object(email_queue, "SMTP_USERNAME", "quadpod@example.com"),
            patch.object(email_queue, "SMTP_PASSWORD", "app-password"),
            patch.object(email_queue, "EMAIL_FROM", "quadpod@example.com"),
            patch.object(email_queue.smtplib, "SMTP", return_value=smtp),
        ):
            email_queue.send_alert(
                "aydenreese1430@gmail.com",
                "Quadpod 003 power alert",
                "Undervoltage detected.",
            )

        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "aydenreese1430@gmail.com")
        self.assertEqual(message["Subject"], "Quadpod 003 power alert")
        self.assertFalse(message.is_multipart())

    def test_process_once_sanitizes_smtp_auth_failure_for_operator(self):
        attachment = self.root / "Project_Job_EXPORT.zip"
        attachment.write_bytes(b"quadpod export")
        job_id = storage.create_job({"project_name": "Email Test", "job_number": "E-1"})
        storage.queue_email(
            job_id,
            "field@example.com",
            "Quadpod export",
            "Attached.",
            str(attachment),
        )

        error = email_queue.smtplib.SMTPAuthenticationError(
            535, b"5.7.8 Username and Password not accepted"
        )
        with (
            patch.object(email_queue, "EMAIL_ENABLED", True),
            patch.object(email_queue, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_queue, "EMAIL_FROM", "quadpod@example.com"),
            patch.object(email_queue, "_send", side_effect=error),
        ):
            message = email_queue.process_once()

        self.assertEqual(
            message,
            "Email sign-in failed. Update the Gmail app password in email settings.",
        )
        row = storage.list_email_queue()[0]
        self.assertIn("Username and Password", row["last_error"])

    def test_smtp_login_strips_gmail_app_password_spaces(self):
        msg = email_queue.EmailMessage()
        msg["From"] = "quadpod@example.com"
        msg["To"] = "field@example.com"
        msg["Subject"] = "Test"
        msg.set_content("Body")
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp

        with (
            patch.object(email_queue, "SMTP_HOST", "smtp.example.com"),
            patch.object(email_queue, "SMTP_PORT", 587),
            patch.object(email_queue, "SMTP_USE_TLS", True),
            patch.object(email_queue, "SMTP_USERNAME", "quadpod@example.com"),
            patch.object(email_queue, "SMTP_PASSWORD", "abcd efgh ijkl mnop"),
            patch.object(email_queue, "EMAIL_FROM", "quadpod@example.com"),
            patch.object(email_queue.smtplib, "SMTP", return_value=smtp),
        ):
            email_queue._send_message(msg)

        smtp.login.assert_called_once_with("quadpod@example.com", "abcdefghijklmnop")

    def test_new_queued_email_is_selected_before_old_retry(self):
        job_id = storage.create_job({"project_name": "Email Test", "job_number": "E-1"})
        old_id = storage.queue_email(
            job_id, "old@example.com", "Old", "Body", str(self.root / "old.zip")
        )
        storage.mark_email_failed(old_id, RuntimeError("old failure"), max_attempts=5)
        new_id = storage.queue_email(
            job_id, "new@example.com", "New", "Body", str(self.root / "new.zip")
        )

        item = storage.next_queued_email(max_attempts=5)

        self.assertEqual(item["id"], new_id)

    def test_email_retry_becomes_failed_at_max_attempts(self):
        job_id = storage.create_job({"project_name": "Email Test", "job_number": "E-1"})
        queue_id = storage.queue_email(
            job_id, "field@example.com", "Export", "Body", str(self.root / "export.zip")
        )

        storage.mark_email_failed(queue_id, RuntimeError("first"), max_attempts=2)
        storage.mark_email_failed(queue_id, RuntimeError("second"), max_attempts=2)

        row = storage.list_email_queue()[0]
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["attempts"], 2)

    def test_retire_email_retries_marks_stuck_retry_failed(self):
        job_id = storage.create_job({"project_name": "Email Test", "job_number": "E-1"})
        queue_id = storage.queue_email(
            job_id, "field@example.com", "Export", "Body", str(self.root / "export.zip")
        )
        with storage.db() as conn:
            conn.execute(
                "UPDATE email_queue SET status='retry', attempts=8 WHERE id=?",
                (queue_id,),
            )

        storage.retire_email_retries(max_attempts=5)

        row = storage.list_email_queue()[0]
        self.assertEqual(row["status"], "failed")


if __name__ == "__main__":
    unittest.main()
