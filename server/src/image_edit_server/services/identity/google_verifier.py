from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.services.identity.jwt_verification import (
    JwksClient,
    decode_provider_token,
    is_email_verified_claim,
    make_jwks_client,
)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]
PROVIDER = "google"


class GoogleVerifier:
    def __init__(
        self, client_ids: list[str], jwks_client: Optional[JwksClient] = None
    ) -> None:
        self._client_ids = client_ids
        self._jwks = jwks_client or make_jwks_client(GOOGLE_JWKS_URL)

    def verify(self, token: str, *, nonce: Optional[str] = None) -> ProviderIdentity:
        claims = decode_provider_token(
            token, self._jwks, audience=self._client_ids, issuers=GOOGLE_ISSUERS
        )
        return ProviderIdentity(
            provider=PROVIDER,
            subject=str(claims["sub"]),
            email=claims.get("email") or None,
            email_verified=is_email_verified_claim(claims.get("email_verified")),
            issued_at=datetime.fromtimestamp(claims["iat"], tz=timezone.utc),
        )
