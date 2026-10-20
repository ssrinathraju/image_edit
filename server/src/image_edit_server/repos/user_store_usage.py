from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from ulid import ULID

from image_edit_server.core.user_store import QuotaExceeded, UserNotFound
from image_edit_server.schemas.user import UsageSnapshot

SOURCE_DAILY = "daily"
SOURCE_BONUS = "bonus"


_USAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_usage (
    reservation_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day TEXT NOT NULL,
    source TEXT NOT NULL,
    refunded INTEGER NOT NULL DEFAULT 0,
    settled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_user_day ON generation_usage(user_id, day);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_referral_code ON users(referral_code);
"""


def _utc_day(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).date().isoformat()


class UsageMixin:
    def reserve_generation(self, user_id: str, daily_limit: int, now: datetime) -> str:
        reservation_id = str(ULID())
        day = _utc_day(now)
        try:
            with self._lock, self._conn:
                if self._used_today(user_id, day) < daily_limit:
                    source = SOURCE_DAILY
                else:
                    spent = self._conn.execute(
                        "UPDATE users SET bonus_credits = bonus_credits - 1"
                        " WHERE id = ? AND bonus_credits > 0",
                        (user_id,),
                    )
                    if spent.rowcount == 0:
                        raise QuotaExceeded(user_id)
                    source = SOURCE_BONUS
                self._conn.execute(
                    "INSERT INTO generation_usage"
                    " (reservation_id, user_id, day, source, created_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (reservation_id, user_id, day, source, now.isoformat()),
                )
        except sqlite3.IntegrityError as error:
            raise UserNotFound(user_id) from error
        return reservation_id

    def refund_generation(self, reservation_id: str) -> None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT user_id, source FROM generation_usage"
                " WHERE reservation_id = ? AND refunded = 0",
                (reservation_id,),
            ).fetchone()
            if row is None:
                return
            self._conn.execute(
                "UPDATE generation_usage SET refunded = 1 WHERE reservation_id = ?",
                (reservation_id,),
            )
            if row[1] == SOURCE_BONUS:
                self._conn.execute(
                    "UPDATE users SET bonus_credits = bonus_credits + 1 WHERE id = ?",
                    (row[0],),
                )

    def settle_generation(self, reservation_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE generation_usage SET settled = 1 WHERE reservation_id = ?",
                (reservation_id,),
            )

    def refund_unsettled_generations(self) -> int:
        with self._lock:
            pending = [
                row[0]
                for row in self._conn.execute(
                    "SELECT reservation_id FROM generation_usage"
                    " WHERE settled = 0 AND refunded = 0"
                )
            ]
        for reservation_id in pending:
            self.refund_generation(reservation_id)
        return len(pending)

    def usage_snapshot(
        self, user_id: str, daily_limit: int, now: datetime
    ) -> UsageSnapshot:
        with self._lock:
            used = self._used_today(user_id, _utc_day(now))
            row = self._conn.execute(
                "SELECT bonus_credits FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        bonus = row[0] if row else 0
        midnight = now.astimezone(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return UsageSnapshot(
            daily_limit=daily_limit,
            used_today=used,
            bonus_credits=bonus,
            remaining=max(0, daily_limit - used) + bonus,
            resets_at=midnight + timedelta(days=1),
        )

    def _used_today(self, user_id: str, day: str) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM generation_usage"
            " WHERE user_id = ? AND day = ? AND source = ? AND refunded = 0",
            (user_id, day, SOURCE_DAILY),
        ).fetchone()[0]
