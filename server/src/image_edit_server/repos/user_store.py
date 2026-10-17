from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ulid import ULID

from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    IssueResult,
    hash_code,
)
from image_edit_server.core.plans import ALL_PLANS, FREE
from image_edit_server.core.referral_codes import generate_code, normalize_code
from image_edit_server.core.user_store import (
    EmailTakenError,
    InvalidReferralCode,
    QuotaExceeded,
    UserNotFound,
)
from image_edit_server.schemas.user import UsageSnapshot, User

SESSION_TOKEN_BYTES = 32
SCHEMA_VERSION = 3
CODE_ATTEMPTS = 5
SOURCE_DAILY = "daily"
SOURCE_BONUS = "bonus"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

# Columns added after the first release. SQLite cannot ALTER in a UNIQUE
# constraint, so referral_code's uniqueness is a separate index below.
_ADDED_USER_COLUMNS = {
    "plan": f"TEXT NOT NULL DEFAULT '{FREE}'",
    "bonus_credits": "INTEGER NOT NULL DEFAULT 0",
    "referral_code": "TEXT",
    "referred_by": "TEXT",
    "referral_rewards": "INTEGER NOT NULL DEFAULT 0",
    "email_verified": "INTEGER NOT NULL DEFAULT 0",
    "referral_bonus_pending": "INTEGER NOT NULL DEFAULT 0",
}

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
CREATE TABLE IF NOT EXISTS email_codes (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, purpose)
);
CREATE TABLE IF NOT EXISTS email_sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_email_sends_user ON email_sends(user_id, sent_at);
"""

_USER_COLUMNS = (
    "id, email, created_at, plan, bonus_credits, referral_code, referral_rewards,"
    " email_verified"
)
_USER_COLUMN_COUNT = 8
SEND_WINDOW = timedelta(hours=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _to_user(row: tuple) -> User:
    return User(
        id=row[0],
        email=row[1],
        created_at=row[2],
        plan=row[3],
        bonus_credits=row[4],
        referral_code=row[5] or "",
        referral_rewards=row[6],
        email_verified=bool(row[7]),
    )


def auth_db_path(settings: Settings) -> str:
    """The SQLite file for users, sessions and usage; shared with the operator script."""
    return settings.AUTH_DB_PATH or str(Path(settings.STORAGE_ROOT) / "app.db")


def _utc_day(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).date().isoformat()


class SqliteUserStore:
    def __init__(
        self, path: str = ":memory:", clock: Callable[[], datetime] = _utc_now
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── schema ───────────────────────────────────────────────────────────

    def _migrate(self) -> None:
        """Bring an existing database up to date; safe to run repeatedly.

        Column presence, not the version number, decides what runs, so a
        half-migrated file heals too.
        """
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                existing = {
                    row[1] for row in self._conn.execute("PRAGMA table_info(users)")
                }
                for column, definition in _ADDED_USER_COLUMNS.items():
                    if column not in existing:
                        self._conn.execute(
                            f"ALTER TABLE users ADD COLUMN {column} {definition}"
                        )
                if "email_verified" not in existing:
                    # Accounts that exist before verification shipped are trusted.
                    self._conn.execute("UPDATE users SET email_verified = 1")
                for statement in _USAGE_SCHEMA.strip().split(";"):
                    if statement.strip():
                        self._conn.execute(statement)
                usage_columns = {
                    row[1]
                    for row in self._conn.execute("PRAGMA table_info(generation_usage)")
                }
                if "settled" not in usage_columns:
                    self._conn.execute(
                        "ALTER TABLE generation_usage"
                        " ADD COLUMN settled INTEGER NOT NULL DEFAULT 0"
                    )
                    # Nothing can be in flight while the database is upgraded, so
                    # every row that exists is history. Left at 0 they would all be
                    # refunded by the startup recovery, handing back paid-for work.
                    self._conn.execute("UPDATE generation_usage SET settled = 1")
                self._backfill_referral_codes()
                self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def _backfill_referral_codes(self) -> None:
        missing = self._conn.execute(
            "SELECT id FROM users WHERE referral_code IS NULL"
        ).fetchall()
        for (user_id,) in missing:
            self._conn.execute(
                "UPDATE users SET referral_code = ? WHERE id = ?",
                (self._unused_code(), user_id),
            )

    def _unused_code(self) -> str:
        for _ in range(CODE_ATTEMPTS):
            code = generate_code()
            taken = self._conn.execute(
                "SELECT 1 FROM users WHERE referral_code = ?", (code,)
            ).fetchone()
            if taken is None:
                return code
        raise RuntimeError("could not generate an unused referral code")

    # ── users ────────────────────────────────────────────────────────────

    def create_user(self, email: str, password_hash: str) -> User:
        return self.register_user(email, password_hash, None)

    def register_user(
        self,
        email: str,
        password_hash: str,
        referral_code: Optional[str],
    ) -> User:
        code_to_redeem = normalize_code(referral_code) if referral_code else ""
        user_id = str(ULID())
        created_at = self._clock().isoformat()
        try:
            with self._lock, self._conn:
                referrer = self._find_referrer(code_to_redeem)
                new_code = self._unused_code()
                self._conn.execute(
                    "INSERT INTO users (id, email, password_hash, created_at,"
                    " bonus_credits, referral_code, referred_by, referral_bonus_pending)"
                    " VALUES (?, ?, ?, ?, 0, ?, ?, ?)",
                    (
                        user_id,
                        email,
                        password_hash,
                        created_at,
                        new_code,
                        referrer,
                        1 if referrer else 0,
                    ),
                )
        except sqlite3.IntegrityError as error:
            # Only a duplicate email is the caller's fault; any other violation
            # (say a referral-code collision) is a bug and must not read as one.
            if "users.email" not in str(error):
                raise
            raise EmailTakenError(email) from error
        return User(
            id=user_id,
            email=email,
            created_at=created_at,
            referral_code=new_code,
        )

    def _find_referrer(self, code: str) -> Optional[str]:
        if not code:
            return None
        row = self._conn.execute(
            "SELECT id FROM users WHERE referral_code = ?", (code,)
        ).fetchone()
        if row is None:
            raise InvalidReferralCode(code)
        return row[0]

    def mark_email_verified(self, user_id: str, bonus: int, max_rewards: int) -> bool:
        with self._lock, self._conn:
            return self._verify_and_reward(user_id, bonus, max_rewards)

    def _verify_and_reward(self, user_id: str, bonus: int, max_rewards: int) -> bool:
        row = self._conn.execute(
            "SELECT email_verified, referral_bonus_pending, referred_by"
            " FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None or row[0]:
            return False
        _, pending, referrer_id = row
        self._conn.execute(
            "UPDATE users SET email_verified = 1, referral_bonus_pending = 0,"
            " bonus_credits = bonus_credits + ? WHERE id = ?",
            (bonus if pending else 0, user_id),
        )
        if referrer_id:
            self._reward_referrer(referrer_id, bonus, max_rewards)
        return True

    def _reward_referrer(self, referrer_id: str, bonus: int, max_rewards: int) -> None:
        self._conn.execute(
            "UPDATE users SET bonus_credits = bonus_credits + ?,"
            " referral_rewards = referral_rewards + 1"
            " WHERE id = ? AND referral_rewards < ?",
            (bonus, referrer_id, max_rewards),
        )

    def get_by_email(self, email: str) -> Optional[User]:
        return self._fetch_user(f"SELECT {_USER_COLUMNS} FROM users WHERE email = ?", email)

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._fetch_user(f"SELECT {_USER_COLUMNS} FROM users WHERE id = ?", user_id)

    def get_password_hash(self, user_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row[0] if row else None

    def delete_user(self, user_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE users SET referred_by = NULL WHERE referred_by = ?", (user_id,)
            )
            self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def set_plan(self, email: str, plan: str) -> bool:
        """Operator tooling: returns False when the email has no account."""
        if plan not in ALL_PLANS:
            raise ValueError(f"unknown plan {plan!r}; expected one of {list(ALL_PLANS)}")
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE users SET plan = ? WHERE email = ?", (plan, email)
            )
        return cursor.rowcount == 1

    # ── email codes ──────────────────────────────────────────────────────

    def issue_code(
        self,
        user_id: str,
        purpose: CodePurpose,
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        with self._lock, self._conn:
            recent = self._recent_sends(user_id, now)
            wait = self._seconds_until_allowed(recent, now, limits)
            if wait > 0:
                return IssueResult(issued=False, retry_after_seconds=wait)
            self._conn.execute(
                "INSERT OR REPLACE INTO email_codes"
                " (user_id, purpose, code_hash, expires_at, attempts, created_at)"
                " VALUES (?, ?, ?, ?, 0, ?)",
                (
                    user_id,
                    purpose.value,
                    code_hash,
                    (now + limits.ttl).isoformat(),
                    now.isoformat(),
                ),
            )
            self._conn.execute(
                "INSERT INTO email_sends (user_id, purpose, sent_at) VALUES (?, ?, ?)",
                (user_id, purpose.value, now.isoformat()),
            )
        return IssueResult(issued=True)

    def _recent_sends(self, user_id: str, now: datetime) -> list[datetime]:
        """Send times within the last hour, pruning older rows for this user."""
        rows = self._conn.execute(
            "SELECT id, sent_at FROM email_sends WHERE user_id = ?", (user_id,)
        ).fetchall()
        cutoff = now - SEND_WINDOW
        stale = [row[0] for row in rows if datetime.fromisoformat(row[1]) <= cutoff]
        for send_id in stale:
            self._conn.execute("DELETE FROM email_sends WHERE id = ?", (send_id,))
        sent = (datetime.fromisoformat(row[1]) for row in rows if row[0] not in stale)
        return sorted(sent)

    @staticmethod
    def _seconds_until_allowed(
        recent: list[datetime], now: datetime, limits: CodeLimits
    ) -> int:
        waits = []
        if recent and now - recent[-1] < limits.resend_interval:
            waits.append(recent[-1] + limits.resend_interval - now)
        if len(recent) >= limits.max_per_hour:
            oldest_counting = recent[len(recent) - limits.max_per_hour]
            waits.append(oldest_counting + SEND_WINDOW - now)
        return math.ceil(max(waits).total_seconds()) if waits else 0

    def consume_code(
        self,
        user_id: str,
        purpose: CodePurpose,
        code: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        with self._lock, self._conn:
            return self._consume(user_id, purpose, code, now, max_attempts)

    def _consume(
        self,
        user_id: str,
        purpose: CodePurpose,
        code: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        row = self._conn.execute(
            "SELECT code_hash, expires_at, attempts FROM email_codes"
            " WHERE user_id = ? AND purpose = ?",
            (user_id, purpose.value),
        ).fetchone()
        if row is None or row[2] >= max_attempts:
            return ConsumeResult.EXPIRED
        if datetime.fromisoformat(row[1]) < now:
            return ConsumeResult.EXPIRED
        if not hmac.compare_digest(row[0], hash_code(user_id, purpose, code)):
            self._conn.execute(
                "UPDATE email_codes SET attempts = attempts + 1"
                " WHERE user_id = ? AND purpose = ?",
                (user_id, purpose.value),
            )
            return ConsumeResult.WRONG
        self._conn.execute(
            "DELETE FROM email_codes WHERE user_id = ? AND purpose = ?",
            (user_id, purpose.value),
        )
        return ConsumeResult.OK

    def reset_password(
        self,
        user_id: str,
        code: str,
        new_hash: str,
        now: datetime,
        max_attempts: int,
        bonus: int,
        max_rewards: int,
    ) -> ConsumeResult:
        with self._lock, self._conn:
            result = self._consume(
                user_id, CodePurpose.PASSWORD_RESET, code, now, max_attempts
            )
            if result is not ConsumeResult.OK:
                return result
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id)
            )
            self._conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            self._verify_and_reward(user_id, bonus, max_rewards)
        return result

    # ── sessions ─────────────────────────────────────────────────────────

    def create_session(self, user_id: str, ttl: timedelta) -> str:
        token = secrets.token_urlsafe(SESSION_TOKEN_BYTES)
        now = self._clock()
        with self._lock, self._conn:
            # Housekeeping: expired rows are never read again, so drop them here.
            self._conn.execute(
                "DELETE FROM sessions WHERE expires_at <= ?", (now.isoformat(),)
            )
            self._conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at)"
                " VALUES (?, ?, ?, ?)",
                (_hash_token(token), user_id, now.isoformat(), (now + ttl).isoformat()),
            )
        return token

    def get_user_by_session(self, token: str) -> Optional[User]:
        columns = ", ".join(f"u.{c.strip()}" for c in _USER_COLUMNS.split(","))
        with self._lock:
            row = self._conn.execute(
                f"SELECT {columns}, s.expires_at"
                " FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token_hash = ?",
                (_hash_token(token),),
            ).fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row[_USER_COLUMN_COUNT]) <= self._clock():
            return None
        return _to_user(row[:_USER_COLUMN_COUNT])

    def delete_session(self, token: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),)
            )

    # ── usage ────────────────────────────────────────────────────────────

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

    def _fetch_user(self, query: str, param: str) -> Optional[User]:
        with self._lock:
            row = self._conn.execute(query, (param,)).fetchone()
        return _to_user(row) if row else None
