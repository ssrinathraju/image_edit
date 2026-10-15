from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Callable, Optional

from fastapi import HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.core.passwords import hash_password, verify_password
from image_edit_server.core.user_store import (
    EmailTakenError,
    InvalidReferralCode,
    UserStore,
)
from image_edit_server.schemas.api import ErrorBody
from image_edit_server.schemas.user import User

logger = logging.getLogger(__name__)

MAX_EMAIL_CHARS = 254
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Verified against when the email is unknown so both failures cost the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def _error(status: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status, ErrorBody(error=code, detail=detail).model_dump())


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        users: UserStore,
        throttle: LoginThrottle,
        settings: Settings,
        purge_user_jobs: Callable[[str], None],
    ) -> None:
        self._users = users
        self._throttle = throttle
        self._settings = settings
        self._purge_user_jobs = purge_user_jobs

    def register(
        self, email: str, password: str, referral_code: Optional[str] = None
    ) -> tuple[str, User]:
        """Create an account and its first session; returns (token, user)."""
        normalized = normalize_email(email)
        self._validate_credentials_format(normalized, password)
        try:
            user = self._users.register_user(
                normalized,
                hash_password(password),
                referral_code,
                self._settings.REFERRAL_BONUS,
                self._settings.REFERRAL_MAX_REWARDS,
            )
        except EmailTakenError:
            raise _error(409, "email_taken", "this email is already registered")
        except InvalidReferralCode:
            raise _error(
                400, "invalid_referral_code", "this referral code was not recognised"
            )
        return self._start_session(user), user

    def login(self, email: str, password: str) -> tuple[str, User]:
        normalized = normalize_email(email)
        self._reject_if_locked(normalized)
        user = self._users.get_by_email(normalized)
        stored = self._users.get_password_hash(user.id) if user else None
        if not verify_password(password, stored or _DUMMY_HASH) or user is None:
            self._throttle.record_failure(normalized)
            raise _error(401, "invalid_credentials", "email or password is incorrect")
        self._throttle.reset(normalized)
        return self._start_session(user), user

    def logout(self, token: str) -> None:
        self._users.delete_session(token)

    def delete_account(self, user: User, password: str) -> None:
        self._reject_if_locked(user.email)
        stored = self._users.get_password_hash(user.id)
        if stored is None or not verify_password(password, stored):
            self._throttle.record_failure(user.email)
            raise _error(403, "invalid_password", "password is incorrect")
        self._throttle.reset(user.email)
        # The user goes first so a submit that was already in flight cannot
        # attach a job to an account that is about to disappear; the worker
        # drops any job whose owner is gone.
        self._users.delete_user(user.id)
        self._purge_user_jobs(user.id)
        logger.info("Deleted account %s", user.id)

    def _reject_if_locked(self, email: str) -> None:
        if self._throttle.is_locked(email):
            raise _error(
                429,
                "too_many_attempts",
                f"too many failed attempts; try again in "
                f"{self._settings.LOGIN_LOCKOUT_MINUTES} minutes",
            )

    def _start_session(self, user: User) -> str:
        ttl = timedelta(days=self._settings.SESSION_TTL_DAYS)
        return self._users.create_session(user.id, ttl)

    def _validate_credentials_format(self, email: str, password: str) -> None:
        s = self._settings
        if len(email) > MAX_EMAIL_CHARS or not EMAIL_PATTERN.match(email):
            raise _error(400, "invalid_credentials_format", "email address is not valid")
        if not s.PASSWORD_MIN_CHARS <= len(password) <= s.PASSWORD_MAX_CHARS:
            raise _error(
                400,
                "invalid_credentials_format",
                f"password must be {s.PASSWORD_MIN_CHARS}..{s.PASSWORD_MAX_CHARS} characters",
            )
