import time

import pytest

from image_edit_server.core.identity_verifier import ProviderUnavailable
from image_edit_server.services.identity.apple_verifier import AppleVerifier
from image_edit_server.services.identity.google_verifier import GoogleVerifier
from tests.api.test_generations_submit import VALID_PROMPT, _face
from tests.helpers import (
    APPLE_BUNDLE,
    GOOGLE_AUDIENCE,
    TEST_KID,
    FakeJwksClient,
    MISSING,
    apple_claims,
    google_claims,
    make_rsa_key,
    sign_token,
)

APPLE_SECRET_CODE = "apple-auth-code-secret"


def _google(client, token="g-tok"):
    return client.post("/auth/oauth/google", json={"id_token": token})


def _apple(client, token="a-tok", nonce="raw-nonce", code=APPLE_SECRET_CODE):
    return client.post(
        "/auth/oauth/apple",
        json={"identity_token": token, "nonce": nonce, "authorization_code": code},
    )


def _bearer(resp) -> dict:
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _user_count(user_store) -> int:
    return user_store._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


# ── Sign in with Google ─────────────────────────────────────────────────


def test_linked_google_identity_signs_in_with_a_working_token(
    anon_client, google_verifier
):
    google_verifier.add("g-tok", "g-1")
    first = _google(anon_client)

    resp = _google(anon_client)

    assert resp.status_code == 200
    assert resp.json()["created"] is False
    assert resp.json()["id"] == first.json()["id"]
    assert anon_client.get("/me", headers=_bearer(resp)).status_code == 200


def test_response_shape_has_the_session_fields_and_created(anon_client, google_verifier):
    google_verifier.add("g-tok", "g-1")

    body = _google(anon_client).json()

    assert set(body) == {"token", "id", "email", "created"}
    assert body["created"] is True


@pytest.fixture
def real_verifiers(verifiers):
    """Swap in the real verifiers over a local key, so token checks run end to end."""
    key = make_rsa_key()
    jwks = FakeJwksClient({TEST_KID: key})
    verifiers["google"] = GoogleVerifier([GOOGLE_AUDIENCE], jwks)
    verifiers["apple"] = AppleVerifier(APPLE_BUNDLE, jwks)
    return key


def test_valid_real_google_token_signs_in(anon_client, real_verifiers, user_store):
    resp = _google(anon_client, sign_token(real_verifiers, google_claims()))

    assert resp.status_code == 200
    assert _user_count(user_store) == 1


def test_wrong_audience_is_401_and_creates_nothing(anon_client, real_verifiers, user_store):
    token = sign_token(real_verifiers, google_claims(aud="not-configured.apps"))

    resp = _google(anon_client, token)

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "invalid_provider_token"
    assert _user_count(user_store) == 0


def test_expired_and_forged_tokens_are_401_and_create_nothing(
    anon_client, real_verifiers, user_store
):
    expired = sign_token(real_verifiers, google_claims(exp=int(time.time()) - 600))
    forged = sign_token(make_rsa_key(), google_claims())

    for token in (expired, forged):
        resp = _google(anon_client, token)
        assert resp.status_code == 401
        assert resp.json()["detail"]["error"] == "invalid_provider_token"
    assert _user_count(user_store) == 0


# ── Sign in with Apple ──────────────────────────────────────────────────


def test_valid_real_apple_token_with_matching_nonce_signs_in(anon_client, real_verifiers):
    token = sign_token(real_verifiers, apple_claims())

    resp = _apple(anon_client, token)

    assert resp.status_code == 200
    assert resp.json()["token"]


def test_nonce_mismatch_is_401(anon_client, real_verifiers, user_store):
    token = sign_token(real_verifiers, apple_claims())

    resp = _apple(anon_client, token, nonce="a-different-nonce")

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "invalid_provider_token"
    assert _user_count(user_store) == 0


def test_apple_receives_the_raw_nonce(anon_client, apple_verifier):
    apple_verifier.add("a-tok", "a-1")

    _apple(anon_client, nonce="my-raw-nonce")

    assert apple_verifier.calls == [("a-tok", "my-raw-nonce")]


# ── Find, link, or create the account ───────────────────────────────────


