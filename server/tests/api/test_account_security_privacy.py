import logging
from tests.helpers import DEFAULT_PASSWORD

NEW_PASSWORD = "a brand new passphrase"
WRONG_PASSWORD = "definitely the wrong one"
NEW = "new@example.com"


def _exercise_every_endpoint(client, sender, google_verifier, apple_verifier, clock):
    """Success and failure paths of each endpoint; returns the secrets that must stay out of logs."""
    good = {"password": DEFAULT_PASSWORD}
    bad = {"password": WRONG_PASSWORD}
    client.post("/me/password", json={"new_password": NEW_PASSWORD, "reauth": bad})
    assert client.post(
        "/me/password", json={"new_password": NEW_PASSWORD, "reauth": good}
    ).status_code == 204
    # The password changed, so later calls use the new one.
    good = {"password": NEW_PASSWORD}
    client.post("/me/email", json={"new_email": NEW, "reauth": bad})
    assert client.post("/me/email", json={"new_email": NEW, "reauth": good}).status_code == 202
    code = sender.last_code(NEW)
    client.post("/me/email/confirm", json={"code": "000000"})
    assert client.post("/me/email/confirm", json={"code": code}).status_code == 200
    google_verifier.add("google-secret-token", "g-1", email="gina@gmail.com")
    apple_verifier.add("apple-secret-token", "a-1", email="relay@privaterelay.appleid.com")
    assert client.post(
        "/me/providers/google", json={"id_token": "google-secret-token", "reauth": good}
    ).status_code == 200
    assert client.post(
        "/me/providers/google", json={"id_token": "google-secret-token", "reauth": good}
    ).status_code == 409
    client.post("/me/providers/google", json={"id_token": "rejected-secret-token", "reauth": good})
    assert client.post(
        "/me/providers/apple",
        json={"identity_token": "apple-secret-token", "nonce": "n", "authorization_code": "code", "reauth": good},
    ).status_code == 200
    client.request("DELETE", "/me/providers/google", json={"reauth": bad})
    assert client.request(
        "DELETE", "/me/providers/google", json={"reauth": good}
    ).status_code == 204
    assert client.request(
        "DELETE", "/me/providers/apple", json={"reauth": good}
    ).status_code == 204
    return [
        DEFAULT_PASSWORD,
        NEW_PASSWORD,
        WRONG_PASSWORD,
        code,
        "000000",
        "google-secret-token",
        "rejected-secret-token",
        "apple-secret-token",
        "apple-refresh-1",
        "Bearer",
    ]


def test_no_password_code_token_or_address_reaches_the_log(
    client, sender, google_verifier, apple_verifier, clock, caplog
):
    session_token = client.headers["Authorization"].split()[-1]

    with caplog.at_level(logging.DEBUG):
        secrets = _exercise_every_endpoint(client, sender, google_verifier, apple_verifier, clock)

    assert caplog.records, "the endpoints are expected to log security events"
    for secret in [*secrets, session_token]:
        assert secret not in caplog.text
    assert "@" not in caplog.text


def test_failed_notification_sends_do_not_log_the_address(client, sender, caplog):
    def broken(to, subject, body):
        raise ConnectionRefusedError("refused")

    sender.send = broken

    with caplog.at_level(logging.DEBUG):
        resp = client.post(
            "/me/password",
            json={"new_password": NEW_PASSWORD, "reauth": {"password": DEFAULT_PASSWORD}},
        )

    assert resp.status_code == 204
    assert "ConnectionRefusedError" in caplog.text
    assert "ana@example.com" not in caplog.text and NEW_PASSWORD not in caplog.text


def test_security_events_are_logged_with_the_user_id_only(client, caplog):
    user_id = client.get("/me").json()["id"]

    with caplog.at_level(logging.INFO):
        client.post(
            "/me/password",
            json={"new_password": NEW_PASSWORD, "reauth": {"password": DEFAULT_PASSWORD}},
        )
        client.post(
            "/me/password",
            json={"new_password": NEW_PASSWORD, "reauth": {"password": WRONG_PASSWORD}},
        )

    assert f"password_changed: user {user_id}" in caplog.text
    assert f"reauth_failed: user {user_id}" in caplog.text
