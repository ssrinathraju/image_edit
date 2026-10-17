from tests.helpers import DEFAULT_PASSWORD


def _verify(client, code, headers=None):
    return client.post("/auth/verify-email", json={"code": code}, headers=headers)


def _resend(client, headers=None):
    return client.post("/auth/verify-email/resend", headers=headers)


def test_correct_code_verifies_the_email(unverified_client, sender):
    resp = _verify(unverified_client, sender.last_code("una@example.com"))

    assert resp.status_code == 200
    assert resp.json() == {"email_verified": True}
    assert unverified_client.get("/me").json()["email_verified"] is True


def test_a_code_with_surrounding_spaces_is_accepted(unverified_client, sender):
    code = sender.last_code("una@example.com")

    assert _verify(unverified_client, f" {code} ").status_code == 200


def test_wrong_code_is_400_invalid_code_and_leaves_the_email_unverified(unverified_client, sender):
    wrong = "000000" if sender.last_code("una@example.com") != "000000" else "111111"

    resp = _verify(unverified_client, wrong)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_code"
    assert unverified_client.get("/me").json()["email_verified"] is False


def test_expired_code_is_400_code_expired(unverified_client, sender, clock):
    code = sender.last_code("una@example.com")
    clock.advance(minutes=16)

    resp = _verify(unverified_client, code)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "code_expired"


def test_five_wrong_codes_invalidate_the_code(unverified_client, sender):
    code = sender.last_code("una@example.com")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert _verify(unverified_client, wrong).status_code == 400

    resp = _verify(unverified_client, code)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "code_expired"


def test_verified_account_gets_409_on_verify(client):
    resp = _verify(client, "123456")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "already_verified"


def test_verify_without_a_session_is_401(anon_client):
    resp = _verify(anon_client, "123456")

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "unauthorized"


def test_resend_without_a_session_is_401(anon_client):
    assert _resend(anon_client).status_code == 401


def test_resend_after_a_minute_sends_a_new_code_and_invalidates_the_old(unverified_client, sender, clock):
    old = sender.last_code("una@example.com")
    clock.advance(seconds=61)

    resp = _resend(unverified_client)

    assert resp.status_code == 202
    assert sender.count_for("una@example.com") == 2
    new = sender.last_code("una@example.com")
    assert old not in resp.text and new not in resp.text
    if new != old:
        assert _verify(unverified_client, old).status_code == 400
    assert _verify(unverified_client, new).status_code == 200


def test_resend_too_soon_is_429_with_retry_after(unverified_client, sender, clock):
    clock.advance(seconds=20)

    resp = _resend(unverified_client)

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "too_many_requests"
    assert int(resp.headers["Retry-After"]) <= 40
    assert sender.count_for("una@example.com") == 1


def test_the_hourly_cap_stops_a_sixth_email(unverified_client, sender, clock):
    for _ in range(4):
        clock.advance(seconds=61)
        assert _resend(unverified_client).status_code == 202
    clock.advance(seconds=61)

    resp = _resend(unverified_client)

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 60
    assert sender.count_for("una@example.com") == 5


def test_verified_account_cannot_resend(client):
    resp = _resend(client)

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "already_verified"


def test_a_resend_response_never_contains_the_code(unverified_client, sender, clock):
    clock.advance(seconds=61)

    resp = _resend(unverified_client)

    code = sender.last_code("una@example.com")
    assert code not in resp.text
    assert all(code not in value for value in resp.headers.values())


def test_a_failing_sender_does_not_fail_the_request(app, anon_client, sender, monkeypatch):
    def boom(*args):
        raise ConnectionRefusedError("down")

    monkeypatch.setattr(sender, "send", boom)

    resp = anon_client.post(
        "/auth/register", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert resp.status_code == 201
