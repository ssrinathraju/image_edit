from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import jwt

from image_edit_server.configs.settings import Settings

logger = logging.getLogger(__name__)

APPLE_AUDIENCE = "https://appleid.apple.com"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_REVOKE_URL = "https://appleid.apple.com/auth/revoke"
CLIENT_SECRET_TTL_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 10
HTTP_OK = 200

Post = Callable[[str, dict[str, str]], tuple[int, str]]


def post_form(url: str, form: dict[str, str]) -> tuple[int, str]:
    """POST a form with the standard library; an HTTP error status is returned, not raised."""
    request = urllib.request.Request(
        url, data=urllib.parse.urlencode(form).encode("ascii"), method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


class AppleRevocationClient:
    """Exchanges Apple authorization codes for refresh tokens and revokes them later."""

    def __init__(
        self,
        settings: Settings,
        post: Post = post_form,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._bundle_id = settings.APPLE_BUNDLE_ID
        self._team_id = settings.APPLE_TEAM_ID
        self._key_id = settings.APPLE_KEY_ID
        self._private_key = Path(settings.APPLE_PRIVATE_KEY_PATH).read_text()
        self._post = post
        self._clock = clock

    def build_client_secret(self) -> str:
        issued = int(self._clock())
        claims = {
            "iss": self._team_id,
            "iat": issued,
            "exp": issued + CLIENT_SECRET_TTL_SECONDS,
            "aud": APPLE_AUDIENCE,
            "sub": self._bundle_id,
        }
        return jwt.encode(
            claims, self._private_key, algorithm="ES256", headers={"kid": self._key_id}
        )

    def exchange_code(self, code: str) -> Optional[str]:
        """Trade an authorization code for a refresh token; None when Apple refuses or is down."""
        try:
            form = {
                "client_id": self._bundle_id,
                "client_secret": self.build_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
            }
            status, body = self._post(APPLE_TOKEN_URL, form)
            if status != HTTP_OK:
                logger.warning("Apple code exchange failed: HTTP %s", status)
                return None
            refresh_token = json.loads(body).get("refresh_token")
        except Exception as error:
            logger.warning("Apple code exchange failed: %s", type(error).__name__)
            return None
        if not refresh_token:
            logger.warning("Apple code exchange returned no refresh token")
            return None
        return str(refresh_token)

    def revoke(self, token: str) -> None:
        """Ask Apple to revoke a refresh token; every failure is logged and swallowed."""
        try:
            form = {
                "client_id": self._bundle_id,
                "client_secret": self.build_client_secret(),
                "token": token,
                "token_type_hint": "refresh_token",
            }
            status, _ = self._post(APPLE_REVOKE_URL, form)
        except Exception as error:
            logger.warning("Apple revocation failed: %s", type(error).__name__)
            return
        if status != HTTP_OK:
            logger.warning("Apple revocation failed: HTTP %s", status)
