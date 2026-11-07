import logging

from tests.helpers import ADULT_DOB, DEFAULT_PASSWORD

LOG_NAME = "image_edit_server.services.auth_service"


def _register(client, email):
    return client.post(
        "/auth/register",
        json={"email": email, "password": DEFAULT_PASSWORD, "date_of_birth": ADULT_DOB},
    )


def _pending_count(user_store, email) -> int:
    return user_store._conn.execute(
        "SELECT COUNT(*) FROM pending_registrations WHERE email = ?", (email,)
    ).fetchone()[0]


def test_a_disposable_domain_is_refused_with_nothing_stored_or_sent(
    anon_client, sender, user_store
):
    resp = _register(anon_client, "someone@mailinator.com")

    assert resp.status_code == 400
    assert resp.json()["detail"] == {
        "error": "disposable_email",
        "detail": "Use a permanent email address.",
    }
    assert sender.sent == []
    assert _pending_count(user_store, "someone@mailinator.com") == 0


def test_a_subdomain_and_upper_case_of_a_listed_domain_are_refused(anon_client, sender):
    for email in ("someone@mx.mailinator.com", "Someone@MAILINATOR.com"):
        resp = _register(anon_client, email)

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "disposable_email"
    assert sender.sent == []


def test_an_ordinary_domain_still_registers(anon_client, sender):
    resp = _register(anon_client, "someone@example.com")

    assert resp.status_code == 202
    assert sender.count_for("someone@example.com") == 1


def test_the_refusal_logs_the_domain_but_not_the_address(anon_client, caplog):
    with caplog.at_level(logging.INFO, logger=LOG_NAME):
        _register(anon_client, "private.person@mx.mailinator.com")

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "disposable_email_refused" in text
    assert "mailinator.com" in text
    assert "private.person" not in text
    assert "@" not in text


def test_a_provider_sign_in_with_a_listed_domain_is_not_checked(
    anon_client, google_verifier, apple_verifier
):
    google_verifier.add("g-tok", "g-1", email="someone@mailinator.com")
    apple_verifier.add("a-tok", "a-1", email="abc123@privaterelay.appleid.com")

    google = anon_client.post(
        "/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": ADULT_DOB}
    )
    apple = anon_client.post(
        "/auth/oauth/apple",
        json={
            "identity_token": "a-tok",
            "nonce": "n",
            "authorization_code": "code",
            "date_of_birth": ADULT_DOB,
        },
    )

    assert google.status_code == 200 and google.json()["created"] is True
    assert apple.status_code == 200 and apple.json()["created"] is True
