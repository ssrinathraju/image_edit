from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Optional

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    IssueResult,
)
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.token_hash import hash_token
from image_edit_server.core.user_store import (
    EmailChange,
    EmailTakenError,
    LastSignInMethod,
    ProviderAlreadyLinked,
    ProviderInUse,
    ProviderNotLinked,
)

APPLE_PROVIDER = "apple"


class SecurityMixin:
    def set_password(self, user_id: str, new_hash: str, keep_token: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user_id)
            )
            self._delete_other_sessions(user_id, keep_token)

    def _delete_other_sessions(self, user_id: str, keep_token: str) -> None:
        self._conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?",
            (user_id, hash_token(keep_token)),
        )

    def request_email_change(
        self,
        user_id: str,
        new_email: str,
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        with self._lock, self._conn:
            if self._email_has_account(new_email):
                raise EmailTakenError(new_email)
            self._prune_email_rows(now)
            wait = self._seconds_until_allowed(self._recent_sends(new_email, now), now, limits)
            if wait > 0:
                return IssueResult(issued=False, retry_after_seconds=wait)
            self._store_code(new_email, CodePurpose.EMAIL_CHANGE, code_hash, now, limits)
            self._conn.execute(
                "INSERT OR REPLACE INTO pending_email_changes (user_id, new_email, created_at)"
                " VALUES (?, ?, ?)",
                (user_id, new_email, now.isoformat()),
            )
        return IssueResult(issued=True)

    def get_pending_email_change(self, user_id: str) -> Optional[str]:
        with self._lock:
            return self._read_pending_email_change(user_id)

    def _read_pending_email_change(self, user_id: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT new_email FROM pending_email_changes WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row[0] if row else None

    def _discard_pending_email_change(self, user_id: str) -> None:
        new_email = self._read_pending_email_change(user_id)
        if new_email is None:
            return
        self._conn.execute(
            "DELETE FROM email_codes WHERE email = ? AND purpose = ?",
            (new_email, CodePurpose.EMAIL_CHANGE.value),
        )
        self._conn.execute("DELETE FROM pending_email_changes WHERE user_id = ?", (user_id,))

    def confirm_email_change(
        self, user_id: str, code: str, now: datetime, max_attempts: int, keep_token: str
    ) -> tuple[ConsumeResult, Optional[EmailChange]]:
        with self._lock, self._conn:
            new_email = self._read_pending_email_change(user_id)
            if new_email is None:
                return ConsumeResult.EXPIRED, None
            result = self._consume(
                new_email, CodePurpose.EMAIL_CHANGE, code, now, max_attempts
            )
            if result is not ConsumeResult.OK:
                return result, None
            if self._email_has_account(new_email):
                self._discard_pending_email_change(user_id)
            else:
                return ConsumeResult.OK, self._apply_email_change(user_id, new_email, keep_token)
        # Raised outside the `with` so that the discard above commits first.
        raise EmailTakenError(new_email)

    def _apply_email_change(self, user_id: str, new_email: str, keep_token: str) -> EmailChange:
        old_email = self._conn.execute(
            "SELECT email FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        try:
            self._conn.execute("UPDATE users SET email = ? WHERE id = ?", (new_email, user_id))
        except sqlite3.IntegrityError as error:
            raise EmailTakenError(new_email) from error
        self._conn.execute("DELETE FROM pending_email_changes WHERE user_id = ?", (user_id,))
        self._delete_other_sessions(user_id, keep_token)
        return EmailChange(old_email=old_email, new_email=new_email)

    def link_identity(self, user_id: str, identity: ProviderIdentity, now: datetime) -> None:
        with self._lock, self._conn:
            owner = self._conn.execute(
                "SELECT user_id FROM identities WHERE provider = ? AND subject = ?",
                (identity.provider, identity.subject),
            ).fetchone()
            if owner and owner[0] != user_id:
                raise ProviderInUse(identity.provider)
            email = identity.email.strip().lower() if identity.email else None
            self._link_identity(user_id, identity, email, now)

    def unlink_identity(self, user_id: str, provider: str) -> Optional[str]:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT apple_refresh_token FROM identities WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            ).fetchone()
            if row is None:
                raise ProviderNotLinked(provider)
            if not self._has_another_sign_in_method(user_id, provider):
                raise LastSignInMethod(provider)
            self._conn.execute(
                "DELETE FROM identities WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )
        return row[0] if provider == APPLE_PROVIDER else None

    def _has_another_sign_in_method(self, user_id: str, provider: str) -> bool:
        row = self._conn.execute(
            "SELECT u.password_hash <> '' OR EXISTS ("
            "  SELECT 1 FROM identities i WHERE i.user_id = u.id AND i.provider <> ?)"
            " FROM users u WHERE u.id = ?",
            (provider, user_id),
        ).fetchone()
        return bool(row and row[0])
