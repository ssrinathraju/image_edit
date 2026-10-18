from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


class InvalidProviderToken(Exception):
    """Raised when a provider token fails any signature, issuer, audience, expiry or nonce check."""


class ProviderUnavailable(Exception):
    """Raised when a provider's signing keys cannot be fetched to check a token."""


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    subject: str
    email: Optional[str]
    email_verified: bool
    issued_at: datetime


class IdentityVerifier(Protocol):
    def verify(self, token: str, *, nonce: Optional[str] = None) -> ProviderIdentity:
        """Check a provider token fully and return the identity it proves.

        Raises InvalidProviderToken for a bad token and ProviderUnavailable when
        the provider's keys cannot be reached.
        """
        ...
