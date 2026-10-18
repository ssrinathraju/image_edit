import pytest

from tests.helpers import DEFAULT_PASSWORD, register_headers

NEW_PASSWORD = "a brand new password"


def _request(client, email):
    return client.post("/auth/password-reset/request", json={"email": email})


def _confirm(client, email, code, new_password=NEW_PASSWORD):
    return client.post(
        "/auth/password-reset/confirm",
        json={"email": email, "code": code, "new_password": new_password},
    )


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


@pytest.fixture
def registered(anon_client, sender, clock):
    """ana@example.com is registered; a minute has passed since her first email."""
    headers = register_headers(anon_client, "ana@example.com")
    clock.advance(seconds=61)
    sender.sent.clear()
    return headers


def test_registered_email_in_mixed_case_receives_a_code(anon_client, sender, registered):
    resp = _request(anon_client, "ANA@Example.com")

    assert resp.status_code == 202
    assert sender.count_for("ana@example.com") == 1
    assert "password reset code" in sender.sent[0][2]


def test_unknown_email_gets_a_byte_identical_response_and_no_email(anon_client, sender, registered):
    known = _request(anon_client, "ana@example.com")
    unknown = _request(anon_client, "nobody@example.com")

    assert unknown.status_code == known.status_code == 202
    assert unknown.content == known.content
    assert sender.count_for("nobody@example.com") == 0


def test_limited_request_gets_a_byte_identical_response_and_no_email(anon_client, sender, registered, clock):
    first = _request(anon_client, "ana@example.com")
    clock.advance(seconds=10)

    limited = _request(anon_client, "ana@example.com")

    assert limited.status_code == 202
    assert limited.content == first.content
    assert sender.count_for("ana@example.com") == 1


def test_malformed_email_is_400_invalid_credentials_format(anon_client):
    resp = _request(anon_client, "not-an-email")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_credentials_format"


def test_reset_response_does_not_contain_the_code(anon_client, sender, registered):
    resp = _request(anon_client, "ana@example.com")

    code = sender.last_code("ana@example.com")
    assert code not in resp.text
    assert all(code not in value for value in resp.headers.values())


def _reset(anon_client, sender):
    _request(anon_client, "ana@example.com")
    return _confirm(anon_client, "ana@example.com", sender.last_code("ana@example.com"))


def test_correct_code_returns_a_working_token(anon_client, sender, registered):
    resp = _reset(anon_client, sender)

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "ana@example.com"
    assert set(body) == {"token", "id", "email"}
    me = anon_client.get("/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_new_password_logs_in_and_the_old_one_does_not(anon_client, sender, registered):
    _reset(anon_client, sender)

    assert _login(anon_client, "ana@example.com", NEW_PASSWORD).status_code == 200
    assert _login(anon_client, "ana@example.com", DEFAULT_PASSWORD).status_code == 401


def test_all_earlier_sessions_are_revoked(anon_client, sender, registered):
    second = _login(anon_client, "ana@example.com", DEFAULT_PASSWORD).json()["token"]

    resp = _reset(anon_client, sender)

    assert anon_client.get("/me", headers=registered).status_code == 401
    assert anon_client.get("/me", headers={"Authorization": f"Bearer {second}"}).status_code == 401
    new = {"Authorization": f"Bearer {resp.json()['token']}"}
    assert anon_client.get("/me", headers=new).status_code == 200


def test_reset_clears_a_login_lockout(anon_client, sender, registered):
    for _ in range(5):
        _login(anon_client, "ana@example.com", "wrong password")
    assert _login(anon_client, "ana@example.com", DEFAULT_PASSWORD).status_code == 429

    _reset(anon_client, sender)

    assert _login(anon_client, "ana@example.com", NEW_PASSWORD).status_code == 200


def test_every_failure_is_the_same_invalid_code_response(anon_client, sender, registered, clock):
    _request(anon_client, "ana@example.com")
    code = sender.last_code("ana@example.com")
    wrong = "000000" if code != "000000" else "111111"

    unknown = _confirm(anon_client, "nobody@example.com", code)
    wrong_code = _confirm(anon_client, "ana@example.com", wrong)
    clock.advance(minutes=16)
    expired = _confirm(anon_client, "ana@example.com", code)

    for resp in (unknown, wrong_code, expired):
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_code"
    assert unknown.content == wrong_code.content == expired.content
    assert _login(anon_client, "ana@example.com", DEFAULT_PASSWORD).status_code == 200
    assert _login(anon_client, "ana@example.com", NEW_PASSWORD).status_code == 401


def test_weak_passwords_do_not_use_up_attempts(anon_client, sender, registered):
    _request(anon_client, "ana@example.com")
    code = sender.last_code("ana@example.com")

    weak = [_confirm(anon_client, "ana@example.com", code, "short") for _ in range(5)]
    final = _confirm(anon_client, "ana@example.com", code)

    for resp in weak:
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_credentials_format"
    assert final.status_code == 200


def test_a_code_cannot_be_used_twice(anon_client, sender, registered):
    _reset(anon_client, sender)

    again = _confirm(anon_client, "ana@example.com", sender.last_code("ana@example.com"), "yet another password")

    assert again.status_code == 400
    assert again.json()["detail"]["error"] == "invalid_code"


def test_over_long_new_password_is_400_invalid_credentials_format(anon_client, sender, registered):
    _request(anon_client, "ana@example.com")
    code = sender.last_code("ana@example.com")
    resp = _confirm(anon_client, "ana@example.com", code, "p" * 129)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_credentials_format"
