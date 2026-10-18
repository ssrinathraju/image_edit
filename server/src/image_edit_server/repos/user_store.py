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
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.plans import ALL_PLANS, FREE
from image_edit_server.core.referral_codes import generate_code, normalize_code
from image_edit_server.core.user_store import (
    EmailTakenError,
    InvalidReferralCode,
    PendingRegistration,
    ProviderAlreadyLinked,
    ProviderEmailMissing,
    ProviderEmailUnverified,
    QuotaExceeded,
    ReferralNotAllowed,
    RegistrationChanged,
    UserNotFound,
)
from image_edit_server.schemas.user import UsageSnapshot, User

SESSION_TOKEN_BYTES = 32
SCHEMA_VERSION = 4
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
    "created_via": "TEXT NOT NULL DEFAULT 'password'",
    "referral_redeemed": "INTEGER NOT NULL DEFAULT 0",
}

# An account made through a provider stores this instead of a password hash;
# verify_password rejects it, so password login fails like a wrong password.
NO_PASSWORD_HASH = ""
PASSWORD_ORIGIN = "password"
APPLE_PROVIDER = "apple"

_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS identities (
    provider TEXT NOT NULL,
    subject TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email TEXT,
    apple_refresh_token TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (provider, subject),
    UNIQUE (user_id, provider)
);
"""

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

# Codes are keyed by email address because a registration code exists before its
# account does; deleting an account therefore removes its rows explicitly.
_EMAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS email_codes (
    email TEXT NOT NULL,
    purpose TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (email, purpose)
);
CREATE TABLE IF NOT EXISTS email_sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    purpose TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_email_sends_email ON email_sends(email, sent_at);
CREATE TABLE IF NOT EXISTS pending_registrations (
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    referral_code TEXT,
    created_at TEXT NOT NULL
);
"""

