from __future__ import annotations

import secrets
from datetime import timedelta

# No 0/O or 1/I, so a code read aloud or typed from a screenshot is unambiguous.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8
REDEEM_WINDOW = timedelta(hours=24)


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(code: str) -> str:
    return code.strip().upper()
