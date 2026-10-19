import pytest


def _google_account(client, google_verifier, subject="g-1", email="gina@example.com"):
    google_verifier.add(f"tok-{subject}", subject, email=email)
    resp = client.post("/auth/oauth/google", json={"id_token": f"tok-{subject}", "date_of_birth": "1990-01-01"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _redeem(client, headers, code):
    return client.post("/me/referral", json={"code": code}, headers=headers)


@pytest.fixture
def friend_code(client) -> str:
    """The referral code of ana@example.com, a verified password account."""
    return client.get("/me").json()["referral"]["code"]


def _bonus(client, headers) -> int:
    return client.get("/me", headers=headers).json()["usage"]["bonus_credits"]


def test_new_provider_account_redeems_a_lowercase_code(
    client, anon_client, google_verifier, clock, friend_code
):
    headers = _google_account(anon_client, google_verifier)
    clock.advance(minutes=5)
    friend_before = _bonus(client, client.headers)

    resp = _redeem(anon_client, headers, f" {friend_code.lower()} ")

    assert resp.status_code == 200
    assert resp.json() == {}
    assert _bonus(anon_client, headers) == 5
    assert _bonus(client, client.headers) == friend_before + 5
    assert client.get("/me").json()["referral"]["rewards"] == 1


def test_second_redemption_is_409(client, anon_client, google_verifier, friend_code):
    headers = _google_account(anon_client, google_verifier)
    assert _redeem(anon_client, headers, friend_code).status_code == 200

    resp = _redeem(anon_client, headers, friend_code)

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "referral_not_allowed"
    assert _bonus(anon_client, headers) == 5


def test_password_registered_account_is_409(anon_client, second_user_headers, friend_code):
    resp = _redeem(anon_client, second_user_headers, friend_code)

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "referral_not_allowed"
    assert _bonus(anon_client, second_user_headers) == 0


def test_account_linked_to_google_but_created_with_a_password_is_409(
    client, google_verifier, friend_code
):
    google_verifier.add("tok", "g-9", email="ana@example.com")
    linked = client.post("/auth/oauth/google", json={"id_token": "tok", "date_of_birth": "1990-01-01"}).json()

    resp = client.post(
        "/me/referral",
        json={"code": friend_code},
        headers={"Authorization": f"Bearer {linked['token']}"},
    )

    assert resp.status_code == 409


def test_window_passed_is_409(client, anon_client, google_verifier, clock, friend_code):
    headers = _google_account(anon_client, google_verifier)
    clock.advance(hours=25)

    resp = _redeem(anon_client, headers, friend_code)

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "referral_not_allowed"
    assert _bonus(anon_client, headers) == 0


def test_own_or_unknown_code_is_400_and_changes_nothing(
    client, anon_client, google_verifier
):
    headers = _google_account(anon_client, google_verifier)
    own = anon_client.get("/me", headers=headers).json()["referral"]["code"]

    for code in (own, "ZZZZZZZZ"):
        resp = _redeem(anon_client, headers, code)
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_referral_code"
    assert _bonus(anon_client, headers) == 0


def test_referrer_cap_still_pays_the_new_account(
    client, anon_client, google_verifier, user_store, user_id, friend_code
):
    user_store._conn.execute(
        "UPDATE users SET referral_rewards = 10 WHERE id = ?", (user_id,)
    )
    user_store._conn.commit()
    headers = _google_account(anon_client, google_verifier)

    resp = _redeem(anon_client, headers, friend_code)

    assert resp.status_code == 200
    assert _bonus(anon_client, headers) == 5
    assert _bonus(client, client.headers) == 0


def test_redeeming_requires_a_session(anon_client, friend_code):
    assert anon_client.post("/me/referral", json={"code": friend_code}).status_code == 401
