from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Optional

from fastapi import BackgroundTasks, HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.age import InvalidDateOfBirth, UnderAge, check_date_of_birth
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
    AgeRequired,
    EmailTakenError,
    InvalidReferralCode,
    ProviderAlreadyLinked,
    ProviderEmailMissing,
    ProviderEmailUnverified,
    RegistrationChanged,
    UnderAge as StoreUnderAge,
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


def _too_many_codes(retry_after_seconds: int) -> HTTPException:
    return HTTPException(
        429,
        ErrorBody(
            error="too_many_requests",
            detail=f"too many codes requested; retry in {retry_after_seconds} seconds",
        ).model_dump(),
        headers={"Retry-After": str(retry_after_seconds)},
    )


def _invalid_reset_code() -> HTTPException:
    return _error(400, "invalid_code", "code is incorrect or has expired")


def _under_age() -> HTTPException:
    return _error(400, "under_age", "you must be 18 or older to use this app")


def _invalid_date_of_birth(error: InvalidDateOfBirth) -> HTTPException:
    return _error(400, "invalid_date_of_birth", str(error))


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
        date_of_birth: str,
        referral_code: Optional[str],
        background: BackgroundTasks,
    ) -> None:
        """Hold an adult's registration as pending and email its code; no account exists until it is confirmed."""
        self._require_adult_date_of_birth(date_of_birth)
        normalized = normalize_email(email)
        self._validate_credentials_format(normalized, password)
        password_hash = hash_password(password)
        code, code_hash = email_code_service.new_code(normalized, CodePurpose.REGISTRATION)
        try:
            result = self._users.start_registration(
                normalized,
                password_hash,
                referral_code,
                code_hash,
                self._clock(),
                email_code_service.limits_from(self._settings),
            )
        except EmailTakenError:
            raise _error(409, "email_taken", "this email is already registered")
        except InvalidReferralCode:
            raise _error(
                400, "invalid_referral_code", "this referral code was not recognised"
            )
        if not result.issued:
            raise _too_many_codes(result.retry_after_seconds)
        self._schedule_code_email(normalized, CodePurpose.REGISTRATION, code, background)

    def confirm_registration(self, email: str, code: str, password: str) -> tuple[str, User]:
        """Create the account for a pending registration whose emailed code and password are right."""
        normalized = normalize_email(email)
        try:
            result, pending = self._users.check_registration_code(
                normalized,
                code.strip(),
                self._clock(),
                self._settings.EMAIL_CODE_MAX_ATTEMPTS,
            )
        except EmailTakenError:
            raise _error(409, "email_taken", "this email is already registered")
        if result is ConsumeResult.WRONG:
            raise _error(400, "invalid_code", "the code is incorrect")
        if result is ConsumeResult.EXPIRED or pending is None:
            raise _error(400, "code_expired", "the code has expired; register again")
        # The slow hash check runs outside the store lock.
        password_matches = verify_password(password, pending.password_hash)
        try:
            user = self._users.complete_registration(
                normalized,
                pending,
                password_matches,
                self._clock(),
                self._settings.REFERRAL_BONUS,
                self._settings.REFERRAL_MAX_REWARDS,
            )
        except EmailTakenError:
            raise _error(409, "email_taken", "this email is already registered")
        except RegistrationChanged:
            raise _error(
                409,
                "registration_changed",
                "the registration changed since the code was sent; register again",
            )
        return self._start_session(user), user

    def request_password_reset(self, email: str, background: BackgroundTasks) -> None:
        """Always succeeds for a well-formed email, so it never reveals whether an account exists."""
        normalized = normalize_email(email)
        self._validate_email_format(normalized)
        if self._users.get_by_email(normalized) is None:
            return
        outcome = email_code_service.issue_code(
            self._users,
            normalized,
            CodePurpose.PASSWORD_RESET,
            self._settings,
            self._clock(),
        )
        if outcome.code is not None:
            self._schedule_code_email(
                normalized, CodePurpose.PASSWORD_RESET, outcome.code, background
            )

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
            normalized,
            code.strip(),
            new_hash,
            self._clock(),
            self._settings.EMAIL_CODE_MAX_ATTEMPTS,
        )
        if result is not ConsumeResult.OK:
            raise _invalid_reset_code()
        self._throttle.reset(normalized)
        return self._start_session(user), user

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
        date_of_birth: Optional[str] = None,
    ) -> tuple[str, User, bool]:
        """Sign in to the account for a provider token, linking or creating it; returns (session, user, created)."""
        adult_confirmed = self._adult_confirmed(date_of_birth)
        identity = self._verify_provider_token(provider, token, nonce, 401)
        try:
            user, created = self._users.sign_in_with_identity(
                identity, self._clock(), adult_confirmed
            )
        except AgeRequired:
            raise _error(
                400,
                "age_required",
                "send a date_of_birth (YYYY-MM-DD) to create an account",
            )
        except StoreUnderAge:
            logger.info("Refused a provider sign-up: under 18")
            raise _under_age()
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

    def confirm_age(self, user: User, date_of_birth: str) -> None:
        """Mark the account's age confirmed for an adult date; the date itself is never kept."""
        if user.age_confirmed:
            raise _error(409, "age_already_confirmed", "this account's age is already confirmed")
        try:
            check_date_of_birth(date_of_birth, self._today())
        except InvalidDateOfBirth as error:
            raise _invalid_date_of_birth(error)
        except UnderAge:
            logger.info("Refused an age confirmation: under 18")
            raise _error(403, "under_age", "you must be 18 or older to use this app")
        self._users.confirm_age(user.id, self._clock())
        logger.info("Confirmed the age of account %s", user.id)

    def accept_consent(self, user: User, version: str) -> None:
        """Record acceptance of the current consent version; any other version is refused."""
        current = self._settings.CONSENT_VERSION
        if version != current:
            raise _error(
                400,
                "consent_version_mismatch",
                f"the current consent version is {current!r}, got {version!r}",
            )
        self._users.set_consent(user.id, version, self._clock())
        logger.info("Account %s accepted consent version %s", user.id, version)

    def withdraw_consent(self, user: User) -> None:
        self._users.clear_consent(user.id)
        logger.info("Account %s withdrew consent", user.id)

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

    def _today(self) -> date:
        return self._clock().astimezone(timezone.utc).date()

    def _require_adult_date_of_birth(self, date_of_birth: str) -> None:
        try:
            check_date_of_birth(date_of_birth, self._today())
        except InvalidDateOfBirth as error:
            raise _invalid_date_of_birth(error)
        except UnderAge:
            logger.info("Refused a registration: under 18")
            raise _under_age()

    def _adult_confirmed(self, date_of_birth: Optional[str]) -> Optional[bool]:
        """None when no date was sent, otherwise whether it shows an adult."""
        if date_of_birth is None:
            return None
        try:
            check_date_of_birth(date_of_birth, self._today())
        except InvalidDateOfBirth as error:
            raise _invalid_date_of_birth(error)
        except UnderAge:
            return False
        return True

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
            self._revoke_apple_token(apple_token)
        else:
            background.add_task(self._revoke_apple_token, apple_token)

    def _revoke_apple_token(self, apple_token: str) -> None:
        # Runs after the response; nothing may depend on it, so it never raises.
        try:
            self._apple_client.revoke(apple_token)
        except Exception as error:
            logger.warning("Apple revocation failed: %s", type(error).__name__)

    def _reject_if_locked(self, email: str) -> None:
        if self._throttle.is_locked(email):
            raise _error(
                429,
                "too_many_attempts",
                f"too many failed attempts; try again in "
                f"{self._settings.LOGIN_LOCKOUT_MINUTES} minutes",
            )

    def _schedule_code_email(
        self,
        email: str,
        purpose: CodePurpose,
        code: str,
        background: BackgroundTasks,
    ) -> None:
        background.add_task(
            email_code_service.deliver,
            self._sender,
            email,
            purpose,
            code,
            self._settings.EMAIL_CODE_TTL_MINUTES,
        )

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
