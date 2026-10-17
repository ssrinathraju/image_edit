from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import BackgroundTasks, HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_codes import CodePurpose, ConsumeResult
from image_edit_server.core.email_sender import EmailSender
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.core.passwords import hash_password, verify_password
from image_edit_server.core.identity_verifier import (
    IdentityVerifier,
    InvalidProviderToken,
    ProviderIdentity,
    ProviderUnavailable,
)
from image_edit_server.core.user_store import (
    EmailTakenError,
    InvalidReferralCode,
    ProviderAlreadyLinked,
    ProviderEmailMissing,
    ProviderEmailUnverified,
    UserStore,
)
from image_edit_server.schemas.api import ErrorBody
from image_edit_server.schemas.user import User
from image_edit_server.services import email_code_service
from image_edit_server.services.apple_revocation import AppleRevocationClient

logger = logging.getLogger(__name__)

MAX_EMAIL_CHARS = 254
PROVIDER_TOKEN_MAX_AGE = timedelta(minutes=5)
APPLE = "apple"
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Verified against when the email is unknown so both failures cost the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _error(status: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status, ErrorBody(error=code, detail=detail).model_dump())


def _already_verified() -> HTTPException:
    return _error(409, "already_verified", "this email is already verified")


def _invalid_reset_code() -> HTTPException:
    return _error(400, "invalid_code", "code is incorrect or has expired")


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        users: UserStore,
        throttle: LoginThrottle,
        settings: Settings,
        purge_user_jobs: Callable[[str], None],
        sender: EmailSender,
        clock: Callable[[], datetime] = _utc_now,
        verifiers: Optional[dict[str, IdentityVerifier]] = None,
        apple_client: Optional[AppleRevocationClient] = None,
    ) -> None:
        self._users = users
        self._throttle = throttle
        self._settings = settings
        self._purge_user_jobs = purge_user_jobs
        self._sender = sender
        self._clock = clock
        self._verifiers = verifiers if verifiers is not None else {}
        self._apple_client = apple_client

    def register(
        self,
        email: str,
        password: str,
        referral_code: Optional[str],
        background: BackgroundTasks,
    ) -> tuple[str, User]:
        """Create an unverified account, email it a code, and start its first session."""
        normalized = normalize_email(email)
        self._validate_credentials_format(normalized, password)
        try:
            user = self._users.register_user(
                normalized,
                hash_password(password),
                referral_code,
            )
        except EmailTakenError:
            raise _error(409, "email_taken", "this email is already registered")
        except InvalidReferralCode:
            raise _error(
                400, "invalid_referral_code", "this referral code was not recognised"
            )
        self._send_code(user, CodePurpose.VERIFY_EMAIL, background)
        return self._start_session(user), user

    def verify_email(self, user: User, code: str) -> None:
        if user.email_verified:
            raise _already_verified()
        result = self._users.consume_code(
            user.id,
            CodePurpose.VERIFY_EMAIL,
            code.strip(),
            self._clock(),
            self._settings.EMAIL_CODE_MAX_ATTEMPTS,
        )
        if result is ConsumeResult.WRONG:
            raise _error(400, "invalid_code", "the code is incorrect")
        if result is ConsumeResult.EXPIRED:
            raise _error(
                400, "code_expired", "the code has expired; request a new one"
            )
        self._mark_verified(user.id)

    def resend_verification(self, user: User, background: BackgroundTasks) -> None:
        if user.email_verified:
            raise _already_verified()
        outcome = self._send_code(user, CodePurpose.VERIFY_EMAIL, background)
        if outcome.code is None:
            raise HTTPException(
                429,
                ErrorBody(
                    error="too_many_requests",
                    detail=f"too many codes requested; retry in {outcome.retry_after_seconds} seconds",
                ).model_dump(),
                headers={"Retry-After": str(outcome.retry_after_seconds)},
            )

    def request_password_reset(self, email: str, background: BackgroundTasks) -> None:
        """Always succeeds for a well-formed email, so it never reveals whether an account exists."""
        normalized = normalize_email(email)
        self._validate_email_format(normalized)
        user = self._users.get_by_email(normalized)
        if user is not None:
            self._send_code(user, CodePurpose.PASSWORD_RESET, background)

    def confirm_password_reset(
        self, email: str, code: str, new_password: str
    ) -> tuple[str, User]:
        normalized = normalize_email(email)
        self._validate_password_format(new_password)
        new_hash = hash_password(new_password)
        user = self._users.get_by_email(normalized)
        if user is None:
            raise _invalid_reset_code()
        result = self._users.reset_password(
            user.id,
            code.strip(),
            new_hash,
            self._clock(),
            self._settings.EMAIL_CODE_MAX_ATTEMPTS,
            self._settings.REFERRAL_BONUS,
            self._settings.REFERRAL_MAX_REWARDS,
        )
        if result is not ConsumeResult.OK:
            raise _invalid_reset_code()
        self._throttle.reset(normalized)
        verified = self._users.get_by_id(user.id) or user
        return self._start_session(verified), verified

    def login(self, email: str, password: str) -> tuple[str, User]:
        normalized = normalize_email(email)
        self._reject_if_locked(normalized)
        user = self._users.get_by_email(normalized)
        stored = self._users.get_password_hash(user.id) if user else None
        # An account without a password has an empty hash; it must fail even for the
        # dummy hash's own password, so the dummy only stands in for timing.
        matches = verify_password(password, stored or _DUMMY_HASH)
        if not (matches and stored and user is not None):
            self._throttle.record_failure(normalized)
            raise _error(401, "invalid_credentials", "email or password is incorrect")
        self._throttle.reset(normalized)
        return self._start_session(user), user

    def logout(self, token: str) -> None:
        self._users.delete_session(token)

    def sign_in_with_provider(
        self,
        provider: str,
        token: str,
        *,
        nonce: Optional[str] = None,
        authorization_code: Optional[str] = None,
    ) -> tuple[str, User, bool]:
        """Sign in to the account for a provider token, linking or creating it; returns (session, user, created)."""
        identity = self._verify_provider_token(provider, token, nonce, 401)
        try:
            user, created = self._users.sign_in_with_identity(
                identity,
                self._clock(),
                self._settings.REFERRAL_BONUS,
                self._settings.REFERRAL_MAX_REWARDS,
            )
        except ProviderEmailUnverified:
            raise _error(
                400, "provider_email_unverified", f"the {provider} email is not verified"
            )
        except ProviderEmailMissing:
            raise _error(
                400,
                "provider_email_missing",
                f"{provider} did not share an email address for this sign-in",
            )
        except ProviderAlreadyLinked:
            raise _error(
                409,
                "provider_already_linked",
                f"this account is already linked to another {provider} account",
            )
        if provider == APPLE:
            self._store_apple_refresh_token(user, authorization_code)
        logger.info("Provider sign-in: user %s via %s created=%s", user.id, provider, created)
        return self._start_session(user), user, created

    def delete_account(
        self,
        user: User,
        password: Optional[str] = None,
        *,
        provider: Optional[str] = None,
        token: Optional[str] = None,
        nonce: Optional[str] = None,
        background: Optional[BackgroundTasks] = None,
    ) -> None:
        if provider is not None and token is not None:
            self._confirm_deletion_with_provider(user, provider, token, nonce)
        else:
            self._confirm_deletion_with_password(user, password or "")
        apple_token = self._users.get_apple_refresh_token(user.id)
        # The user goes first so a submit that was already in flight cannot
        # attach a job to an account that is about to disappear; the worker
        # drops any job whose owner is gone.
        self._users.delete_user(user.id)
        self._purge_user_jobs(user.id)
        self._schedule_apple_revocation(apple_token, background)
        logger.info("Deleted account %s", user.id)

    def _confirm_deletion_with_password(self, user: User, password: str) -> None:
        self._reject_if_locked(user.email)
        stored = self._users.get_password_hash(user.id)
        if stored is None or not verify_password(password, stored):
            self._throttle.record_failure(user.email)
            raise _error(403, "invalid_password", "password is incorrect")
        self._throttle.reset(user.email)

    def _confirm_deletion_with_provider(
        self, user: User, provider: str, token: str, nonce: Optional[str]
    ) -> None:
        identity = self._verify_provider_token(provider, token, nonce, 403)
        fresh = self._clock() - identity.issued_at <= PROVIDER_TOKEN_MAX_AGE
        if not fresh or not self._users.has_identity(user.id, provider, identity.subject):
            raise _error(
                403,
                "invalid_provider_token",
                f"sign in with {provider} again to confirm; the token is old or belongs"
                " to another account",
            )

    def _verify_provider_token(
        self, provider: str, token: str, nonce: Optional[str], rejection_status: int
    ) -> ProviderIdentity:
        verifier = self._verifiers.get(provider)
        if verifier is None:
            raise _error(
                503, "provider_not_configured", f"sign-in with {provider} is not configured"
            )
        try:
            return verifier.verify(token, nonce=nonce)
        except InvalidProviderToken:
            raise _error(
                rejection_status,
                "invalid_provider_token",
                f"the {provider} token was rejected; sign in with {provider} again",
            )
        except ProviderUnavailable:
            raise _error(
                503,
                "provider_unavailable",
                f"{provider} could not be reached; try again shortly",
            )

    def _store_apple_refresh_token(self, user: User, code: Optional[str]) -> None:
        if self._apple_client is None or not code:
            return
        if self._users.get_apple_refresh_token(user.id):
            return
        refresh_token = self._apple_client.exchange_code(code)
        if refresh_token:
            self._users.set_apple_refresh_token(user.id, refresh_token)

    def _schedule_apple_revocation(
        self, apple_token: Optional[str], background: Optional[BackgroundTasks]
    ) -> None:
        if not apple_token or self._apple_client is None:
            return
        if background is None:
            self._apple_client.revoke(apple_token)
        else:
            background.add_task(self._apple_client.revoke, apple_token)

    def _reject_if_locked(self, email: str) -> None:
        if self._throttle.is_locked(email):
            raise _error(
                429,
                "too_many_attempts",
                f"too many failed attempts; try again in "
                f"{self._settings.LOGIN_LOCKOUT_MINUTES} minutes",
            )

    def _mark_verified(self, user_id: str) -> None:
        self._users.mark_email_verified(
            user_id, self._settings.REFERRAL_BONUS, self._settings.REFERRAL_MAX_REWARDS
        )

    def _send_code(
        self, user: User, purpose: CodePurpose, background: BackgroundTasks
    ) -> email_code_service.CodeOutcome:
        outcome = email_code_service.issue_code(
            self._users, user.id, purpose, self._settings, self._clock()
        )
        if outcome.code is not None:
            background.add_task(
                email_code_service.deliver,
                self._sender,
                user.id,
                user.email,
                purpose,
                outcome.code,
                self._settings.EMAIL_CODE_TTL_MINUTES,
            )
        return outcome

    def _start_session(self, user: User) -> str:
        ttl = timedelta(days=self._settings.SESSION_TTL_DAYS)
        return self._users.create_session(user.id, ttl)

    def _validate_credentials_format(self, email: str, password: str) -> None:
        self._validate_email_format(email)
        self._validate_password_format(password)

    @staticmethod
    def _validate_email_format(email: str) -> None:
        if len(email) > MAX_EMAIL_CHARS or not EMAIL_PATTERN.match(email):
            raise _error(400, "invalid_credentials_format", "email address is not valid")

    def _validate_password_format(self, password: str) -> None:
        s = self._settings
        if not s.PASSWORD_MIN_CHARS <= len(password) <= s.PASSWORD_MAX_CHARS:
            raise _error(
                400,
                "invalid_credentials_format",
                f"password must be {s.PASSWORD_MIN_CHARS}..{s.PASSWORD_MAX_CHARS} characters",
            )
