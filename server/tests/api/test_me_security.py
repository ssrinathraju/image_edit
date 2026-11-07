import logging

from tests.helpers import DEFAULT_PASSWORD

LOG_NAME = "image_edit_server.services.auth_service"


def _request(client, new_email):
    return client.post(
        "/me/email", json={"new_email": new_email, "reauth": {"password": DEFAULT_PASSWORD}}
    )


def test_a_change_to_a_disposable_address_is_refused_and_sends_no_code(client, sender):
    sent_before = len(sender.sent)

    resp = _request(client, "new@mailinator.com")

    assert resp.status_code == 400
    assert resp.json()["detail"] == {
        "error": "disposable_email",
        "detail": "Use a permanent email address.",
    }
    assert len(sender.sent) == sent_before
    assert client.get("/me").json()["email"] == "ana@example.com"


def test_a_change_to_a_subdomain_of_a_listed_domain_is_refused(client):
    resp = _request(client, "New@Mx.MAILINATOR.com")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "disposable_email"


def test_a_change_to_an_ordinary_domain_still_works(client, sender):
    resp = _request(client, "new@example.com")

    assert resp.status_code == 202
    assert sender.count_for("new@example.com") == 1


def test_the_refusal_logs_the_domain_but_not_the_address(client, caplog):
    with caplog.at_level(logging.INFO, logger=LOG_NAME):
        _request(client, "private.person@mailinator.com")

    text = "\n".join(record.getMessage() for record in caplog.records)
    assert "disposable_email_refused" in text
    assert "private.person" not in text
