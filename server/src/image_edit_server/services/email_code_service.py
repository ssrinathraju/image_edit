from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    generate_code,
    hash_code,
)
from image_edit_server.core.email_sender import EmailSender
from image_edit_server.core.user_store import UserStore

logger = logging.getLogger(__name__)

_PURPOSE_TEXT = {
    CodePurpose.VERIFY_EMAIL: ("verification code", "verify your email address"),
    CodePurpose.PASSWORD_RESET: ("password reset code", "reset your password"),
}


@dataclass(frozen=True)
class CodeOutcome:
    """code is None when a sending limit applied and nothing was issued."""

    code: Optional[str]
    retry_after_seconds: int = 0


def limits_from(settings: Settings) -> CodeLimits:
    return CodeLimits(
        ttl=timedelta(minutes=settings.EMAIL_CODE_TTL_MINUTES),
        resend_interval=timedelta(seconds=settings.EMAIL_RESEND_SECONDS),
        max_per_hour=settings.EMAIL_MAX_PER_HOUR,
    )


def issue_code(
    users: UserStore,
    user_id: str,
    purpose: CodePurpose,
    settings: Settings,
    now: datetime,
) -> CodeOutcome:
    """Generate and store a code for the account, unless a sending limit applies."""
    code = generate_code()
    result = users.issue_code(
        user_id, purpose, hash_code(user_id, purpose, code), now, limits_from(settings)
    )
    if not result.issued:
        return CodeOutcome(code=None, retry_after_seconds=result.retry_after_seconds)
    return CodeOutcome(code=code)


def compose_message(
    purpose: CodePurpose, code: str, ttl_minutes: int
) -> tuple[str, str]:
    label, action = _PURPOSE_TEXT[purpose]
    subject = f"Your image_edit {label}"
    body = (
        f"Your image_edit {label} is {code}. Use it to {action}. "
        f"It expires in {ttl_minutes} minutes."
    )
    return subject, body


def deliver(
    sender: EmailSender,
    user_id: str,
    to: str,
    purpose: CodePurpose,
    code: str,
    ttl_minutes: int,
) -> None:
    """Send the code; a failure is logged without the code and never raised."""
    try:
        subject, body = compose_message(purpose, code, ttl_minutes)
        sender.send(to, subject, body)
    except Exception as error:
        logger.error(
            "Could not send %s email for user %s: %s",
            purpose.value,
            user_id,
            type(error).__name__,
        )