def test_existing_password_account_is_linked_by_email(client, google_verifier, user_id):
    google_verifier.add("g-tok", "g-1", email="Ana@Example.com")

    resp = _google(client)

    assert resp.status_code == 200
    assert (resp.json()["id"], resp.json()["created"]) == (user_id, False)
    me = client.get("/me", headers=_bearer(resp)).json()
    assert me["providers"] == ["google"]
    assert me["has_password"] is True


def test_new_identity_with_a_new_email_creates_an_account(anon_client, google_verifier):
    google_verifier.add("g-tok", "g-1", email="new@example.com")

    resp = _google(anon_client)

    assert (resp.json()["email"], resp.json()["created"]) == ("new@example.com", True)


def test_changed_provider_email_does_not_move_the_account(anon_client, google_verifier):
    google_verifier.add("g-tok", "g-1", email="ana@example.com")
    first = _google(anon_client)
    google_verifier.add("g-tok-2", "g-1", email="different@example.com")

    resp = _google(anon_client, "g-tok-2")

    assert resp.json()["id"] == first.json()["id"]
    assert resp.json()["email"] == "ana@example.com"
    me = anon_client.get("/me", headers=_bearer(resp)).json()
    assert me["email"] == "ana@example.com"


def test_apple_relay_email_becomes_the_account_email(anon_client, apple_verifier):
    relay = "x1y2@privaterelay.appleid.com"
    apple_verifier.add("a-tok", "a-1", email=relay)

    resp = _apple(anon_client)

    assert (resp.json()["email"], resp.json()["created"]) == (relay, True)


# ── Accounts reached through a provider are verified ────────────────────


def test_new_provider_account_is_passwordless_and_can_generate(
    anon_client, google_verifier
):
    google_verifier.add("g-tok", "g-1")
    headers = _bearer(_google(anon_client))

    me = anon_client.get("/me", headers=headers).json()
    submit = anon_client.post(
        "/generations", data={"prompt": VALID_PROMPT}, files=[_face()], headers=headers
    )

    assert me["has_password"] is False
    assert submit.status_code == 202


def test_linking_leaves_password_login_working(client, google_verifier):
    google_verifier.add("g-tok", "g-1", email="ana@example.com")
    resp = _google(client)

    login = client.post(
        "/auth/login",
        json={"email": "ana@example.com", "password": "correct horse battery"},
    )

    assert resp.status_code == 200
    assert login.status_code == 200
    assert login.json()["id"] == resp.json()["id"]


# ── Require a provider-verified email ───────────────────────────────────


def test_unverified_google_email_is_400_and_writes_nothing(
    client, google_verifier, user_store
):
    google_verifier.add("g-tok", "g-1", email="ana@example.com", verified=False)
    users_before = _user_count(user_store)

    resp = _google(client)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "provider_email_unverified"
    assert _user_count(user_store) == users_before
    assert user_store.list_providers(user_store.get_by_email("ana@example.com").id) == []


@pytest.mark.parametrize("claim", [MISSING, False, "false", "True", 1, "yes"])
def test_apple_email_without_a_verified_claim_is_refused_and_writes_nothing(
    anon_client, real_verifiers, user_store, claim
):
    token = sign_token(real_verifiers, apple_claims(email_verified=claim))

    resp = _apple(anon_client, token)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "provider_email_unverified"
    assert "apple" in resp.json()["detail"]["detail"]
    assert _user_count(user_store) == 0
    assert user_store._conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0


@pytest.mark.parametrize("claim", ["true", True])
def test_apple_true_claim_in_either_form_creates_an_account(
    anon_client, real_verifiers, user_store, claim
):
    token = sign_token(real_verifiers, apple_claims(email_verified=claim))

    resp = _apple(anon_client, token)

    assert (resp.status_code, resp.json()["created"]) == (200, True)
    assert _user_count(user_store) == 1


def test_an_unverified_apple_email_does_not_link_to_a_password_account(
    client, real_verifiers, user_store
):
    token = sign_token(real_verifiers, apple_claims(email_verified="false"))

    resp = _apple(client, token)

    assert resp.status_code == 400
    assert user_store.list_providers(user_store.get_by_email("ana@example.com").id) == []


