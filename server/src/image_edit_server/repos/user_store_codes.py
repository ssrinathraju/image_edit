from __future__ import annotations

import hmac
import math
from datetime import datetime, timedelta
from typing import Optional

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    IssueResult,
    hash_code,
)
from image_edit_server.core.referral_codes import normalize_code
from image_edit_server.core.user_store import (
    EmailTakenError,
    PendingRegistration,
    RegistrationChanged,
)
from image_edit_server.schemas.user import User

SEND_WINDOW = timedelta(hours=1)
PENDING_REGISTRATION_MAX_AGE = timedelta(hours=24)
PENDING_EMAIL_CHANGE_MAX_AGE = timedelta(hours=24)

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
CREATE TABLE IF NOT EXISTS pending_email_changes (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    new_email TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class CodesMixin:
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
            if not self._email_has_account(email):
                return ConsumeResult.EXPIRED, None
            self._discard_pending(email)
        # Raised outside the `with` so that the discard above commits first.
        raise EmailTakenError(email)

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
    ) -> Optional[type[Exception]]:
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
        self._conn.execute(
            "DELETE FROM pending_email_changes WHERE created_at <= ?",
            ((now - PENDING_EMAIL_CHANGE_MAX_AGE).isoformat(),),
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
        # Every pending registration passed the age check when it was started.
        user_id = self._insert_password_user(
            email,
            password_hash,
            now,
            bonus if referral_code else 0,
            referrer,
            now.isoformat(),
        )
        if referrer:
            self._reward_referrer(referrer, bonus, max_rewards)
        return user_id

    def _email_has_account(self, email: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        return row is not None
