from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from fastapi import BackgroundTasks, HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_codes import CodePurpose, ConsumeResult
from image_edit_server.core.email_sender import EmailSender
from image_edit_server.core.passwords import hash_password
from image_edit_server.core.user_store import (
    EmailTakenError,
    LastSignInMethod,
    ProviderAlreadyLinked,
    ProviderInUse,
    ProviderNotLinked,
    UserStore,
)
from image_edit_server.schemas.user import Reauth, User
from image_edit_server.services import email_code_service
from image_edit_server.services.auth_service import (
    AuthService,
    api_error,
    normalize_email,
    too_many_codes,
)

logger = logging.getLogger(__name__)

APPLE = "apple"


def _email_taken() -> HTTPException:
    return api_error(409, "email_taken", "this email is already registered")


class AccountSecurityService:
    """Password, email and sign-in-provider changes for a signed-in account."""

    def __init__(
        self,
        users: UserStore,
        auth: AuthService,
        settings: Settings,
        sender: EmailSender,
        clock: Callable[[], datetime],
    ) -> None:
        self._users = users
        self._auth = auth
        self._settings = settings
        self._sender = sender
        self._clock = clock

    def change_password(
        self,
        user: User,
        token: str,
        new_password: str,
        reauth: Reauth,
        background: BackgroundTasks,
    ) -> None:
        """Set a new password, sign out every other session and tell the account's address."""
        self._auth.validate_password_format(new_password)
        self._auth.reauthenticate(user, reauth)
        # The slow hash runs outside the store lock.
        new_hash = hash_password(new_password)
        self._users.set_password(user.id, new_hash, token)
        self._notify(user.email, email_code_service.compose_password_changed(), background)
        logger.info("password_changed: user %s", user.id)

    def request_email_change(
        self, user: User, new_email: str, reauth: Reauth, background: BackgroundTasks
    ) -> None:
        """Email a code to the new address and remember the pending change."""
        normalized = normalize_email(new_email)
        self._auth.validate_email_format(normalized)
        if normalized == user.email:
            raise api_error(
                400, "invalid_credentials_format", "this is already your email address"
            )
        self._auth.reauthenticate(user, reauth)
        code, code_hash = email_code_service.new_code(normalized, CodePurpose.EMAIL_CHANGE)
        try:
            result = self._users.request_email_change(
                user.id,
                normalized,
                code_hash,
                self._clock(),
                email_code_service.limits_from(self._settings),
            )
        except EmailTakenError:
            raise _email_taken()
        if not result.issued:
            raise too_many_codes(result.retry_after_seconds)
        background.add_task(
            email_code_service.deliver,
            self._sender,
            normalized,
            CodePurpose.EMAIL_CHANGE,
            code,
            self._settings.EMAIL_CODE_TTL_MINUTES,
        )
        logger.info("email_change_requested: user %s", user.id)

    def confirm_email_change(
        self, user: User, token: str, code: str, background: BackgroundTasks
    ) -> str:
        """Switch the account to the pending address when the code is right; returns it."""
        try:
            result, change = self._users.confirm_email_change(
                user.id,
                code.strip(),
                self._clock(),
                self._settings.EMAIL_CODE_MAX_ATTEMPTS,
                token,
            )
        except EmailTakenError:
            raise _email_taken()
        if result is ConsumeResult.WRONG:
            raise api_error(400, "invalid_code", "the code is incorrect")
        if result is ConsumeResult.EXPIRED or change is None:
            raise api_error(
                400, "code_expired", "the code has expired or was never requested; ask for a new one"
            )
        message = email_code_service.compose_email_changed(
            change.new_email, self._settings.SUPPORT_EMAIL
        )
        self._notify(change.old_email, message, background)
        logger.info("email_changed: user %s", user.id)
        return change.new_email

    def link_provider(
        self,
        user: User,
        provider: str,
        token: str,
        reauth: Reauth,
        *,
        nonce: Optional[str] = None,
        authorization_code: Optional[str] = None,
    ) -> None:
        """Link a new identity, after re-authenticating against the identities already linked."""
        self._auth.reauthenticate(user, reauth)
        identity = self._auth.verify_provider_token(provider, token, nonce, 401)
        try:
            self._users.link_identity(user.id, identity, self._clock())
        except ProviderInUse:
            raise api_error(
                409,
                "provider_in_use",
                f"this {provider} account is already linked to another account",
            )
        except ProviderAlreadyLinked:
            raise api_error(
                409,
                "provider_already_linked",
                f"this account already has a {provider} account linked",
            )
        if provider == APPLE:
            self._auth.store_apple_refresh_token(user, authorization_code)
        logger.info("provider_linked: user %s via %s", user.id, provider)

    def unlink_provider(
        self, user: User, provider: str, reauth: Reauth, background: BackgroundTasks
    ) -> None:
        """Remove a provider, unless it is the account's last way to sign in."""
        self._auth.reauthenticate(user, reauth)
        try:
            apple_token = self._users.unlink_identity(user.id, provider)
        except ProviderNotLinked:
            raise api_error(404, "not_found", f"no {provider} account is linked")
        except LastSignInMethod:
            raise api_error(
                409,
                "last_sign_in_method",
                f"{provider} is the only way to sign in; set a password or link another"
                " provider first",
            )
        self._auth.schedule_apple_revocation(apple_token, background)
        logger.info("provider_unlinked: user %s from %s", user.id, provider)

    def _notify(
        self, to: str, message: tuple[str, str], background: BackgroundTasks
    ) -> None:
        background.add_task(email_code_service.deliver_notice, self._sender, to, message)
