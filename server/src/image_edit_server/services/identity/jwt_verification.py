from __future__ import annotations

import logging
from typing import Any, Container, Protocol

import jwt

from image_edit_server.core.identity_verifier import (
    InvalidProviderToken,
    ProviderUnavailable,
)

logger = logging.getLogger(__name__)

ALLOWED_ALGORITHMS = ["RS256"]
CLOCK_LEEWAY_SECONDS = 60
JWKS_FETCH_TIMEOUT_SECONDS = 5
REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud", "sub"]


class JwksClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


def make_jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, timeout=JWKS_FETCH_TIMEOUT_SECONDS)


def decode_provider_token(
    token: str,
    jwks_client: JwksClient,
    *,
    audience: Container[str],
    issuers: list[str],
) -> dict:
    """Verify signature, issuer, audience and expiry; returns the claims.

    Only the failure class is logged, never the token text.
    """
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as error:
        logger.warning("Provider keys unreachable: %s", type(error).__name__)
        raise ProviderUnavailable("provider signing keys could not be fetched") from error
    except jwt.PyJWTError as error:
        logger.info("Provider token rejected: %s", type(error).__name__)
        raise InvalidProviderToken("no matching signing key") from error
    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALLOWED_ALGORITHMS,
            audience=list(audience),
            issuer=issuers,
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.InvalidAudienceError as error:
        _log_rejected_audience(token)
        raise InvalidProviderToken("audience not accepted") from error
    except jwt.PyJWTError as error:
        logger.info("Provider token rejected: %s", type(error).__name__)
        raise InvalidProviderToken(type(error).__name__) from error


def _log_rejected_audience(token: str) -> None:
    # Reached only after the signature verified, so the claim is the issuer's own word.
    audience = jwt.decode(token, options={"verify_signature": False}).get("aud")
    logger.warning("Provider token rejected: audience %r is not configured", audience)
