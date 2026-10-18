from __future__ import annotations

import json
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
# An unknown key ID forces at most one JWKS refetch per this many seconds, so
# anyone posting random key IDs cannot make the server hammer the provider.
JWKS_REFRESH_COOLDOWN_SECONDS = 30
UNKNOWN_KEY_MESSAGE = "Unable to find a signing key"


class JwksClient(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


def make_jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(
        url,
        timeout=JWKS_FETCH_TIMEOUT_SECONDS,
        cooldown_duration=JWKS_REFRESH_COOLDOWN_SECONDS,
    )


def is_email_verified_claim(value: object) -> bool:
    """True only for the boolean true or the string "true" (Apple sends a string)."""
    return value is True or value == "true"


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
    signing_key = _fetch_signing_key(token, jwks_client)
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


def _fetch_signing_key(token: str, jwks_client: JwksClient) -> Any:
    try:
        return jwks_client.get_signing_key_from_jwt(token)
    except jwt.PyJWKClientError as error:
        if UNKNOWN_KEY_MESSAGE in str(error):
            logger.info("Provider token rejected: %s", type(error).__name__)
            raise InvalidProviderToken("no matching signing key") from error
        # Connection failures, a body that is not a key set, a set with no keys:
        # the provider's side is broken, not the caller's token.
        _raise_unavailable(error)
    except (jwt.PyJWKSetError, json.JSONDecodeError, UnicodeDecodeError) as error:
        _raise_unavailable(error)
    except jwt.PyJWTError as error:
        logger.info("Provider token rejected: %s", type(error).__name__)
        raise InvalidProviderToken("malformed token") from error


def _raise_unavailable(error: Exception) -> None:
    logger.warning("Provider keys unusable: %s", type(error).__name__)
    raise ProviderUnavailable("provider signing keys could not be fetched") from error


def _log_rejected_audience(token: str) -> None:
    # Reached only after the signature verified, so the claim is the issuer's own word.
    audience = jwt.decode(token, options={"verify_signature": False}).get("aud")
    logger.warning("Provider token rejected: audience %r is not configured", audience)
