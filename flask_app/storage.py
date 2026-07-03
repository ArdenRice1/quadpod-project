import csv
import datetime as dt
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DATABASE_PATH, DATA_DIR


JOB_FIELDS = [
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
    "load_cell_id",
    "load_cell_calibration_date",
    "ir_temp_gun_id",
    "ir_temp_gun_calibration_date",
    "calibration_verified",
    "weather_checked",
    "unsafe_wind",
    "lightning_present",
    "rain_or_moisture",
    "heat_or_cold_hazard",
    "ice_present",
    "weather_bypass_approved",
    "weather_bypass_reason",
    "occupants_notified",
    "safety_acknowledged",
    "humidity_percent",
    "barometric_pressure_inhg",
    "weather_notes",
]

TEST_FIELDS = [
    "test_number",
    "test_area",
    "roof_area",
    "angle_degrees",
    "air_temperature_f",
    "roof_temperature_f",
    "wind_speed_direction",
    "shingle_type",
    "wind_lift_evidence",
    "nail_observations",
    "photo_reference",
    "site_clear_of_hazards",
    "site_representative",
    "site_free_of_blemishes",
    "test_board_visible",
    "initial_reading_photo",
    "final_reading_photo",
    "repair_needed",
    "repair_completed",
    "sample_removed",
    "maintenance_notified",
    "post_test_notes",
    "failure_type",
    "operator_notes",
    "deviation_from_standard",
    "deviation_description",
    "effect_on_uncertainty",
    "approved_by",
    "approved_date",
]

RESULT_FIELDS = [
    "test_started_at",
    "test_completed_at",
    "initial_preload_lbs",
    "max_load_lbs",
    "stop_reason",
    "sample_count",
    "software_version",
]

EXPORT_FIELDS = JOB_FIELDS + TEST_FIELDS + RESULT_FIELDS


def utc_now():
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def ensure_data_dir():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)


def connect():
    ensure_data_dir()
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                form_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL,
                form_json TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                initial_preload_lbs REAL,
                peak_load_lbs REAL DEFAULT 0,
                stop_reason TEXT,
                sample_count INTEGER DEFAULT 0,
                software_version TEXT
            );

            CREATE TABLE IF NOT EXISTS force_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL REFERENCES tests(id) ON DELETE CASCADE,
                timestamp TEXT NOT NULL,
                elapsed_s REAL NOT NULL,
                force_lbs REAL NOT NULL,
                raw_lbs REAL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER,
                test_id INTEGER,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                data_json TEXT
            );

            CREATE TABLE IF NOT EXISTS email_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                attachment_path TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def normalize_form(data, fields):
    return {field: str(data.get(field, "")).strip() for field in fields}


def normalize_partial(data, fields):
    return {field: str(data.get(field, "")).strip() for field in fields if field in data}


def create_job(form):
    now = utc_now()
    form_json = json.dumps(normalize_form(form, JOB_FIELDS), sort_keys=True)
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO jobs (created_at, updated_at, status, form_json) VALUES (?, ?, ?, ?)",
            (now, now, "active", form_json),
        )
        return cur.lastrowid


def update_job(job_id, form=None, status=None):
    job = get_job(job_id)
    if not job:
        return False
    payload = job["form"]
    if form is not None:
        payload.update(normalize_partial(form, JOB_FIELDS))
    new_status = status or job["status"]
    with db() as conn:
        conn.execute(
            "UPDATE jobs SET updated_at=?, status=?, form_json=? WHERE id=?",
            (utc_now(), new_status, json.dumps(payload, sort_keys=True), job_id),
        )
    return True


def get_job(job_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    return _job_from_row(row)


def list_jobs():
    with db() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    return [_job_from_row(row) for row in rows]


def search_jobs(query=""):
    jobs = list_jobs()
    term = str(query or "").strip().lower()
    if not term:
        return jobs
    matches = []
    for job in jobs:
        form = job["form"]
        haystack = " ".join(
            str(form.get(field, ""))
            for field in [
                "project_name",
                "project_address",
                "project_city_state_zip",
                "client_name",
                "job_number",
                "building_number",
                "date",
                "suspected_loss_date",
            ]
        ).lower()
        if term in haystack:
            matches.append(job)
    return matches


def _job_from_row(row):
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "form": json.loads(row["form_json"]),
    }


def create_test(job_id, form):
    now = utc_now()
    form_json = json.dumps(normalize_form(form, TEST_FIELDS), sort_keys=True)
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO tests (job_id, created_at, updated_at, status, form_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, now, now, "created", form_json),
        )
        return cur.lastrowid


def update_test(test_id, form=None, **fields):
    test = get_test(test_id)
    if not test:
        return False
    payload = test["form"]
    if form is not None:
        payload.update(normalize_partial(form, TEST_FIELDS))

    allowed = {
        "status",
        "started_at",
        "completed_at",
        "initial_preload_lbs",
        "peak_load_lbs",
        "stop_reason",
        "sample_count",
        "software_version",
    }
    assignments = ["updated_at=?", "form_json=?"]
    values = [utc_now(), json.dumps(payload, sort_keys=True)]
    for key, value in fields.items():
        if key in allowed:
            assignments.append(f"{key}=?")
            values.append(value)
    values.append(test_id)
    with db() as conn:
        conn.execute(f"UPDATE tests SET {', '.join(assignments)} WHERE id=?", values)
    return True


