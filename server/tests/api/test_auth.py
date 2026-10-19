import pytest

from tests.helpers import ADULT_DOB, DEFAULT_PASSWORD, register_headers


def _register(client, email="ana@example.com", password=DEFAULT_PASSWORD, **extra):
    body = {"email": email, "password": password, "date_of_birth": ADULT_DOB, **extra}
    return client.post("/auth/register", json=body)


def _confirm(client, sender, email="ana@example.com", code=None, password=DEFAULT_PASSWORD):
    return client.post(
        "/auth/register/confirm",
        json={"email": email, "code": code or sender.last_code(email), "password": password},
    )


def _signup(client, sender, email="ana@example.com", password=DEFAULT_PASSWORD, **extra):
    """Register and confirm; returns the confirm response (the new account's session)."""
    assert _register(client, email, password, **extra).status_code == 202
    resp = _confirm(client, sender, email)
    assert resp.status_code == 201, resp.text
    return resp


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login(client, email="ana@example.com", password=DEFAULT_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_sends_a_code_and_creates_no_account(anon_client, sender):
    resp = _register(anon_client)

    assert resp.status_code == 202
    assert resp.json() == {}
    assert sender.count_for("ana@example.com") == 1
    code = sender.last_code("ana@example.com")
    assert len(code) == 6 and code.isdigit()
    assert _login(anon_client).status_code == 401


def test_confirm_creates_the_account_and_returns_a_working_session(anon_client, sender):
    _register(anon_client)

    resp = _confirm(anon_client, sender)

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"token", "id", "email"}
    assert body["email"] == "ana@example.com"
    me = anon_client.get("/me", headers=_bearer(body["token"]))
    assert me.status_code == 200 and me.json()["id"] == body["id"]
    assert _login(anon_client).status_code == 200


def test_registering_again_after_a_minute_replaces_the_pending_registration(
    anon_client, sender, clock, monkeypatch
):
    codes = iter(["111111", "222222"])
    monkeypatch.setattr(
        "image_edit_server.services.email_code_service.generate_code", lambda: next(codes)
    )
    _register(anon_client, password="first password 1")
    clock.advance(seconds=61)

    assert _register(anon_client, password="second password 2").status_code == 202

    assert sender.count_for("ana@example.com") == 2
    stale = _confirm(anon_client, sender, code="111111")
    assert (stale.status_code, stale.json()["detail"]["error"]) == (400, "invalid_code")
    assert _confirm(
        anon_client, sender, code="222222", password="second password 2"
    ).status_code == 201
    assert _login(anon_client, password="second password 2").status_code == 200
    assert _login(anon_client, password="first password 1").status_code == 401


def test_registering_again_too_soon_is_429_and_keeps_the_first_code(anon_client, sender, clock):
    _register(anon_client)
    clock.advance(seconds=20)

    resp = _register(anon_client)

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "too_many_requests"
    assert resp.headers["Retry-After"] == "40"
    assert sender.count_for("ana@example.com") == 1
    assert _confirm(anon_client, sender).status_code == 201


def test_register_duplicate_in_any_case_is_409(anon_client, sender):
    _signup(anon_client, sender)

    resp = _register(anon_client, email="ANA@Example.com")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "email_taken"
    assert sender.count_for("ana@example.com") == 1


@pytest.mark.parametrize(
    "email,password",
    [("not-an-email", DEFAULT_PASSWORD), ("ana@example.com", "short")],
)
def test_register_invalid_format_is_400_and_sends_no_code(anon_client, sender, email, password):
    resp = _register(anon_client, email=email, password=password)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_credentials_format"
    assert sender.sent == []
    assert _login(anon_client, email, password).status_code == 401


def test_a_wrong_code_is_400_and_creates_no_account(anon_client, sender):
    _register(anon_client)
    code = sender.last_code("ana@example.com")
    wrong = "000000" if code != "000000" else "111111"

    resp = _confirm(anon_client, sender, code=wrong)

    assert (resp.status_code, resp.json()["detail"]["error"]) == (400, "invalid_code")
    assert _login(anon_client).status_code == 401


def test_an_expired_code_is_400_and_creates_no_account(anon_client, sender, clock):
    _register(anon_client)
    clock.advance(minutes=16)

    resp = _confirm(anon_client, sender)

    assert (resp.status_code, resp.json()["detail"]["error"]) == (400, "code_expired")
    assert _login(anon_client).status_code == 401


def test_confirming_an_email_that_never_registered_is_code_expired(anon_client):
    resp = anon_client.post(
        "/auth/register/confirm", json={"email": "nobody@example.com", "code": "123456", "password": DEFAULT_PASSWORD}
    )

    assert (resp.status_code, resp.json()["detail"]["error"]) == (400, "code_expired")


