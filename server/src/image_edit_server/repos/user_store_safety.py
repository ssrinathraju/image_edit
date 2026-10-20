from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from image_edit_server.core.user_store import TooManyReports, UserNotFound
from image_edit_server.schemas.report import Report

REPORT_DAILY_WINDOW = timedelta(hours=24)

_SAFETY_SCHEMA = """
CREATE TABLE IF NOT EXISTS safety_strikes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strikes_user_time ON safety_strikes(user_id, created_at);
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    category TEXT NOT NULL,
    note TEXT NOT NULL,
    image_source TEXT NOT NULL CHECK (image_source IN ('server', 'device', 'none')),
    image_name TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    outcome TEXT
);
CREATE INDEX IF NOT EXISTS idx_reports_reporter_time ON reports(reporter_id, created_at)
"""

_REPORT_COLUMNS = (
    "id, reporter_id, job_id, category, note, image_source, image_name,"
    " created_at, resolved_at, outcome"
)


def _stamp(moment: datetime) -> str:
    """One UTC text format everywhere, so string comparison orders by time."""
    return moment.astimezone(timezone.utc).isoformat()


def _to_report(row: tuple) -> Report:
    return Report(
        id=row[0],
        reporter_id=row[1],
        job_id=row[2],
        category=row[3],
        note=row[4],
        image_source=row[5],
        image_name=row[6],
        created_at=datetime.fromisoformat(row[7]),
        resolved_at=datetime.fromisoformat(row[8]) if row[8] else None,
        outcome=row[9],
    )


class SafetyMixin:
    def record_strike(self, user_id: str, now: datetime, window: timedelta) -> None:
        try:
            with self._lock, self._conn:
                self._conn.execute(
                    "DELETE FROM safety_strikes WHERE created_at <= ?",
                    (_stamp(now - window),),
                )
                self._conn.execute(
                    "INSERT INTO safety_strikes (user_id, created_at) VALUES (?, ?)",
                    (user_id, _stamp(now)),
                )
        except sqlite3.IntegrityError as error:
            raise UserNotFound(user_id) from error

    def suspended_until(
        self, user_id: str, now: datetime, window: timedelta, threshold: int
    ) -> Optional[datetime]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT created_at FROM safety_strikes"
                " WHERE user_id = ? AND created_at > ?"
                " ORDER BY created_at DESC LIMIT ?",
                (user_id, _stamp(now - window), threshold),
            ).fetchall()
        if len(rows) < threshold:
            return None
        return datetime.fromisoformat(rows[-1][0]) + window

    def add_report(
        self,
        report_id: str,
        reporter_id: str,
        job_id: str,
        category: str,
        note: str,
        image_source: str,
        image_name: Optional[str],
        now: datetime,
        daily_limit: int,
    ) -> None:
        """Insert a report unless the reporter is at the daily cap; the check and the write are one transaction."""
        try:
            with self._lock, self._conn:
                recent = self._conn.execute(
                    "SELECT COUNT(*) FROM reports WHERE reporter_id = ? AND created_at > ?",
                    (reporter_id, _stamp(now - REPORT_DAILY_WINDOW)),
                ).fetchone()[0]
                if recent >= daily_limit:
                    raise TooManyReports(reporter_id)
                self._conn.execute(
                    f"INSERT INTO reports ({_REPORT_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                    (report_id, reporter_id, job_id, category, note, image_source,
                     image_name, _stamp(now)),
                )
        except sqlite3.IntegrityError as error:
            if "FOREIGN KEY" not in str(error):
                raise
            raise UserNotFound(reporter_id) from error

    def get_report(self, report_id: str) -> Optional[Report]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_REPORT_COLUMNS} FROM reports WHERE id = ?", (report_id,)
            ).fetchone()
        return _to_report(row) if row else None

    def list_open_reports(self) -> list[Report]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_REPORT_COLUMNS} FROM reports WHERE resolved_at IS NULL"
                " ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [_to_report(row) for row in rows]

    def resolve_report(self, report_id: str, outcome: str, now: datetime) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE reports SET resolved_at = ?, outcome = ?"
                " WHERE id = ? AND resolved_at IS NULL",
                (_stamp(now), outcome, report_id),
            )
        return cursor.rowcount == 1

    def expired_reports(self, now: datetime, max_age: timedelta) -> list[Report]:
        with self._lock:
            rows = self._conn.execute(
                f"SELECT {_REPORT_COLUMNS} FROM reports WHERE created_at <= ?",
                (_stamp(now - max_age),),
            ).fetchall()
        return [_to_report(row) for row in rows]

    def delete_report(self, report_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))

    def report_image_names(self, reporter_id: Optional[str] = None) -> list[str]:
        """Image file names of one reporter's reports, or of every report when no reporter is given."""
        query = "SELECT image_name FROM reports WHERE image_name IS NOT NULL"
        params: tuple = ()
        if reporter_id is not None:
            query += " AND reporter_id = ?"
            params = (reporter_id,)
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [row[0] for row in rows]
