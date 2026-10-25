import pytest

from tests.helpers import DEFAULT_PASSWORD

ANA = "ana@example.com"
NEW = "new@example.com"


def _request(client, new_email=NEW, headers=None, password=DEFAULT_PASSWORD):
    body = {"new_email": new_email, "reauth": {"password": password}}
    return client.post("/me/email", json=body, headers=headers)


def _confirm(client, code, headers=None):
    return client.post("/me/email/confirm", json={"code": code}, headers=headers)


def _login(client, email, password=DEFAULT_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def _error(resp):
    return resp.json()["detail"]["error"]


# ── request ──


def test_the_code_goes_to_the_new_address_and_the_email_is_unchanged(client, sender):
    resp = _request(client)

    assert resp.status_code == 202
    assert sender.count_for(NEW) == 1
    assert "email change code" in sender.sent[-1][1]
    assert client.get("/me").json()["email"] == ANA


def test_the_new_address_is_normalised(client, sender):
    assert _request(client, "  New@Example.COM ").status_code == 202

    assert sender.count_for(NEW) == 1


def test_an_address_used_by_another_account_is_409_and_sends_no_code(
    client, second_user_headers, sender
):
    resp = _request(client, "ben@example.com")

    assert resp.status_code == 409 and _error(resp) == "email_taken"
    assert sender.count_for("ben@example.com") == 1  # only ben's registration code


@pytest.mark.parametrize("new_email", ["not-an-email", "a@b", "", ANA, "ANA@example.com"])
def test_a_bad_or_unchanged_address_is_400(client, sender, new_email):
    resp = _request(client, new_email)

    assert resp.status_code == 400 and _error(resp) == "invalid_credentials_format"
    assert sender.count_for(NEW) == 0


def test_a_second_request_within_a_minute_is_429_with_retry_after(client):
    _request(client)

    resp = _request(client)

    assert resp.status_code == 429 and _error(resp) == "too_many_requests"
    assert int(resp.headers["Retry-After"]) > 0


def test_the_hourly_cap_counts_all_code_purposes(client, clock, sender, settings):
    for _ in range(settings.EMAIL_MAX_PER_HOUR):
        assert _request(client).status_code == 202
        clock.advance(seconds=settings.EMAIL_RESEND_SECONDS + 1)

    resp = _request(client)

    assert resp.status_code == 429 and _error(resp) == "too_many_requests"


def test_a_new_request_replaces_the_pending_change(client, clock, sender):
    _request(client, "first@example.com")
    clock.advance(minutes=2)
    _request(client, NEW)

    resp = _confirm(client, sender.last_code(NEW))

    assert resp.status_code == 200 and resp.json() == {"email": NEW}


# ── confirm ──


def test_a_confirmed_change_updates_the_email_and_sign_in(client, sender):
    _request(client)

    resp = _confirm(client, sender.last_code(NEW))

    assert resp.status_code == 200 and resp.json() == {"email": NEW}
    assert client.get("/me").json()["email"] == NEW
    assert _login(client, NEW).status_code == 200
    assert _login(client, ANA).status_code == 401


def test_other_sessions_are_signed_out_and_this_one_stays(client, sender):
    second = {"Authorization": f"Bearer {_login(client, ANA).json()['token']}"}
    _request(client)

    _confirm(client, sender.last_code(NEW))

    assert client.get("/me").status_code == 200
    assert client.get("/me", headers=second).status_code == 401


def test_the_old_address_is_told_with_the_new_address_and_no_code(client, sender):
    _request(client)
    before = sender.count_for(ANA)

    _confirm(client, sender.last_code(NEW))

    assert sender.count_for(ANA) == before + 1
    to, _, body = sender.sent[-1]
    assert to == ANA
    assert NEW in body and "reset" not in body.lower()
    assert "right away" in body
    assert not any(part.strip(".,").isdigit() and len(part) >= 6 for part in body.split())


def test_the_notice_names_the_configured_support_address(client, sender, settings):
    settings.SUPPORT_EMAIL = "help@example.com"
    _request(client)

    _confirm(client, sender.last_code(NEW))

    assert "contact us right away at help@example.com" in sender.sent[-1][2]


def test_a_wrong_code_is_400_invalid_code_and_the_email_is_unchanged(client, sender):
    _request(client)
    code = sender.last_code(NEW)
    wrong = "000000" if code != "000000" else "111111"

    resp = _confirm(client, wrong)

    assert resp.status_code == 400 and _error(resp) == "invalid_code"
    assert client.get("/me").json()["email"] == ANA
    assert _confirm(client, code).status_code == 200


def test_an_expired_code_is_400_code_expired(client, sender, clock):
    _request(client)
    clock.advance(minutes=16)

    resp = _confirm(client, sender.last_code(NEW))

    assert resp.status_code == 400 and _error(resp) == "code_expired"
    assert client.get("/me").json()["email"] == ANA


def test_confirming_without_a_request_is_code_expired(client):
    resp = _confirm(client, "123456")

    assert resp.status_code == 400 and _error(resp) == "code_expired"


def test_a_code_cannot_be_used_twice(client, sender):
    _request(client)
    code = sender.last_code(NEW)
    _confirm(client, code)

    assert _confirm(client, code).status_code == 400


def test_an_address_registered_meanwhile_is_409_and_the_change_is_discarded(
    client, user_store, sender
):
    _request(client)
    user_store.create_user(NEW, "hash")

    resp = _confirm(client, sender.last_code(NEW))

    assert resp.status_code == 409 and _error(resp) == "email_taken"
    assert client.get("/me").json()["email"] == ANA
    assert _confirm(client, sender.last_code(NEW)).status_code == 400


def test_the_pending_address_is_never_returned_by_me(client):
    _request(client)

    assert NEW not in client.get("/me").text


def test_a_code_sent_to_another_address_does_not_confirm_my_change(
    client, anon_client, second_user_headers, sender
):
    """Codes are keyed by address, so this checks only that an unrelated address's code fails."""
    _request(client)
    other = anon_client.post(
        "/me/email",
        json={"new_email": "other@example.com", "reauth": {"password": DEFAULT_PASSWORD}},
        headers=second_user_headers,
    )
    assert other.status_code == 202

    resp = _confirm(client, sender.last_code("other@example.com"))

    assert resp.status_code == 400
    assert client.get("/me").json()["email"] == ANA


def test_confirm_needs_a_session(anon_client):
    assert _confirm(anon_client, "123456").status_code == 401