def test_a_used_code_cannot_confirm_twice(anon_client, sender):
    _signup(anon_client, sender)
    used = sender.last_code("ana@example.com")

    again = _confirm(anon_client, sender, code=used)

    assert (again.status_code, again.json()["detail"]["error"]) == (400, "code_expired")


def test_a_registration_confirmed_after_google_created_the_account_is_409(
    anon_client, sender, google_verifier
):
    _register(anon_client)
    google_verifier.add("g-tok", "g-1", email="ana@example.com")
    google = anon_client.post("/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": ADULT_DOB}).json()

    resp = _confirm(anon_client, sender)

    assert (resp.status_code, resp.json()["detail"]["error"]) == (409, "email_taken")
    me = anon_client.get("/me", headers=_bearer(google["token"])).json()
    assert (me["id"], me["providers"], me["has_password"]) == (google["id"], ["google"], False)
    assert _login(anon_client).status_code == 401


@pytest.mark.parametrize("path", ["/auth/verify-email", "/auth/verify-email/resend"])
def test_the_verification_endpoints_no_longer_exist(client, path):
    assert client.post(path, json={"code": "123456"}).status_code == 404


def test_login_correct_credentials_returns_token(anon_client, sender):
    _signup(anon_client, sender)

    resp = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_failures_are_indistinguishable(anon_client, sender):
    _signup(anon_client, sender)

    wrong = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "wrong password"}
    )
    unknown = anon_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["detail"]["error"] == "invalid_credentials"


def test_sixth_login_is_429(anon_client, sender):
    _signup(anon_client, sender)
    for _ in range(5):
        anon_client.post(
            "/auth/login", json={"email": "ana@example.com", "password": "wrong password"}
        )

    resp = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "too_many_attempts"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic abc"}])
def test_missing_or_invalid_token_is_401(anon_client, headers):
    resp = anon_client.get("/me", headers=headers)

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "unauthorized"


def test_expired_session_is_401(anon_client, user_store):
    from datetime import timedelta

    user = user_store.create_user("old@example.com", "hash")
    token = user_store.create_session(user.id, timedelta(seconds=-1))

    resp = anon_client.get("/me", headers=_bearer(token))

    assert resp.status_code == 401


def test_me_returns_identity_without_password_material(client):
    resp = client.get("/me")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {
        "id", "email", "created_at", "plan", "usage", "referral",
        "providers", "has_password", "age_confirmed", "consent",
    }
    assert "hash" not in resp.text


def test_logout_revokes_the_token_but_not_other_sessions(anon_client, sender):
    first = _signup(anon_client, sender).json()["token"]
    second = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    ).json()["token"]

    resp = anon_client.post("/auth/logout", headers=_bearer(first))

    assert resp.status_code == 204
    assert anon_client.get("/me", headers=_bearer(first)).status_code == 401
    assert anon_client.get("/me", headers=_bearer(second)).status_code == 200


def test_logout_without_token_is_401(anon_client):
    assert anon_client.post("/auth/logout").status_code == 401


def test_delete_me_with_wrong_password_is_403_and_keeps_account(client):
    resp = client.request("DELETE", "/me", json={"password": "wrong password"})

    assert resp.status_code == 403
    assert client.get("/me").status_code == 200


def test_delete_me_removes_the_account(client):
    resp = client.request("DELETE", "/me", json={"password": DEFAULT_PASSWORD})

    assert resp.status_code == 204
    assert client.get("/me").status_code == 401
    login = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401


def test_no_response_body_contains_a_password(anon_client, sender):
    bodies = [
        _register(anon_client).text,
        _confirm(anon_client, sender).text,
        _login(anon_client).text,
        _login(anon_client, password="wrong password").text,
    ]

    assert all(DEFAULT_PASSWORD not in body for body in bodies)
    assert all("hash" not in body.lower() for body in bodies)


def test_overlong_credentials_are_rejected_before_any_hashing(anon_client, client):
    long_email = "a" * 250 + "@example.com"
    long_password = "p" * 129

    login = anon_client.post(
        "/auth/login", json={"email": long_email, "password": DEFAULT_PASSWORD}
    )
    login_password = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": long_password}
    )
    delete = client.request("DELETE", "/me", json={"password": long_password})

    assert login.status_code == 422
    assert login_password.status_code == 422
    assert delete.status_code == 422
    assert client.get("/me").status_code == 200


def _me(client, token):
    return client.get("/me", headers=_bearer(token)).json()


