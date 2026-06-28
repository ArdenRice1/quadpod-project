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


if __name__ == "__main__":
    unittest.main()
