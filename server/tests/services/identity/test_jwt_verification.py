import io
import json

import jwt
import pytest
from jwt.algorithms import RSAAlgorithm

from image_edit_server.core.identity_verifier import InvalidProviderToken
from image_edit_server.services.identity.google_verifier import GoogleVerifier
from image_edit_server.services.identity.jwt_verification import (
    JWKS_REFRESH_COOLDOWN_SECONDS,
    is_email_verified_claim,
    make_jwks_client,
)
from tests.helpers import GOOGLE_AUDIENCE, TEST_KID, google_claims, make_rsa_key, sign_token


class CountingOpener:
    """Stands in for urllib's opener: serves one key set and counts the fetches."""

    def __init__(self, body: dict) -> None:
        self._body = json.dumps(body).encode()
        self.fetches = 0

    def open(self, request, timeout=None):
        self.fetches += 1
        return io.BytesIO(self._body)


@pytest.fixture
def key():
    return make_rsa_key()


@pytest.fixture
def opener(key, monkeypatch) -> CountingOpener:
    jwk = json.loads(RSAAlgorithm.to_jwk(key.public_key()))
    opener = CountingOpener({"keys": [{**jwk, "kid": TEST_KID, "use": "sig"}]})
    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: opener)
    return opener


def test_the_key_client_uses_the_refresh_cooldown():
    client = make_jwks_client("https://keys.example.test/certs")

    assert client.cooldown_duration == JWKS_REFRESH_COOLDOWN_SECONDS > 0


def test_random_key_ids_do_not_make_the_server_refetch_the_keys_each_time(key, opener):
    verifier = GoogleVerifier([GOOGLE_AUDIENCE], make_jwks_client("https://keys.example.test/c"))

    for i in range(5):
        with pytest.raises(InvalidProviderToken):
            verifier.verify(sign_token(key, google_claims(), kid=f"random-{i}"))

    assert opener.fetches == 1
    assert verifier.verify(sign_token(key, google_claims())).provider == "google"
    assert opener.fetches == 1


@pytest.mark.parametrize(
    "value,expected",
    [(True, True), ("true", True), (False, False), ("false", False), ("True", False),
     (1, False), (None, False), ("", False)],
)
def test_only_boolean_true_and_the_string_true_count_as_verified(value, expected):
    assert is_email_verified_claim(value) is expected
