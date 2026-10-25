from datetime import timedelta

import pytest

from tests.helpers import DEFAULT_PASSWORD

NEW_PASSWORD = "a brand new passphrase"
ANA = "ana@example.com"


def _password_reauth(password=DEFAULT_PASSWORD):
    return {"password": password}


def _change_password(client, headers=None, new_password=NEW_PASSWORD, reauth=None):
    body = {"new_password": new_password, "reauth": _password_reauth() if reauth is None else reauth}
    return client.post("/me/password", json=body, headers=headers)


def _login(client, email=ANA, password=DEFAULT_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _google_account(client, google_verifier, subject="g-1", email="gina@example.com"):
    google_verifier.add(f"signin-{subject}", subject, email=email)
    resp = client.post(
        "/auth/oauth/google", json={"id_token": f"signin-{subject}", "date_of_birth": "1990-01-01"}
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _error(resp):
    return resp.json()["detail"]["error"]


# ── re-authentication ──


def test_a_wrong_current_password_is_403_and_changes_nothing(client, sender):
    resp = _change_password(client, reauth=_password_reauth("wrong password"))

    assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert _login(client).status_code == 200
    assert _login(client, password=NEW_PASSWORD).status_code == 401
    assert sender.count_for(ANA) == 1  # only the registration code


def test_a_wrong_current_password_on_an_email_change_sends_no_code(client, sender):
    resp = client.post(
        "/me/email",
        json={"new_email": "new@example.com", "reauth": _password_reauth("wrong password")},
    )

    assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert sender.count_for("new@example.com") == 0


def test_a_fresh_provider_token_lets_a_provider_only_account_set_a_password(
    anon_client, google_verifier, clock
):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("fresh", "g-1", issued_at=clock.now - timedelta(minutes=1))

    resp = _change_password(
        anon_client, headers, reauth={"provider": "google", "token": "fresh"}
    )

    assert resp.status_code == 204


def test_a_ten_minute_old_provider_token_is_403(anon_client, google_verifier, clock):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("stale", "g-1", issued_at=clock.now - timedelta(minutes=10))

    resp = _change_password(
        anon_client, headers, reauth={"provider": "google", "token": "stale"}
    )

    assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert anon_client.get("/me", headers=headers).json()["has_password"] is False


def test_five_wrong_passwords_lock_out_even_the_right_one(client):
    for _ in range(5):
        assert _change_password(client, reauth=_password_reauth("wrong password")).status_code == 403

    resp = _change_password(client)

    assert resp.status_code == 429 and _error(resp) == "too_many_attempts"
    assert _login(client).status_code == 429


@pytest.mark.parametrize(
    "reauth", [{}, {"provider": "google"}, {"password": "x", "provider": "google", "token": "t"}]
)
def test_a_malformed_reauth_is_422(client, reauth):
    assert _change_password(client, reauth=reauth).status_code == 422


def test_the_endpoints_need_a_session(anon_client):
    assert _change_password(anon_client).status_code == 401


# ── set or change the password ──


def test_change_keeps_this_device_and_signs_out_others(client):
    second = {"Authorization": f"Bearer {_login(client).json()['token']}"}
    assert client.get("/me", headers=second).status_code == 200

    resp = _change_password(client)

    assert resp.status_code == 204
    assert client.get("/me").status_code == 200
    assert client.get("/me", headers=second).status_code == 401
    assert _login(client, password=NEW_PASSWORD).status_code == 200
    assert _login(client).status_code == 401


def test_a_provider_only_account_can_set_a_password(anon_client, google_verifier, clock):
    headers = _google_account(anon_client, google_verifier)
    google_verifier.add("fresh", "g-1", issued_at=clock.now)

    resp = _change_password(
        anon_client, headers, reauth={"provider": "google", "token": "fresh"}
    )

    assert resp.status_code == 204
    assert anon_client.get("/me", headers=headers).json()["has_password"] is True
    assert _login(anon_client, "gina@example.com", NEW_PASSWORD).status_code == 200


@pytest.mark.parametrize("length", [7, 129, 1024])
def test_a_new_password_outside_the_limits_is_400_and_changes_nothing(client, length):
    resp = _change_password(client, new_password="p" * length)

    assert resp.status_code == 400 and _error(resp) == "invalid_credentials_format"
    assert _login(client).status_code == 200


@pytest.mark.parametrize("length", [8, 128])
def test_the_length_limits_are_inclusive(client, length):
    assert _change_password(client, new_password="p" * length).status_code == 204


def test_the_notification_goes_to_the_account_address_without_a_code_or_password(client, sender):
    before = len(sender.sent)

    _change_password(client)

    assert len(sender.sent) == before + 1
    to, subject, body = sender.sent[-1]
    assert to == ANA
    assert "password was changed" in body and "reset your password" in body
    assert NEW_PASSWORD not in subject + body and DEFAULT_PASSWORD not in subject + body
    assert not any(part.strip(".,").isdigit() and len(part) >= 6 for part in body.split())


def test_a_failed_change_sends_no_notification(client, sender):
    before = len(sender.sent)

    _change_password(client, new_password="short")
    _change_password(client, reauth=_password_reauth("wrong password"))

    assert len(sender.sent) == before
