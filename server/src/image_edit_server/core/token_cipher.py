from __future__ import annotations

import base64
import binascii
import os
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16
VERSION_PREFIX = "v1:"


class TokenCipher:
    """AES-256-GCM for secrets stored at rest, bound to the account that owns them."""

    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise ValueError(f"token encryption key must be {KEY_BYTES} bytes, got {len(key)}")
        self._aead = AESGCM(key)

    @classmethod
    def from_encoded_key(cls, encoded: str) -> "TokenCipher":
        """Build from a standard or URL-safe base64 key; the error never echoes the key."""
        text = encoded.strip().replace("-", "+").replace("_", "/")
        try:
            key = base64.b64decode(text + "=" * (-len(text) % 4), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("is not valid base64") from None
        if len(key) != KEY_BYTES:
            raise ValueError(f"must decode to {KEY_BYTES} bytes, got {len(key)}")
        return cls(key)

    def encrypt(self, token: str, account_id: str) -> str:
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, token.encode(), account_id.encode())
        return VERSION_PREFIX + base64.urlsafe_b64encode(nonce + sealed).decode()

    def decrypt(self, value: str, account_id: str) -> Optional[str]:
        """The original token, or None for any value this key and account cannot open."""
        if not value.startswith(VERSION_PREFIX):
            return None
        try:
            raw = base64.urlsafe_b64decode(value[len(VERSION_PREFIX):].encode())
        except (binascii.Error, ValueError):
            return None
        if len(raw) < NONCE_BYTES + TAG_BYTES:
            return None
        try:
            plain = self._aead.decrypt(raw[:NONCE_BYTES], raw[NONCE_BYTES:], account_id.encode())
            return plain.decode()
        except (InvalidTag, UnicodeDecodeError):
            return None