def test_apple_token_without_an_email_for_an_unknown_identity_is_400(
    anon_client, apple_verifier
):
    apple_verifier.add("a-tok", "a-1", email=None)

    resp = _apple(anon_client)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "provider_email_missing"


# ── Refuse unconfigured providers, report unreachable ones ──────────────


def test_unconfigured_google_is_503(anon_client, verifiers):
    del verifiers["google"]

    resp = _google(anon_client)

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "provider_not_configured"


def test_unconfigured_apple_is_503(anon_client, verifiers):
    del verifiers["apple"]

    resp = _apple(anon_client)

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "provider_not_configured"


def test_unreachable_google_keys_are_503_and_create_nothing(
    anon_client, google_verifier, user_store
):
    google_verifier.fail_with("g-tok", ProviderUnavailable("down"))

    resp = _google(anon_client)

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "provider_unavailable"
    assert _user_count(user_store) == 0


def test_unreachable_keys_through_the_real_verifier_are_503(
    anon_client, real_verifiers, verifiers, user_store
):
    token = sign_token(real_verifiers, google_claims())
    verifiers["google"]._jwks.unreachable = True

    resp = _google(anon_client, token)

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "provider_unavailable"
    assert _user_count(user_store) == 0


# ── One identity per provider per account ───────────────────────────────


def test_second_google_identity_for_the_same_account_is_409(client, google_verifier):
    google_verifier.add("g-tok-1", "g-1", email="ana@example.com")
    google_verifier.add("g-tok-2", "g-2", email="ana@example.com")
    assert _google(client, "g-tok-1").status_code == 200

    resp = _google(client, "g-tok-2")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "provider_already_linked"


# ── Apple authorization code and refresh token ──────────────────────────


def test_apple_sign_in_stores_the_refresh_token_from_the_exchange(
    anon_client, apple_verifier, apple_client, user_store
):
    apple_verifier.add("a-tok", "a-1")

    resp = _apple(anon_client)

    assert apple_client.exchanged == [APPLE_SECRET_CODE]
    assert user_store.get_apple_refresh_token(resp.json()["id"]) == "apple-refresh-1"


def test_a_failed_exchange_still_signs_in_and_is_retried_next_time(
    anon_client, apple_verifier, apple_client, user_store
):
    apple_verifier.add("a-tok", "a-1")
    apple_client.refresh_token = None
    first = _apple(anon_client)
    assert first.status_code == 200
    assert user_store.get_apple_refresh_token(first.json()["id"]) is None

    apple_client.refresh_token = "apple-refresh-2"
    second = _apple(anon_client, code="second-code")

    assert apple_client.exchanged == [APPLE_SECRET_CODE, "second-code"]
    assert user_store.get_apple_refresh_token(second.json()["id"]) == "apple-refresh-2"


def test_a_stored_token_is_not_exchanged_again(anon_client, apple_verifier, apple_client):
    apple_verifier.add("a-tok", "a-1")
    _apple(anon_client)

    _apple(anon_client, code="second-code")

    assert apple_client.exchanged == [APPLE_SECRET_CODE]


def test_google_sign_in_never_exchanges_an_apple_code(
    anon_client, google_verifier, apple_client
):
    google_verifier.add("g-tok", "g-1")

    _google(anon_client)

    assert apple_client.exchanged == []


# ── Keep provider tokens secret ─────────────────────────────────────────


def test_tokens_codes_and_refresh_tokens_are_never_logged_or_returned(
    anon_client, apple_client, real_verifiers, caplog
):
    good = sign_token(real_verifiers, apple_claims())
    bad = sign_token(make_rsa_key(), apple_claims())

    with caplog.at_level("DEBUG"):
        ok = _apple(anon_client, good)
        rejected = _apple(anon_client, bad)
        _apple(anon_client, good, nonce="wrong")

    assert ok.status_code == 200 and rejected.status_code == 401
    for secret in (good, bad, APPLE_SECRET_CODE, "apple-refresh-1"):
        assert secret not in caplog.text
        assert secret not in ok.text
        assert secret not in rejected.text
