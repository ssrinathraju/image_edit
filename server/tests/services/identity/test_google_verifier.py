import json
import time

import jwt
import pytest

from image_edit_server.core.identity_verifier import (
    InvalidProviderToken,
    ProviderUnavailable,
)
from image_edit_server.services.identity.google_verifier import GoogleVerifier
from tests.helpers import (
    GOOGLE_AUDIENCE,
    TEST_KID,
    FakeJwksClient,
    google_claims,
    make_rsa_key,
    sign_token,
)


@pytest.fixture(scope="module")
def key():
    return make_rsa_key()


@pytest.fixture
def jwks(key) -> FakeJwksClient:
    return FakeJwksClient({TEST_KID: key})


@pytest.fixture
def verifier(jwks) -> GoogleVerifier:
    return GoogleVerifier([GOOGLE_AUDIENCE, "ios.apps.example"], jwks)


def test_valid_token_yields_the_identity(verifier, key):
    identity = verifier.verify(sign_token(key, google_claims(subject="g-9")))

    assert (identity.provider, identity.subject) == ("google", "g-9")
    assert identity.email == "ana@example.com"
    assert identity.email_verified is True
    assert abs(identity.issued_at.timestamp() - time.time()) < 5


@pytest.mark.parametrize("issuer", ["accounts.google.com", "https://accounts.google.com"])
def test_both_google_issuer_forms_are_accepted(verifier, key, issuer):
    assert verifier.verify(sign_token(key, google_claims(iss=issuer)))


def test_unverified_email_is_reported_not_rejected(verifier, key):
    identity = verifier.verify(sign_token(key, google_claims(email_verified=False)))

    assert identity.email_verified is False


def test_any_configured_client_id_is_an_accepted_audience(verifier, key):
    assert verifier.verify(sign_token(key, google_claims(aud="ios.apps.example")))


def test_wrong_audience_is_rejected_and_logged_without_the_token(verifier, key, caplog):
    token = sign_token(key, google_claims(aud="someone-else.apps"))

    with caplog.at_level("INFO"), pytest.raises(InvalidProviderToken):
        verifier.verify(token)

    assert "someone-else.apps" in caplog.text
    assert token not in caplog.text


def test_wrong_issuer_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, google_claims(iss="https://evil.example")))


def test_expired_token_is_rejected(verifier, key):
    expired = google_claims(exp=int(time.time()) - 120)

    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, expired))


def test_token_expired_within_the_leeway_is_accepted(verifier, key):
    just_expired = google_claims(exp=int(time.time()) - 30)

    assert verifier.verify(sign_token(key, just_expired))


def test_token_issued_in_the_future_beyond_the_leeway_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, google_claims(iat=int(time.time()) + 300)))


def test_bad_signature_is_rejected(verifier):
    forged = sign_token(make_rsa_key(), google_claims())

    with pytest.raises(InvalidProviderToken):
        verifier.verify(forged)


def test_unknown_kid_is_rejected(verifier, key):
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, google_claims(), kid="other"))


def test_alg_none_is_rejected(verifier):
    unsigned = jwt.encode(google_claims(), None, algorithm="none", headers={"kid": TEST_KID})

    with pytest.raises(InvalidProviderToken):
        verifier.verify(unsigned)


def test_hs256_token_is_rejected(verifier):
    symmetric = jwt.encode(
        google_claims(), "x" * 64, algorithm="HS256", headers={"kid": TEST_KID}
    )

    with pytest.raises(InvalidProviderToken):
        verifier.verify(symmetric)


def test_garbage_is_rejected(verifier):
    with pytest.raises(InvalidProviderToken):
        verifier.verify("not.a.jwt")


def test_missing_required_claim_is_rejected(verifier, key):
    claims = google_claims()
    del claims["sub"]

    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, claims))


def test_unreachable_keys_raise_provider_unavailable(verifier, jwks, key):
    jwks.unreachable = True

    with pytest.raises(ProviderUnavailable):
        verifier.verify(sign_token(key, google_claims()))


@pytest.mark.parametrize(
    "claim,expected",
    [(True, True), ("true", True), (False, False), ("false", False), (1, False)],
)
def test_email_verified_is_true_only_for_boolean_true_or_the_string_true(
    verifier, key, claim, expected
):
    token = sign_token(key, google_claims(email_verified=claim))

    assert verifier.verify(token).email_verified is expected


def test_a_key_endpoint_that_answers_with_a_non_json_body_is_provider_unavailable(
    verifier, jwks, key
):
    jwks.error = json.JSONDecodeError("Expecting value", "<html>", 0)

    with pytest.raises(ProviderUnavailable):
        verifier.verify(sign_token(key, google_claims()))


def test_a_key_set_with_no_keys_is_provider_unavailable_but_an_unknown_kid_is_rejected(
    verifier, jwks, key
):
    jwks.error = jwt.PyJWKClientError("The JWKS endpoint did not contain any signing keys")
    with pytest.raises(ProviderUnavailable):
        verifier.verify(sign_token(key, google_claims()))

    jwks.error = None
    with pytest.raises(InvalidProviderToken):
        verifier.verify(sign_token(key, google_claims(), kid="other"))
