from datetime import timedelta

import pytest

from tests.helpers import DEFAULT_PASSWORD


def _delete(client, headers=None, **body):
    return client.request("DELETE", "/me", json=body, headers=headers)


def _google_account(client, google_verifier, subject="g-1", email="gina@example.com"):
    google_verifier.add(f"signin-{subject}", subject, email=email)
    resp = client.post("/auth/oauth/google", json={"id_token": f"signin-{subject}", "date_of_birth": "1990-01-01"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _apple_account(client, apple_verifier, subject="a-1", email="ann@example.com"):
    apple_verifier.add(f"signin-{subject}", subject, email=email)
    resp = client.post(
        "/auth/oauth/apple",
        json={"identity_token": f"signin-{subject}", "nonce": "n", "authorization_code": "c", "date_of_birth": "1990-01-01"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _usable(client, headers) -> bool:
    return client.get("/me", headers=headers).status_code == 200


# ── password form ──


def test_password_account_still_deletes_with_its_password(client):
    assert _delete(client, password=DEFAULT_PASSWORD).status_code == 204
    assert client.get("/me").status_code == 401


def test_password_account_with_a_wrong_password_keeps_the_account(client):
    assert _delete(client, password="wrong password").status_code == 403
    assert client.get("/me").status_code == 200


# ── provider form ──


def test_google_only_account_deletes_with_a_fresh_token_and_can_sign_up_again(
    anon_client, google_verifier, clock
):
    headers = _google_account(anon_client, google_verifier)
    old_id = anon_client.get("/me", headers=headers).json()["id"]
    google_verifier.add("fresh", "g-1", issued_at=clock.now - timedelta(minutes=1))

    resp = _delete(anon_client, headers, provider="google", token="fresh")

    assert resp.status_code == 204
    assert not _usable(anon_client, headers)
    again = anon_client.post("/auth/oauth/google", json={"id_token": "signin-g-1", "date_of_birth": "1990-01-01"})
    assert again.json()["created"] is True
    assert again.json()["id"] != old_id


def test_a_ten_minute_old_token_is_403_and_keeps_the_account(
    anon_client, google_verifier, clock
):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("stale", "g-1", issued_at=clock.now - timedelta(minutes=10))

    resp = _delete(anon_client, headers, provider="google", token="stale")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "invalid_provider_token"
    assert _usable(anon_client, headers)


def test_a_token_just_inside_five_minutes_is_accepted(anon_client, google_verifier, clock):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("edge", "g-1", issued_at=clock.now - timedelta(minutes=4, seconds=59))

    assert _delete(anon_client, headers, provider="google", token="edge").status_code == 204


def test_another_identitys_token_is_403(anon_client, google_verifier, clock):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("theirs", "someone-else", issued_at=clock.now)

    resp = _delete(anon_client, headers, provider="google", token="theirs")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "invalid_provider_token"
    assert _usable(anon_client, headers)


def test_a_rejected_token_is_403(anon_client, google_verifier):
    headers = _google_account(anon_client, google_verifier)

    resp = _delete(anon_client, headers, provider="google", token="never-registered")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "invalid_provider_token"


def test_a_password_on_a_provider_only_account_is_403(anon_client, google_verifier):
    headers = _google_account(anon_client, google_verifier)

    for password in ("anything at all", "not-a-real-password", ""):
        assert _delete(anon_client, headers, password=password).status_code == 403
    assert _usable(anon_client, headers)


def test_a_google_token_cannot_confirm_for_an_account_linked_only_to_apple(
    anon_client, apple_verifier, google_verifier, clock
):
    headers = _apple_account(anon_client, apple_verifier)
    google_verifier.add("g", "g-1", email="ann@example.com", issued_at=clock.now)

    resp = _delete(anon_client, headers, provider="google", token="g")

    assert resp.status_code == 403
    assert _usable(anon_client, headers)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"provider": "google"},
        {"token": "t"},
        {"provider": "google", "token": "t", "password": "x"},
        {"provider": "twitter", "token": "t"},
    ],
)
def test_a_request_with_neither_or_both_forms_is_422(client, body):
    assert _delete(client, **body).status_code == 422
    assert client.get("/me").status_code == 200


# ── Apple revocation ──


def test_deleting_an_apple_account_revokes_its_stored_token(
    anon_client, apple_verifier, apple_client, clock
):
    headers = _apple_account(anon_client, apple_verifier)
    apple_verifier.add("fresh", "a-1", email="ann@example.com", issued_at=clock.now)

    resp = _delete(anon_client, headers, provider="apple", token="fresh", nonce="n")

    assert resp.status_code == 204
    assert apple_client.revoked == ["apple-refresh-1"]
    assert apple_verifier.calls[-1] == ("fresh", "n")


def test_a_failing_revocation_still_deletes_the_account_and_is_logged(
    anon_client, apple_verifier, apple_client, clock, caplog
):
    headers = _apple_account(anon_client, apple_verifier)
    apple_verifier.add("fresh", "a-1", email="ann@example.com", issued_at=clock.now)
    apple_client.revoke_error = RuntimeError("apple is down")

    with caplog.at_level("WARNING"):
        resp = _delete(anon_client, headers, provider="apple", token="fresh", nonce="n")

    assert resp.status_code == 204
    assert not _usable(anon_client, headers)
    assert "Apple revocation failed" in caplog.text
    assert "apple-refresh-1" not in caplog.text


def test_nothing_is_revoked_when_no_token_is_stored(
    anon_client, apple_verifier, apple_client, clock
):
    apple_client.refresh_token = None
    headers = _apple_account(anon_client, apple_verifier)
    apple_verifier.add("fresh", "a-1", email="ann@example.com", issued_at=clock.now)

    assert _delete(anon_client, headers, provider="apple", token="fresh", nonce="n").status_code == 204
    assert apple_client.revoked == []


def test_a_password_account_linked_to_apple_also_revokes_on_password_delete(
    client, apple_verifier, apple_client
):
    apple_verifier.add("a", "a-1", email="ana@example.com")
    client.post(
        "/auth/oauth/apple",
        json={"identity_token": "a", "nonce": "n", "authorization_code": "c", "date_of_birth": "1990-01-01"},
    )

    assert _delete(client, password=DEFAULT_PASSWORD).status_code == 204
    assert apple_client.revoked == ["apple-refresh-1"]
