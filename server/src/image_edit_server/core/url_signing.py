from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timedelta

RESULT_URL_TTL = timedelta(minutes=15)


def sign(job_id: str, expires_at: int, secret: bytes) -> str:
    """HMAC-SHA256 over `<job_id>:<expires_at>`, base64url without padding."""
    digest = hmac.new(secret, f"{job_id}:{expires_at}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def verify(job_id: str, expires_at: int, signature: str, secret: bytes, now: datetime) -> bool:
    """True when the signature matches this job and expiry and the expiry is still ahead."""
    try:
        received = signature.encode("ascii")
    except UnicodeEncodeError:
        return False
    expected = sign(job_id, expires_at, secret).encode("ascii")
    matches = hmac.compare_digest(expected, received)
    return matches and expires_at > now.timestamp()