_USER_COLUMNS = (
    "u.id, u.email, u.created_at, u.plan, u.bonus_credits, u.referral_code,"
    " u.referral_rewards, u.password_hash <> ''"
)
_USER_COLUMN_COUNT = 8
SEND_WINDOW = timedelta(hours=1)
PENDING_REGISTRATION_MAX_AGE = timedelta(hours=24)


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
        has_password=bool(row[7]),
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
                # Every account is now proven by a registration code or a provider, so
                # older never-verified accounts (development data) are trusted.
                self._conn.execute(
                    "UPDATE users SET email_verified = 1 WHERE email_verified = 0"
                )
                self._drop_user_keyed_code_tables()
                schema = _USAGE_SCHEMA + _IDENTITY_SCHEMA + _EMAIL_SCHEMA
                for statement in schema.strip().split(";"):
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
    ) -> str:
        user_id = str(ULID())
        # email_verified stays written as 1 so a rollback to the version-3 server
        # does not treat these accounts as unverified.
        self._conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
            " referral_code, referred_by, email_verified)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (
                user_id,
                email,
                password_hash,
                now.isoformat(),
                bonus_credits,
                self._unused_code(),
                referrer_id,
            ),
        )
        return user_id

    def _find_referrer(self, code: str) -> Optional[str]:
        if not code:
            return None
        row = self._conn.execute(
            "SELECT id FROM users WHERE referral_code = ?", (code,)
        ).fetchone()
        if row is None:
            raise InvalidReferralCode(code)
        return row[0]

    def _reward_referrer(self, referrer_id: str, bonus: int, max_rewards: int) -> None:
        self._conn.execute(
            "UPDATE users SET bonus_credits = bonus_credits + ?,"
            " referral_rewards = referral_rewards + 1"
            " WHERE id = ? AND referral_rewards < ?",
            (bonus, referrer_id, max_rewards),
        )

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
        email: str,
        purpose: CodePurpose,
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        with self._lock, self._conn:
            self._prune_email_rows(now)
            wait = self._seconds_until_allowed(self._recent_sends(email, now), now, limits)
            if wait > 0:
                return IssueResult(issued=False, retry_after_seconds=wait)
            self._store_code(email, purpose, code_hash, now, limits)
        return IssueResult(issued=True)

    def _store_code(
        self,
        email: str,
        purpose: CodePurpose,
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO email_codes"
            " (email, purpose, code_hash, expires_at, attempts, created_at)"
            " VALUES (?, ?, ?, ?, 0, ?)",
            (email, purpose.value, code_hash, (now + limits.ttl).isoformat(), now.isoformat()),
        )
        self._conn.execute(
            "INSERT INTO email_sends (email, purpose, sent_at) VALUES (?, ?, ?)",
            (email, purpose.value, now.isoformat()),
        )

    def _recent_sends(self, email: str, now: datetime) -> list[datetime]:
        """Send times within the last hour, pruning older rows for this address."""
        rows = self._conn.execute(
            "SELECT id, sent_at FROM email_sends WHERE email = ?", (email,)
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
        email: str,
        purpose: CodePurpose,
        code: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        with self._lock, self._conn:
            return self._consume(email, purpose, code, now, max_attempts)

    def _consume(
        self,
        email: str,
        purpose: CodePurpose,
        code: str,
        now: datetime,
        max_attempts: int,
        keep_on_ok: bool = False,
    ) -> ConsumeResult:
        row = self._conn.execute(
            "SELECT code_hash, expires_at, attempts FROM email_codes"
            " WHERE email = ? AND purpose = ?",
            (email, purpose.value),
        ).fetchone()
        if row is None or row[2] >= max_attempts:
            return ConsumeResult.EXPIRED
        if datetime.fromisoformat(row[1]) < now:
            return ConsumeResult.EXPIRED
        if not hmac.compare_digest(row[0], hash_code(email, purpose, code)):
            self._conn.execute(
                "UPDATE email_codes SET attempts = attempts + 1"
                " WHERE email = ? AND purpose = ?",
                (email, purpose.value),
            )
            return ConsumeResult.WRONG
        if not keep_on_ok:
            self._conn.execute(
                "DELETE FROM email_codes WHERE email = ? AND purpose = ?",
                (email, purpose.value),
            )
        return ConsumeResult.OK

    def reset_password(
        self,
        email: str,
        code: str,
        new_hash: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        with self._lock, self._conn:
            result = self._consume(email, CodePurpose.PASSWORD_RESET, code, now, max_attempts)
            if result is not ConsumeResult.OK:
                return result
            row = self._conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row is None:
                return ConsumeResult.EXPIRED
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, row[0])
            )
            self._conn.execute("DELETE FROM sessions WHERE user_id = ?", (row[0],))
        return result

    # ── registration ─────────────────────────────────────────────────────

    def start_registration(
        self,
        email: str,
        password_hash: str,
        referral_code: Optional[str],
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        wanted = normalize_code(referral_code) if referral_code else ""
        with self._lock, self._conn:
            self._find_referrer(wanted)
            if self._email_has_account(email):
                raise EmailTakenError(email)
            self._prune_email_rows(now)
            wait = self._seconds_until_allowed(self._recent_sends(email, now), now, limits)
            if wait > 0:
                return IssueResult(issued=False, retry_after_seconds=wait)
            self._conn.execute(
                "INSERT OR REPLACE INTO pending_registrations"
                " (email, password_hash, referral_code, created_at) VALUES (?, ?, ?, ?)",
                (email, password_hash, wanted or None, now.isoformat()),
            )
            self._store_code(email, CodePurpose.REGISTRATION, code_hash, now, limits)
        return IssueResult(issued=True)

    def check_registration_code(
        self, email: str, code: str, now: datetime, max_attempts: int
    ) -> tuple[ConsumeResult, Optional[PendingRegistration]]:
        with self._lock, self._conn:
            result = self._consume(
                email, CodePurpose.REGISTRATION, code, now, max_attempts, keep_on_ok=True
            )
            if result is not ConsumeResult.OK:
                return result, None
            pending = self._read_pending(email)
            if pending is not None:
                return ConsumeResult.OK, pending
            if self._email_has_account(email):
                self._discard_pending(email)
                raise EmailTakenError(email)
            return ConsumeResult.EXPIRED, None

    def complete_registration(
        self,
        email: str,
        checked: PendingRegistration,
        password_matches: bool,
        now: datetime,
        bonus: int,
        max_rewards: int,
    ) -> User:
        with self._lock, self._conn:
            taken = self._email_has_account(email)
            current = self._read_pending(email)
            outcome = self._registration_outcome(taken, current, checked, password_matches)
            referral = self._pending_referral_code(email)
            self._discard_pending(email)
            if outcome is None:
                user_id = self._create_confirmed_user(
                    email, checked.password_hash, referral, now, bonus, max_rewards
                )
                return self._load_user(user_id)
        # Raised outside the `with` so that the discard above commits first.
        raise outcome(email)

    @staticmethod
    def _registration_outcome(
        taken: bool,
        current: Optional[PendingRegistration],
        checked: PendingRegistration,
        password_matches: bool,
    ):
        if taken:
            return EmailTakenError
        if current != checked or not password_matches:
            return RegistrationChanged
        return None

    def _read_pending(self, email: str) -> Optional[PendingRegistration]:
        row = self._conn.execute(
            "SELECT password_hash, created_at FROM pending_registrations WHERE email = ?",
            (email,),
        ).fetchone()
        return PendingRegistration(row[0], row[1]) if row else None

    def _pending_referral_code(self, email: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT referral_code FROM pending_registrations WHERE email = ?", (email,)
        ).fetchone()
        return row[0] if row else None

    def _discard_pending(self, email: str) -> None:
        self._conn.execute("DELETE FROM pending_registrations WHERE email = ?", (email,))
        self._conn.execute(
            "DELETE FROM email_codes WHERE email = ? AND purpose = ?",
            (email, CodePurpose.REGISTRATION.value),
        )

    def prune_email_rows(self, now: datetime) -> None:
        with self._lock, self._conn:
            self._prune_email_rows(now)

    def _prune_email_rows(self, now: datetime) -> None:
        self._conn.execute(
            "DELETE FROM email_codes WHERE expires_at < ?", (now.isoformat(),)
        )
        self._conn.execute(
            "DELETE FROM email_sends WHERE sent_at <= ?", ((now - SEND_WINDOW).isoformat(),)
        )
        self._conn.execute(
            "DELETE FROM pending_registrations WHERE created_at <= ?",
            ((now - PENDING_REGISTRATION_MAX_AGE).isoformat(),),
        )

    def _create_confirmed_user(
        self,
        email: str,
        password_hash: str,
        referral_code: Optional[str],
        now: datetime,
        bonus: int,
        max_rewards: int,
    ) -> str:
        referrer = None
        if referral_code:
            row = self._conn.execute(
                "SELECT id FROM users WHERE referral_code = ?", (referral_code,)
            ).fetchone()
            referrer = row[0] if row else None
        user_id = self._insert_password_user(
            email, password_hash, now, bonus if referral_code else 0, referrer
        )
        if referrer:
            self._reward_referrer(referrer, bonus, max_rewards)
        return user_id

    def _email_has_account(self, email: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        return row is not None

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
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_USER_COLUMNS}, s.expires_at"
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

    # ── provider identities ──────────────────────────────────────────────

    def sign_in_with_identity(
        self, identity: ProviderIdentity, now: datetime
    ) -> tuple[User, bool]:
        with self._lock, self._conn:
            linked = self._conn.execute(
                "SELECT user_id FROM identities WHERE provider = ? AND subject = ?",
                (identity.provider, identity.subject),
            ).fetchone()
            if linked:
                return self._load_user(linked[0]), False
            email = self._require_usable_email(identity)
            existing = self._conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()
            if existing:
                self._link_identity(existing[0], identity, email, now)
                return self._load_user(existing[0]), False
            user_id = self._insert_provider_user(identity, email, now)
            return self._load_user(user_id), True

    @staticmethod
    def _require_usable_email(identity: ProviderIdentity) -> str:
        if not identity.email:
            raise ProviderEmailMissing(identity.provider)
        if not identity.email_verified:
            raise ProviderEmailUnverified(identity.provider)
        return identity.email.strip().lower()

    def _link_identity(
        self,
        user_id: str,
        identity: ProviderIdentity,
        email: str,
        now: datetime,
    ) -> None:
        same_provider = self._conn.execute(
            "SELECT 1 FROM identities WHERE user_id = ? AND provider = ?",
            (user_id, identity.provider),
        ).fetchone()
        if same_provider:
            raise ProviderAlreadyLinked(identity.provider)
        self._insert_identity(user_id, identity, email, now)

    def _insert_provider_user(
        self, identity: ProviderIdentity, email: str, now: datetime
    ) -> str:
        user_id = str(ULID())
        # A stale registration code for this email must not later create a second account.
        self._conn.execute("DELETE FROM pending_registrations WHERE email = ?", (email,))
        self._conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
            " referral_code, email_verified, created_via)"
            " VALUES (?, ?, ?, ?, 0, ?, 1, ?)",
            (
                user_id,
                email,
                NO_PASSWORD_HASH,
                now.isoformat(),
                self._unused_code(),
                identity.provider,
            ),
        )
        self._insert_identity(user_id, identity, email, now)
        return user_id

    def _insert_identity(
        self, user_id: str, identity: ProviderIdentity, email: str, now: datetime
    ) -> None:
        self._conn.execute(
            "INSERT INTO identities (provider, subject, user_id, email, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (identity.provider, identity.subject, user_id, email, now.isoformat()),
        )

    def _load_user(self, user_id: str) -> User:
        row = self._conn.execute(
            f"SELECT {_USER_COLUMNS} FROM users u WHERE u.id = ?", (user_id,)
        ).fetchone()
        return _to_user(row)

    def has_identity(self, user_id: str, provider: str, subject: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM identities"
                " WHERE user_id = ? AND provider = ? AND subject = ?",
                (user_id, provider, subject),
            ).fetchone()
        return row is not None

    def list_providers(self, user_id: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT provider FROM identities WHERE user_id = ? ORDER BY provider",
                (user_id,),
            ).fetchall()
        return [row[0] for row in rows]

    def set_apple_refresh_token(self, user_id: str, token: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE identities SET apple_refresh_token = ?"
                " WHERE user_id = ? AND provider = ?",
                (token, user_id, APPLE_PROVIDER),
            )

    def get_apple_refresh_token(self, user_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT apple_refresh_token FROM identities"
                " WHERE user_id = ? AND provider = ?",
                (user_id, APPLE_PROVIDER),
            ).fetchone()
        return row[0] if row else None

    # ── referral redemption ──────────────────────────────────────────────

    def redeem_referral(
        self,
        user_id: str,
        code: str,
        now: datetime,
        window: timedelta,
        bonus: int,
        max_rewards: int,
    ) -> None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT created_via, created_at, referral_redeemed, referred_by,"
                " referral_code FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise UserNotFound(user_id)
            created_via, created_at, redeemed, referred_by, own_code = row
            allowed = (
                created_via != PASSWORD_ORIGIN
                and datetime.fromisoformat(created_at) > now - window
                and not redeemed
                and referred_by is None
            )
            if not allowed:
                raise ReferralNotAllowed(user_id)
            wanted = normalize_code(code)
            referrer = self._find_referrer(wanted)
            if referrer is None or wanted == own_code:
                raise InvalidReferralCode(wanted)
            self._conn.execute(
                "UPDATE users SET referred_by = ?, referral_redeemed = 1,"
                " bonus_credits = bonus_credits + ? WHERE id = ?",
                (referrer, bonus, user_id),
            )
            self._reward_referrer(referrer, bonus, max_rewards)

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
