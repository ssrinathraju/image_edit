import pytest

from tests.helpers import DEFAULT_PASSWORD, register_headers


def _register(client, email="ana@example.com", password=DEFAULT_PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_register_returns_201_and_a_working_token(anon_client):
    resp = _register(anon_client)

    assert resp.status_code == 201
    body = resp.json()
    assert set(body) == {"token", "id", "email"}
    assert body["email"] == "ana@example.com"
    me = anon_client.get("/me", headers=_bearer(body["token"]))
    assert me.status_code == 200
    assert me.json()["id"] == body["id"]


def test_register_duplicate_in_any_case_is_409(anon_client):
    _register(anon_client)

    resp = _register(anon_client, email="ANA@Example.com")

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "email_taken"


@pytest.mark.parametrize(
    "email,password",
    [("not-an-email", DEFAULT_PASSWORD), ("ana@example.com", "short")],
)
def test_register_invalid_format_is_400(anon_client, email, password):
    resp = _register(anon_client, email=email, password=password)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_credentials_format"
    login = anon_client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 401


def test_login_correct_credentials_returns_token(anon_client):
    _register(anon_client)

    resp = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )

    assert resp.status_code == 200
    assert resp.json()["token"]


def test_login_failures_are_indistinguishable(anon_client):
    _register(anon_client)

    wrong = anon_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": "wrong password"}
    )
    unknown = anon_client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["detail"]["error"] == "invalid_credentials"


def test_sixth_login_is_429(anon_client):
    _register(anon_client)
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
    assert set(body) == {"id", "email", "created_at", "plan", "usage", "referral"}
    assert "password" not in resp.text


def test_logout_revokes_the_token_but_not_other_sessions(anon_client):
    first = _register(anon_client).json()["token"]
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


def test_no_response_body_contains_a_password(anon_client):
    bodies = [
        _register(anon_client).text,
        anon_client.post(
            "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
        ).text,
        anon_client.post(
            "/auth/login", json={"email": "ana@example.com", "password": "wrong password"}
        ).text,
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


def test_register_with_a_lowercase_referral_code_rewards_both(anon_client):
    referrer = _register(anon_client).json()
    code = _me(anon_client, referrer["token"])["referral"]["code"]

    resp = anon_client.post(
        "/auth/register",
        json={"email": "ben@example.com", "password": DEFAULT_PASSWORD, "referral_code": f" {code.lower()} "},
    )

    assert resp.status_code == 201
    assert _me(anon_client, resp.json()["token"])["usage"]["bonus_credits"] == 5
    assert _me(anon_client, referrer["token"])["usage"]["bonus_credits"] == 5
    assert _me(anon_client, referrer["token"])["referral"]["rewards"] == 1


def test_register_with_an_unknown_referral_code_is_400_and_creates_nothing(anon_client):
    resp = anon_client.post(
        "/auth/register",
        json={"email": "ben@example.com", "password": DEFAULT_PASSWORD, "referral_code": "NOSUCH22"},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_referral_code"
    login = anon_client.post(
        "/auth/login", json={"email": "ben@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401


def test_register_without_a_code_grants_no_bonus(anon_client):
    token = _register(anon_client).json()["token"]

    assert _me(anon_client, token)["usage"]["bonus_credits"] == 0


def test_blank_referral_code_is_treated_as_absent(anon_client):
    resp = anon_client.post(
        "/auth/register",
        json={"email": "ben@example.com", "password": DEFAULT_PASSWORD, "referral_code": "  "},
    )

    assert resp.status_code == 201


def test_overlong_referral_code_is_422(anon_client):
    resp = anon_client.post(
        "/auth/register",
        json={"email": "ben@example.com", "password": DEFAULT_PASSWORD, "referral_code": "X" * 33},
    )

    assert resp.status_code == 422