def get_test(test_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM tests WHERE id=?", (test_id,)).fetchone()
    if not row:
        return None
    return _test_from_row(row)


def list_tests(job_id=None):
    query = "SELECT * FROM tests"
    params = ()
    if job_id is not None:
        query += " WHERE job_id=?"
        params = (job_id,)
    query += " ORDER BY id"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_test_from_row(row) for row in rows]


def _test_from_row(row):
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "form": json.loads(row["form_json"]),
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "initial_preload_lbs": row["initial_preload_lbs"],
        "peak_load_lbs": row["peak_load_lbs"] or 0,
        "stop_reason": row["stop_reason"],
        "sample_count": row["sample_count"] or 0,
        "software_version": row["software_version"],
    }


def add_sample(test_id, elapsed_s, force_lbs, raw_lbs=None):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO force_samples (test_id, timestamp, elapsed_s, force_lbs, raw_lbs)
            VALUES (?, ?, ?, ?, ?)
            """,
            (test_id, utc_now(), float(elapsed_s), float(force_lbs), raw_lbs),
        )
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM force_samples WHERE test_id=?", (test_id,)
        ).fetchone()
    return row["n"]


def clear_samples(test_id):
    with db() as conn:
        conn.execute("DELETE FROM force_samples WHERE test_id=?", (test_id,))
    return True


def list_samples(test_id):
    with db() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, elapsed_s, force_lbs, raw_lbs
            FROM force_samples
            WHERE test_id=?
            ORDER BY id
            """,
            (test_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def add_event(message, level="info", job_id=None, test_id=None, data=None):
    with db() as conn:
        conn.execute(
            """
            INSERT INTO events (job_id, test_id, timestamp, level, message, data_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                test_id,
                utc_now(),
                level,
                message,
                json.dumps(data or {}, sort_keys=True),
            ),
        )


def build_export_row(job, test):
    row = {}
    row.update({field: job["form"].get(field, "") for field in JOB_FIELDS})
    row.update({field: test["form"].get(field, "") for field in TEST_FIELDS})
    row.update(
        {
            "test_started_at": test.get("started_at") or "",
            "test_completed_at": test.get("completed_at") or "",
            "initial_preload_lbs": _num(test.get("initial_preload_lbs")),
            "max_load_lbs": _num(test.get("peak_load_lbs")),
            "stop_reason": test.get("stop_reason") or "",
            "sample_count": test.get("sample_count") or 0,
            "software_version": test.get("software_version") or "",
        }
    )
    for field in EXPORT_FIELDS:
        row.setdefault(field, "")
    return row


def _num(value):
    if value is None:
        return ""
    return round(float(value), 3)


def write_csv(path, rows, fieldnames):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def set_setting(key, value):
    now = utc_now()
    with db() as conn:
        conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (str(key), str(value), now),
        )


def get_setting(key, default=""):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (str(key),)).fetchone()
    if not row:
        return default
    return row["value"]


def get_settings(keys):
    if not keys:
        return {}
    with db() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join('?' for _ in keys)})",
            [str(key) for key in keys],
        ).fetchall()
    return {row["key"]: row["value"] for row in rows}


def queue_email(job_id, recipient, subject, body, attachment_path):
    now = utc_now()
    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO email_queue (
                job_id, created_at, updated_at, recipient, subject, body,
                attachment_path, status, attempts
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (job_id, now, now, recipient, subject, body, attachment_path, "queued"),
        )
        return cur.lastrowid


def retire_email_retries(max_attempts):
    with db() as conn:
        conn.execute(
            """
            UPDATE email_queue
            SET status='failed', updated_at=?
            WHERE status='retry' AND attempts >= ?
            """,
            (utc_now(), max(1, int(max_attempts))),
        )


def next_queued_email(max_attempts=None):
    max_attempts = max(1, int(max_attempts or 999999))
    with db() as conn:
        row = conn.execute(
            """
            SELECT * FROM email_queue
            WHERE status='queued' OR (status='retry' AND attempts < ?)
            ORDER BY CASE status WHEN 'queued' THEN 0 ELSE 1 END, created_at
            LIMIT 1
            """,
            (max_attempts,),
        ).fetchone()
    return dict(row) if row else None


def mark_email_sent(queue_id):
    with db() as conn:
        conn.execute(
            "UPDATE email_queue SET status='sent', updated_at=?, last_error=NULL WHERE id=?",
            (utc_now(), queue_id),
        )


def mark_email_failed(queue_id, error, max_attempts=None):
    max_attempts = max(1, int(max_attempts or 999999))
    with db() as conn:
        conn.execute(
            """
            UPDATE email_queue
            SET status=CASE WHEN attempts + 1 >= ? THEN 'failed' ELSE 'retry' END,
                updated_at=?, attempts=attempts+1, last_error=?
            WHERE id=?
            """,
            (max_attempts, utc_now(), str(error)[:500], queue_id),
        )


def list_email_queue(job_id=None):
    query = "SELECT * FROM email_queue"
    params = ()
    if job_id is not None:
        query += " WHERE job_id=?"
        params = (job_id,)
    query += " ORDER BY id DESC"
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]
