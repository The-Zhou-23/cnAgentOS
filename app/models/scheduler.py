import json
from datetime import datetime
from app.models.db import get_connection


class SchedulerRepository:

    DEFAULT_JOB = {
        "name": "定时瞭望采集",
        "cron_expr": "0 */1 * * *",
        "task_type": "watch_collect",
        "config_json": json.dumps({"keyword": "人工智能", "source_id": None, "item_count": 10, "max_pages": 1}, ensure_ascii=False),
    }

    @staticmethod
    def init_schema():
        with get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_jobs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cron_expr TEXT NOT NULL DEFAULT '0 */1 * * *',
                    task_type TEXT NOT NULL DEFAULT 'watch_collect',
                    is_enabled INTEGER NOT NULL DEFAULT 0,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    last_run_at TEXT,
                    created_at TEXT NOT NULL DEFAULT(datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduler_logs(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT(datetime('now'))
                )
                """
            )
            existing = conn.execute("SELECT COUNT(*) FROM scheduler_jobs").fetchone()[0]
            if existing == 0:
                d = SchedulerRepository.DEFAULT_JOB
                conn.execute(
                    "INSERT INTO scheduler_jobs(name, cron_expr, task_type, is_enabled, config_json) VALUES(?,?,?,?,?)",
                    (d["name"], d["cron_expr"], d["task_type"], 0, d["config_json"]),
                )

    @staticmethod
    def list_jobs():
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM scheduler_jobs ORDER BY id").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_job(job_id):
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM scheduler_jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def create_job(data):
        with get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO scheduler_jobs(name, cron_expr, task_type, is_enabled, config_json) VALUES(?,?,?,?,?)",
                (data["name"], data["cron_expr"], data.get("task_type", "watch_collect"), data.get("is_enabled", 0), data.get("config_json", "{}")),
            )
            return cur.lastrowid

    @staticmethod
    def update_job(job_id, data):
        with get_connection() as conn:
            fields = []
            values = []
            for key in ("name", "cron_expr", "task_type", "config_json"):
                if key in data:
                    fields.append(f"{key}=?")
                    values.append(data[key])
            if not fields:
                return
            fields.append("updated_at=datetime('now')")
            values.append(job_id)
            conn.execute(f"UPDATE scheduler_jobs SET {', '.join(fields)} WHERE id=?", values)

    @staticmethod
    def delete_job(job_id):
        with get_connection() as conn:
            conn.execute("DELETE FROM scheduler_logs WHERE job_id=?", (job_id,))
            conn.execute("DELETE FROM scheduler_jobs WHERE id=?", (job_id,))

    @staticmethod
    def toggle_job(job_id, enabled):
        with get_connection() as conn:
            conn.execute(
                "UPDATE scheduler_jobs SET is_enabled=?, updated_at=datetime('now') WHERE id=?",
                (1 if enabled else 0, job_id),
            )

    @staticmethod
    def update_last_run(job_id):
        with get_connection() as conn:
            conn.execute("UPDATE scheduler_jobs SET last_run_at=datetime('now') WHERE id=?", (job_id,))

    @staticmethod
    def add_log(job_id, status, message=""):
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO scheduler_logs(job_id, status, message) VALUES(?,?,?)",
                (job_id, status, message),
            )

    @staticmethod
    def get_logs(job_id=None, limit=20):
        with get_connection() as conn:
            if job_id:
                rows = conn.execute(
                    "SELECT * FROM scheduler_logs WHERE job_id=? ORDER BY id DESC LIMIT ?",
                    (job_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM scheduler_logs ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def parse_cron(cron_expr):
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return None
        return {"minute": parts[0], "hour": parts[1], "day": parts[2], "month": parts[3], "week": parts[4]}

    @staticmethod
    def cron_matches(cron_expr, dt=None):
        if dt is None:
            dt = datetime.now()
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            return False

        def _match(field, value):
            if field == "*":
                return True
            for item in field.split(","):
                item = item.strip()
                if "/" in item:
                    base, step = item.split("/")
                    base = 0 if base == "*" else int(base)
                    step = int(step)
                    if value >= base and (value - base) % step == 0:
                        return True
                elif "-" in item:
                    lo, hi = item.split("-")
                    if int(lo) <= value <= int(hi):
                        return True
                else:
                    try:
                        if int(item) == value:
                            return True
                    except ValueError:
                        pass
            return False

        return (
            _match(parts[0], dt.minute)
            and _match(parts[1], dt.hour)
            and _match(parts[2], dt.day)
            and _match(parts[3], dt.month)
            and _match(parts[4], dt.weekday())
        )
