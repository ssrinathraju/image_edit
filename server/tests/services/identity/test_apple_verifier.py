import hashlib
import json
import time

import jwt
import pytest

from image_edit_server.core.identity_verifier import (
    InvalidProviderToken,
    ProviderUnavailable,
)
from image_edit_server.services.identity.apple_verifier import AppleVerifier
from tests.helpers import (
    APPLE_BUNDLE,
    MISSING,
    TEST_KID,
    FakeJwksClient,
    apple_claims,
    make_rsa_key,
    sign_token,
)

NONCE = "raw-nonce"


@pytest.fixture(scope="module")
def key():
    return make_rsa_key()


@pytest.fixture
def jwks(key) -> FakeJwksClient:
    return FakeJwksClient({TEST_KID: key})


@pytest.fixture
def verifier(jwks) -> AppleVerifier:
    return AppleVerifier(APPLE_BUNDLE, jwks)


def test_valid_token_yields_the_identity(verifier, key):
    identity = verifier.verify(sign_token(key, apple_claims()), nonce=NONCE)

    assert (identity.provider, identity.subject) == ("apple", "a-1")
    assert identity.email == "ana@example.com"
    assert identity.email_verified is True


def test_token_without_an_email_has_none(verifier, key):
    identity = verifier.verify(sign_token(key, apple_claims(email=None)), nonce=NONCE)

    assert identity.email is None


def test_nonce_must_match_the_digest_in_the_token(verifier, key):
    assert hashlib.sha256(NONCE.encode()).hexdigest() != NONCE
    token = sign_token(key, apple_claims())

    with pytest.raises(InvalidProviderToken):
        verifier.verify(token, nonce="a-different-nonce")


def test_missing_nonce_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims()), nonce=None)


def test_token_without_a_nonce_claim_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims(raw_nonce=None)), nonce=NONCE)


def test_raw_nonce_sent_in_place_of_its_digest_is_rejected(verifier, key):
    claims = apple_claims(nonce=NONCE)

    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, claims), nonce=NONCE)


def test_non_ascii_nonce_claim_is_rejected_not_an_error(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims(nonce="é")), nonce=NONCE)


def test_wrong_audience_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims(aud="com.other.app")), nonce=NONCE)


def test_wrong_issuer_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims(iss="https://evil.example")), nonce=NONCE)


def test_expired_token_is_rejected(verifier, key):
    expired = apple_claims(exp=int(time.time()) - 120)

    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, expired), nonce=NONCE)


def test_token_expired_within_the_leeway_is_accepted(verifier, key):
    just_expired = apple_claims(exp=int(time.time()) - 30)

    assert verifier.verify(sign_token(key, just_expired), nonce=NONCE)


def test_bad_signature_is_rejected(verifier):
    forged = sign_token(make_rsa_key(), apple_claims())

    with pytest.raises(InvalidProviderToken):
        verifier.verify(forged, nonce=NONCE)


def test_unknown_kid_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, apple_claims(), kid="other"), nonce=NONCE)


def test_alg_none_is_rejected(verifier):
    unsigned = jwt.encode(apple_claims(), None, algorithm="none", headers={"kid": TEST_KID})

    with pytest.raises(InvalidProviderToken):
        verifier.verify(unsigned, nonce=NONCE)


def test_hs256_token_is_rejected(verifier):
    symmetric = jwt.encode(
        apple_claims(), "x" * 64, algorithm="HS256", headers={"kid": TEST_KID}
    )

    with pytest.raises(InvalidProviderToken):
        verifier.verify(symmetric, nonce=NONCE)


def test_unreachable_keys_raise_provider_unavailable(verifier, jwks, key):
    jwks.unreachable = True

    with pytest.raises(ProviderUnavailable):
        verifier.verify(sign_token(key, apple_claims()), nonce=NONCE)


@pytest.mark.parametrize(
    "claim,expected",
    [("true", True), (True, True), (MISSING, False), (False, False), ("false", False),
     ("True", False), (1, False)],
)
def test_email_verified_is_true_only_for_boolean_true_or_the_string_true(
    verifier, key, claim, expected
):
    token = sign_token(key, apple_claims(email_verified=claim))

    assert verifier.verify(token, nonce=NONCE).email_verified is expected


@pytest.mark.parametrize(
    "error",
    [
        json.JSONDecodeError("Expecting value", "<html>", 0),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        jwt.PyJWKSetError("The JWK Set did not contain any keys"),
        jwt.PyJWKClientError("The JWKS endpoint did not return a JSON object"),
        jwt.PyJWKClientError("The JWKS endpoint did not contain any signing keys"),
    ],
)
def test_a_broken_key_endpoint_is_provider_unavailable_not_a_rejected_token(
    verifier, jwks, key, error
):
    jwks.error = error

    with pytest.raises(ProviderUnavailable):
        verifier.verify(sign_token(key, apple_claims()), nonce=NONCE)
