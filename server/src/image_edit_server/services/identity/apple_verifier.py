from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional

from image_edit_server.core.identity_verifier import (
    InvalidProviderToken,
    ProviderIdentity,
)
from image_edit_server.services.identity.jwt_verification import (
    JwksClient,
    decode_provider_token,
    make_jwks_client,
)

logger = logging.getLogger(__name__)

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
PROVIDER = "apple"


class AppleVerifier:
    def __init__(
        self, bundle_id: str, jwks_client: Optional[JwksClient] = None
    ) -> None:
        self._bundle_id = bundle_id
        self._jwks = jwks_client or make_jwks_client(APPLE_JWKS_URL)

    def verify(self, token: str, *, nonce: Optional[str] = None) -> ProviderIdentity:
        claims = decode_provider_token(
            token, self._jwks, audience=[self._bundle_id], issuers=[APPLE_ISSUER]
        )
        self._check_nonce(claims.get("nonce"), nonce)
        return ProviderIdentity(
            provider=PROVIDER,
            subject=str(claims["sub"]),
            email=claims.get("email") or None,
            email_verified=claims.get("email_verified") in (True, "true"),
            issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        )

    @staticmethod
    def _check_nonce(claimed: object, raw_nonce: Optional[str]) -> None:
        if not raw_nonce or not isinstance(claimed, str):
            logger.info("Apple token rejected: nonce missing")
            raise InvalidProviderToken("nonce missing")
        expected = hashlib.sha256(raw_nonce.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(claimed.encode("utf-8"), expected.encode("utf-8")):
            logger.info("Apple token rejected: nonce mismatch")
            raise InvalidProviderToken("nonce mismatch")
