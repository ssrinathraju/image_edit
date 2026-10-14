from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets

SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000
HASH_BYTES = 32
SALT_BYTES = 16


def hash_password(plain: str) -> str:
    """Hash a password into a self-describing `pbkdf2_sha256$iterations$salt$hash` string."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = _pbkdf2(plain, salt, PBKDF2_ITERATIONS, HASH_BYTES)
    return "$".join([SCHEME, str(PBKDF2_ITERATIONS), _b64(salt), _b64(digest)])


def verify_password(plain: str, stored: str) -> bool:
    """Check a password against a stored hash; a malformed stored value is False."""
    try:
        scheme, iterations, salt_b64, hash_b64 = stored.split("$")
        if scheme != SCHEME:
            return False
        expected = base64.b64decode(hash_b64, validate=True)
        actual = _pbkdf2(
            plain, base64.b64decode(salt_b64, validate=True), int(iterations), len(expected)
        )
    except (ValueError, TypeError, binascii.Error):
        return False
    return hmac.compare_digest(actual, expected)


def _pbkdf2(plain: str, salt: bytes, iterations: int, dklen: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations, dklen)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