def test_a_confirmed_referral_registration_rewards_both(anon_client, sender):
    referrer = _signup(anon_client, sender).json()
    code = _me(anon_client, referrer["token"])["referral"]["code"]

    friend = _signup(
        anon_client, sender, "ben@example.com", referral_code=f" {code.lower()} "
    ).json()

    assert _me(anon_client, friend["token"])["usage"]["bonus_credits"] == 5
    assert _me(anon_client, referrer["token"])["usage"]["bonus_credits"] == 5
    assert _me(anon_client, referrer["token"])["referral"]["rewards"] == 1


def test_an_unconfirmed_referral_registration_earns_nothing(anon_client, sender):
    referrer = _signup(anon_client, sender).json()
    code = _me(anon_client, referrer["token"])["referral"]["code"]

    _register(anon_client, "ben@example.com", referral_code=code)

    me = _me(anon_client, referrer["token"])
    assert (me["usage"]["bonus_credits"], me["referral"]["rewards"]) == (0, 0)


def test_register_with_an_unknown_referral_code_is_400_and_sends_no_code(anon_client, sender):
    resp = _register(anon_client, "ben@example.com", referral_code="NOSUCH22")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_referral_code"
    assert sender.sent == []
    assert _login(anon_client, "ben@example.com").status_code == 401


def test_register_without_a_code_grants_no_bonus(anon_client, sender):
    token = _signup(anon_client, sender).json()["token"]

    assert _me(anon_client, token)["usage"]["bonus_credits"] == 0


def test_blank_referral_code_is_treated_as_absent(anon_client, sender):
    resp = _register(anon_client, "ben@example.com", referral_code="  ")

    assert resp.status_code == 202
    assert _confirm(anon_client, sender, "ben@example.com").status_code == 201


def test_overlong_referral_code_is_422(anon_client):
    resp = _register(anon_client, "ben@example.com", referral_code="X" * 33)

    assert resp.status_code == 422


def test_no_registration_response_contains_the_code(anon_client, sender, clock):
    first = _register(anon_client)
    clock.advance(seconds=61)
    again = _register(anon_client)
    code = sender.last_code("ana@example.com")
    confirmed = _confirm(anon_client, sender)

    for resp in (first, again, confirmed):
        assert code not in resp.text
        assert all(code not in value for value in resp.headers.values())


def test_the_hourly_cap_counts_registration_and_reset_codes_together(
    anon_client, sender, clock
):
    _signup(anon_client, sender)
    for _ in range(4):
        clock.advance(seconds=61)
        anon_client.post("/auth/password-reset/request", json={"email": "ana@example.com"})
    assert sender.count_for("ana@example.com") == 5

    clock.advance(seconds=61)
    resp = anon_client.post("/auth/password-reset/request", json={"email": "ana@example.com"})

    assert resp.status_code == 202
    assert sender.count_for("ana@example.com") == 5


# ── accounts without a password ──


def _google_account(client, google_verifier, email="gina@example.com"):
    google_verifier.add("g-tok", "g-1", email=email)
    return client.post("/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": ADULT_DOB})


def test_password_login_on_a_google_account_fails_like_a_wrong_password(
    anon_client, google_verifier, sender
):
    _google_account(anon_client, google_verifier)
    _signup(anon_client, sender, email="other@example.com")

    on_google = anon_client.post(
        "/auth/login", json={"email": "gina@example.com", "password": "any password"}
    )
    wrong = anon_client.post(
        "/auth/login", json={"email": "other@example.com", "password": "any password"}
    )

    assert on_google.status_code == 401
    assert on_google.json() == wrong.json()
    assert on_google.json()["detail"]["error"] == "invalid_credentials"


def test_the_timing_stand_in_password_cannot_log_in_to_a_google_account(
    anon_client, google_verifier
):
    _google_account(anon_client, google_verifier)

    resp = anon_client.post(
        "/auth/login",
        json={"email": "gina@example.com", "password": "not-a-real-password"},
    )

    assert resp.status_code == 401


def test_password_reset_gives_a_google_account_a_password(
    anon_client, google_verifier, sender, clock
):
    google_id = _google_account(anon_client, google_verifier).json()["id"]
    anon_client.post("/auth/password-reset/request", json={"email": "gina@example.com"})
    code = sender.last_code("gina@example.com")

    confirm = anon_client.post(
        "/auth/password-reset/confirm",
        json={"email": "gina@example.com", "code": code, "new_password": "a brand new password"},
    )
    login = anon_client.post(
        "/auth/login",
        json={"email": "gina@example.com", "password": "a brand new password"},
    )
    again = anon_client.post("/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": ADULT_DOB})

    assert confirm.status_code == 200
    assert login.status_code == 200
    assert login.json()["id"] == google_id
    assert (again.status_code, again.json()["id"]) == (200, google_id)
    me = anon_client.get("/me", headers={"Authorization": f"Bearer {login.json()['token']}"})
    assert me.json()["has_password"] is True


