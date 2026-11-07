from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from ulid import ULID

from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.user_store import (
    AgeRequired,
    ProviderAlreadyLinked,
    ProviderEmailMissing,
    ProviderEmailUnverified,
    UnderAgeSignUp,
)
from image_edit_server.core.token_cipher import VERSION_PREFIX
from image_edit_server.schemas.user import User

logger = logging.getLogger(__name__)

# An account made through a provider stores this instead of a password hash;
# verify_password rejects it, so password login fails like a wrong password.
NO_PASSWORD_HASH = ""
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


class IdentitiesMixin:
    def sign_in_with_identity(
        self,
        identity: ProviderIdentity,
        now: datetime,
        adult_confirmed: Optional[bool] = None,
        before_create: Optional[Callable[[], None]] = None,
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
            if before_create is not None:
                before_create()
            if adult_confirmed is None:
                raise AgeRequired(identity.provider)
            if not adult_confirmed:
                raise UnderAgeSignUp(identity.provider)
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
        email: Optional[str],
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
            " referral_code, email_verified, created_via, age_confirmed_at)"
            " VALUES (?, ?, ?, ?, 0, ?, 1, ?, ?)",
            (
                user_id,
                email,
                NO_PASSWORD_HASH,
                now.isoformat(),
                self._unused_code(),
                identity.provider,
                now.isoformat(),
            ),
        )
        self._insert_identity(user_id, identity, email, now)
        return user_id

    def _insert_identity(
        self, user_id: str, identity: ProviderIdentity, email: Optional[str], now: datetime
    ) -> None:
        self._conn.execute(
            "INSERT INTO identities (provider, subject, user_id, email, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (identity.provider, identity.subject, user_id, email, now.isoformat()),
        )

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
        if self._token_cipher is None:
            raise RuntimeError(
                "cannot store an Apple token without TOKEN_ENCRYPTION_KEY; "
                "set it whenever the Apple key settings are set"
            )
        sealed = self._token_cipher.encrypt(token, user_id)
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE identities SET apple_refresh_token = ?"
                " WHERE user_id = ? AND provider = ?",
                (sealed, user_id, APPLE_PROVIDER),
            )

    def get_apple_refresh_token(self, user_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT apple_refresh_token FROM identities"
                " WHERE user_id = ? AND provider = ?",
                (user_id, APPLE_PROVIDER),
            ).fetchone()
        return self._open_apple_token(user_id, row[0]) if row else None

    def _open_apple_token(self, user_id: str, stored: Optional[str]) -> Optional[str]:
        if stored is None:
            return None
        token = self._token_cipher.decrypt(stored, user_id) if self._token_cipher else None
        if token is None:
            logger.warning("apple_token_unreadable user=%s", user_id)
        return token

    def _discard_unencrypted_apple_tokens(self) -> None:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE identities SET apple_refresh_token = NULL"
                " WHERE apple_refresh_token IS NOT NULL"
                " AND substr(apple_refresh_token, 1, ?) <> ?",
                (len(VERSION_PREFIX), VERSION_PREFIX),
            )
        if cursor.rowcount > 0:
            logger.info("apple_tokens_discarded count=%d", cursor.rowcount)
