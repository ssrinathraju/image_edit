from __future__ import annotations
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

from ulid import ULID

from image_edit_server.configs.settings import Settings
from image_edit_server.core.plans import ALL_PLANS, FREE
from image_edit_server.core.referral_codes import generate_code
from image_edit_server.core.token_hash import hash_token
from image_edit_server.core.user_store import EmailTakenError
from image_edit_server.repos.user_store_codes import (
    _EMAIL_SCHEMA,
    CodesMixin,
)
from image_edit_server.repos.user_store_consent import ConsentMixin
from image_edit_server.repos.user_store_identities import (
    _IDENTITY_SCHEMA,
    IdentitiesMixin,
)
from image_edit_server.repos.user_store_referrals import ReferralsMixin
from image_edit_server.repos.user_store_safety import _SAFETY_SCHEMA, SafetyMixin
from image_edit_server.repos.user_store_security import SecurityMixin
from image_edit_server.repos.user_store_usage import _USAGE_SCHEMA, UsageMixin
from image_edit_server.schemas.user import User

SESSION_TOKEN_BYTES = 32
SCHEMA_VERSION = 7
CODE_ATTEMPTS = 5

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
    "created_via": "TEXT NOT NULL DEFAULT 'password'",
    "referral_redeemed": "INTEGER NOT NULL DEFAULT 0",
    "age_confirmed_at": "TEXT",
    "consent_version": "TEXT",
    "consent_at": "TEXT",
}

_USER_COLUMNS = (
    "u.id, u.email, u.created_at, u.plan, u.bonus_credits, u.referral_code,"
    " u.referral_rewards, u.password_hash <> '', u.age_confirmed_at,"
    " u.consent_version, u.consent_at"
)
_USER_COLUMN_COUNT = 11


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_user(row: tuple) -> User:
    return User(
        id=row[0],
        email=row[1],
        created_at=row[2],
        plan=row[3],
        bonus_credits=row[4],
        referral_code=row[5] or "",
        referral_rewards=row[6],
        has_password=bool(row[7]),
        age_confirmed_at=row[8],
        consent_version=row[9],
        consent_at=row[10],
    )


def auth_db_path(settings: Settings) -> str:
    """The SQLite file for users, sessions and usage; shared with the operator script."""
    return settings.AUTH_DB_PATH or str(Path(settings.STORAGE_ROOT) / "app.db")


class SqliteUserStore(
    CodesMixin,
    IdentitiesMixin,
    ReferralsMixin,
    UsageMixin,
    ConsentMixin,
    SafetyMixin,
    SecurityMixin,
):
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
            previous_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
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
                # Every account is now proven by a registration code or a provider, so
                # older never-verified accounts (development data) are trusted.
                self._conn.execute(
                    "UPDATE users SET email_verified = 1 WHERE email_verified = 0"
                )
                self._drop_user_keyed_code_tables()
                schema = _USAGE_SCHEMA + _IDENTITY_SCHEMA + _EMAIL_SCHEMA + _SAFETY_SCHEMA
                for statement in schema.strip().split(";"):
                    if statement.strip():
                        self._conn.execute(statement)
                if previous_version < 5:
                    # Registrations started before the age check carry no date of
                    # birth, so they must be started again, not confirmed unchecked.
                    self._conn.execute("DELETE FROM pending_registrations")
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

    def _drop_user_keyed_code_tables(self) -> None:
        # Codes live 15 minutes and send times an hour, so the version-3 rows are
        # not worth converting; at worst a reset code in flight is requested again.
        columns = {row[1] for row in self._conn.execute("PRAGMA table_info(email_codes)")}
        if "user_id" in columns:
            self._conn.execute("DROP TABLE email_codes")
            self._conn.execute("DROP TABLE IF EXISTS email_sends")

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
        try:
            with self._lock, self._conn:
                user_id = self._insert_password_user(
                    email, password_hash, self._clock(), 0, None
                )
                return self._load_user(user_id)
        except sqlite3.IntegrityError as error:
            # Only a duplicate email is the caller's fault; any other violation
            # (say a referral-code collision) is a bug and must not read as one.
            if "users.email" not in str(error):
                raise
            raise EmailTakenError(email) from error

    def _insert_password_user(
        self,
        email: str,
        password_hash: str,
        now: datetime,
        bonus_credits: int,
        referrer_id: Optional[str],
        age_confirmed_at: Optional[str] = None,
    ) -> str:
        user_id = str(ULID())
        # email_verified stays written as 1 so a rollback to the version-3 server
        # does not treat these accounts as unverified.
        self._conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
            " referral_code, referred_by, email_verified, age_confirmed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
            (
                user_id,
                email,
                password_hash,
                now.isoformat(),
                bonus_credits,
                self._unused_code(),
                referrer_id,
                age_confirmed_at,
            ),
        )
        return user_id

    def get_by_email(self, email: str) -> Optional[User]:
        return self._fetch_user(f"SELECT {_USER_COLUMNS} FROM users u WHERE u.email = ?", email)

    def get_by_id(self, user_id: str) -> Optional[User]:
        return self._fetch_user(f"SELECT {_USER_COLUMNS} FROM users u WHERE u.id = ?", user_id)

    def get_password_hash(self, user_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return row[0] if row else None

    def delete_user(self, user_id: str) -> None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT email FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if row:
                self._conn.execute("DELETE FROM email_codes WHERE email = ?", (row[0],))
                self._conn.execute("DELETE FROM email_sends WHERE email = ?", (row[0],))
                self._discard_pending_email_change(user_id)
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
                (hash_token(token), user_id, now.isoformat(), (now + ttl).isoformat()),
            )
        return token

    def get_user_by_session(self, token: str) -> Optional[User]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS}, s.expires_at"
                " FROM sessions s JOIN users u ON u.id = s.user_id"
                " WHERE s.token_hash = ?",
                (hash_token(token),),
            ).fetchone()
        if row is None:
            return None
        if datetime.fromisoformat(row[_USER_COLUMN_COUNT]) <= self._clock():
            return None
        return _to_user(row[:_USER_COLUMN_COUNT])

    def delete_session(self, token: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),)
            )

    def _load_user(self, user_id: str) -> User:
        row = self._conn.execute(
            f"SELECT {_USER_COLUMNS} FROM users u WHERE u.id = ?", (user_id,)
        ).fetchone()
        return _to_user(row)

    def _fetch_user(self, query: str, param: str) -> Optional[User]:
        with self._lock:
            row = self._conn.execute(query, (param,)).fetchone()
        return _to_user(row) if row else None