def test_someone_elses_reregistration_cannot_set_the_password(anon_client, sender, clock):
    victim, attacker = "victim password 1", "attacker password 2"
    _register(anon_client, password=victim)
    clock.advance(seconds=61)
    assert _register(anon_client, password=attacker).status_code == 202

    resp = _confirm(anon_client, sender, password=victim)

    assert (resp.status_code, resp.json()["detail"]["error"]) == (409, "registration_changed")
    assert _login(anon_client, password=victim).status_code == 401
    assert _login(anon_client, password=attacker).status_code == 401
    again = _confirm(anon_client, sender, code=sender.last_code("ana@example.com"), password=attacker)
    assert (again.status_code, again.json()["detail"]["error"]) == (400, "code_expired")
    assert _login(anon_client, password=attacker).status_code == 401


def test_the_password_is_checked_only_after_the_code(anon_client, sender):
    _register(anon_client)
    right = sender.last_code("ana@example.com")
    wrong = "000000" if right != "000000" else "111111"

    resp = _confirm(anon_client, sender, code=wrong, password="not the password 9")

    assert (resp.status_code, resp.json()["detail"]["error"]) == (400, "invalid_code")
    assert _confirm(anon_client, sender).status_code == 201


def test_a_wrong_password_with_the_right_code_discards_the_registration(anon_client, sender):
    _register(anon_client)

    resp = _confirm(anon_client, sender, password="not the password 9")

    assert (resp.status_code, resp.json()["detail"]["error"]) == (409, "registration_changed")
    retry = _confirm(anon_client, sender)
    assert (retry.status_code, retry.json()["detail"]["error"]) == (400, "code_expired")
    assert _login(anon_client).status_code == 401


def test_a_reregistration_between_the_password_check_and_the_commit_is_registration_changed(
    anon_client, sender, clock, monkeypatch
):
    from image_edit_server.services import auth_service

    _register(anon_client)
    real_verify = auth_service.verify_password

    def verify_then_reregister(password, stored):
        matched = real_verify(password, stored)
        clock.advance(seconds=61)
        assert _register(anon_client, password="attacker password 2").status_code == 202
        return matched

    monkeypatch.setattr(auth_service, "verify_password", verify_then_reregister)

    resp = _confirm(anon_client, sender)

    assert (resp.status_code, resp.json()["detail"]["error"]) == (409, "registration_changed")
    assert _login(anon_client).status_code == 401
    assert _login(anon_client, password="attacker password 2").status_code == 401


# ── Age check on registration ───────────────────────────────────────────

EXACTLY_18 = "2008-01-01"  # the fake clock reads 2026-01-01
ONE_DAY_SHORT = "2008-01-02"


def _pending_count(user_store) -> int:
    return user_store._conn.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[0]


def test_under_18_registration_sends_no_code_and_leaves_no_pending_row(
    anon_client, sender, user_store
):
    resp = _register(anon_client, date_of_birth=ONE_DAY_SHORT)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "under_age"
    assert sender.count_for("ana@example.com") == 0
    assert _pending_count(user_store) == 0


def test_registration_without_a_date_of_birth_is_refused_and_sends_no_code(
    anon_client, sender
):
    resp = anon_client.post(
        "/auth/register", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert resp.status_code == 422
    assert sender.count_for("ana@example.com") == 0


def test_registration_at_exactly_18_is_confirmed_as_an_adult(anon_client, sender):
    token = _signup(anon_client, sender, date_of_birth=EXACTLY_18).json()["token"]

    me = anon_client.get("/me", headers=_bearer(token)).json()

    assert me["age_confirmed"] is True


def test_a_malformed_date_of_birth_is_400_and_sends_no_code(anon_client, sender):
    resp = _register(anon_client, date_of_birth="2008-13-01")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_date_of_birth"
    assert sender.count_for("ana@example.com") == 0


def test_the_age_check_runs_before_the_email_is_looked_at(anon_client, sender):
    resp = _register(anon_client, email="not-an-email", date_of_birth=ONE_DAY_SHORT)

    assert resp.json()["detail"]["error"] == "under_age"


def test_login_works_without_a_date_of_birth(anon_client, sender):
    _signup(anon_client, sender)

    assert _login(anon_client).status_code == 200
