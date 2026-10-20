from __future__ import annotations

from datetime import datetime


class ConsentMixin:
    def confirm_age(self, user_id: str, now: datetime) -> None:
        self._update_user_columns(
            user_id, "age_confirmed_at = ?", (now.isoformat(),)
        )

    def set_consent(self, user_id: str, version: str, now: datetime) -> None:
        self._update_user_columns(
            user_id, "consent_version = ?, consent_at = ?", (version, now.isoformat())
        )

    def clear_consent(self, user_id: str) -> None:
        self._update_user_columns(user_id, "consent_version = NULL, consent_at = NULL", ())

    def _update_user_columns(self, user_id: str, assignments: str, values: tuple) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE users SET {assignments} WHERE id = ?", (*values, user_id)
            )
