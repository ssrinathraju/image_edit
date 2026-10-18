import json

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from image_edit_server.configs.settings import Settings
from image_edit_server.services.apple_revocation import (
    APPLE_REVOKE_URL,
    APPLE_TOKEN_URL,
    AppleRevocationClient,
)

SECRET_CODE = "authcode-secret-text"
SECRET_TOKEN = "refresh-secret-text"


@pytest.fixture(scope="module")
def ec_key():
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def settings(tmp_path, ec_key) -> Settings:
    key_file = tmp_path / "AuthKey.p8"
    key_file.write_bytes(
        ec_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return Settings(
        APPLE_BUNDLE_ID="com.example.app",
        APPLE_TEAM_ID="TEAM123",
        APPLE_KEY_ID="KEY456",
        APPLE_PRIVATE_KEY_PATH=str(key_file),
    )


class FakePost:
    def __init__(self, status=200, body="{}", error=None) -> None:
        self.status, self.body, self.error = status, body, error
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, form):
        self.calls.append((url, form))
        if self.error:
            raise self.error
        return self.status, self.body


def _client(settings, post) -> AppleRevocationClient:
    return AppleRevocationClient(settings, post, clock=lambda: 1_000_000.0)


def test_client_secret_has_apple_claims_and_header_and_verifies(settings, ec_key):
    secret = _client(settings, FakePost()).build_client_secret()

    header = jwt.get_unverified_header(secret)
    claims = jwt.decode(
        secret,
        ec_key.public_key(),
        algorithms=["ES256"],
        audience="https://appleid.apple.com",
        options={"verify_exp": False, "verify_iat": False},
    )
    assert (header["alg"], header["kid"]) == ("ES256", "KEY456")
    assert claims["iss"] == "TEAM123"
    assert claims["sub"] == "com.example.app"
    assert claims["exp"] - claims["iat"] == 300


def test_successful_exchange_returns_the_refresh_token_and_posts_the_right_form(settings):
    post = FakePost(body=json.dumps({"refresh_token": SECRET_TOKEN, "access_token": "x"}))

    token = _client(settings, post).exchange_code(SECRET_CODE)

    assert token == SECRET_TOKEN
    url, form = post.calls[0]
    assert url == APPLE_TOKEN_URL
    assert form["code"] == SECRET_CODE
    assert form["grant_type"] == "authorization_code"
    assert form["client_id"] == "com.example.app"
    assert form["client_secret"]


def test_a_non_200_exchange_returns_none_and_logs_without_the_code(settings, caplog):
    post = FakePost(status=400, body='{"error": "invalid_grant"}')

    with caplog.at_level("INFO"):
        token = _client(settings, post).exchange_code(SECRET_CODE)

    assert token is None
    assert "400" in caplog.text
    assert SECRET_CODE not in caplog.text


def test_a_raising_post_returns_none_and_logs_without_the_code(settings, caplog):
    post = FakePost(error=OSError(f"boom {SECRET_CODE}"))

    with caplog.at_level("INFO"):
        token = _client(settings, post).exchange_code(SECRET_CODE)

    assert token is None
    assert "OSError" in caplog.text
    assert SECRET_CODE not in caplog.text


def test_a_200_without_a_refresh_token_returns_none(settings):
    assert _client(settings, FakePost(body="{}")).exchange_code(SECRET_CODE) is None
    assert _client(settings, FakePost(body="not json")).exchange_code(SECRET_CODE) is None


def test_revoke_sends_the_refresh_token_form(settings):
    post = FakePost()

    _client(settings, post).revoke(SECRET_TOKEN)

    url, form = post.calls[0]
    assert url == APPLE_REVOKE_URL
    assert form["token"] == SECRET_TOKEN
    assert form["token_type_hint"] == "refresh_token"
    assert form["client_id"] == "com.example.app"


def test_a_raising_post_in_revoke_is_logged_and_not_raised(settings, caplog):
    post = FakePost(error=RuntimeError(f"boom {SECRET_TOKEN}"))

    with caplog.at_level("INFO"):
        _client(settings, post).revoke(SECRET_TOKEN)

    assert "RuntimeError" in caplog.text
    assert SECRET_TOKEN not in caplog.text


def test_a_failing_revoke_status_is_logged_without_the_token(settings, caplog):
    with caplog.at_level("INFO"):
        _client(settings, FakePost(status=500)).revoke(SECRET_TOKEN)

    assert "500" in caplog.text
    assert SECRET_TOKEN not in caplog.text


def test_a_key_file_that_cannot_be_parsed_makes_the_exchange_return_none_not_raise(
    settings, caplog
):
    post = FakePost()
    client = _client(settings, post)
    client._private_key = "not a pem key"

    with caplog.at_level("WARNING"):
        token = client.exchange_code(SECRET_CODE)

    assert token is None
    assert post.calls == []
    assert SECRET_CODE not in caplog.text
    assert "Apple code exchange failed" in caplog.text


def test_a_key_file_that_cannot_be_parsed_makes_revoke_log_not_raise(settings, caplog):
    post = FakePost()
    client = _client(settings, post)
    client._private_key = "not a pem key"

    with caplog.at_level("WARNING"):
        client.revoke(SECRET_TOKEN)

    assert post.calls == []
    assert SECRET_TOKEN not in caplog.text
    assert "Apple revocation failed" in caplog.text
