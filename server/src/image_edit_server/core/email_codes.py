from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

CODE_DIGITS = 6


class CodePurpose(str, Enum):
    VERIFY_EMAIL = "verify_email"
    PASSWORD_RESET = "password_reset"


class ConsumeResult(str, Enum):
    OK = "ok"
    WRONG = "wrong"
    EXPIRED = "expired"


@dataclass(frozen=True)
class CodeLimits:
    ttl: timedelta
    resend_interval: timedelta
    max_per_hour: int


@dataclass(frozen=True)
class IssueResult:
    """issued is False when a sending limit applies; retry_after_seconds then says when to retry."""

    issued: bool
    retry_after_seconds: int = 0


def generate_code() -> str:
    return f"{secrets.randbelow(10 ** CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(user_id: str, purpose: CodePurpose, code: str) -> str:
    return hashlib.sha256(f"{user_id}:{purpose.value}:{code}".encode("utf-8")).hexdigest()
