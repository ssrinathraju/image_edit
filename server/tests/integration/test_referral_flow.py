"""A refers B; both are paid when B verifies; the cap stops rewarding the referrer only."""
import io

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import DEFAULT_PASSWORD, RecordingSender
from tests.integration.test_generation_flow import SMALL_PNG


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def app_client(tmp_path, templates_dir, sender):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    with TestClient(create_app(settings, sender=sender)) as client:
        yield client


def _register(client, email, code=None) -> dict:
    body = {"email": email, "password": DEFAULT_PASSWORD}
    if code:
        body["referral_code"] = code
    resp = client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _verify(client, sender, email, headers) -> None:
    resp = client.post(
        "/auth/verify-email", json={"code": sender.last_code(email)}, headers=headers
    )
    assert resp.status_code == 200, resp.text


def _register_verified(client, sender, email, code=None) -> dict:
    headers = _register(client, email, code)
    _verify(client, sender, email, headers)
    return headers


def _me(client, headers) -> dict:
    return client.get("/me", headers=headers).json()


def _bonus(client, headers) -> int:
    return _me(client, headers)["usage"]["bonus_credits"]


def _submit(client, headers):
    return client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=headers,
    )


def test_referral_pays_both_only_after_the_friend_verifies(app_client, sender):
    a = _register_verified(app_client, sender, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]

    b = _register(app_client, "b@example.com", code.lower())
    assert (_bonus(app_client, a), _bonus(app_client, b)) == (0, 0)

    _verify(app_client, sender, "b@example.com", b)
    assert (_bonus(app_client, a), _bonus(app_client, b)) == (5, 5)
    assert [_submit(app_client, b).status_code for _ in range(4)] == [202] * 4
    usage = _me(app_client, b)["usage"]
    assert (usage["used_today"], usage["bonus_credits"]) == (3, 4)


def _user_store(client):
    from image_edit_server.api.deps import get_user_store

    return client.app.dependency_overrides[get_user_store]()


def _forget_recent_sends(client) -> None:
    """Stand in for a minute passing, so the next code email is not rate limited."""
    users = _user_store(client)
    users._conn.execute("DELETE FROM email_sends")
    users._conn.commit()


def test_a_later_password_reset_pays_nothing_more(app_client, sender):
    a = _register_verified(app_client, sender, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]
    _register_verified(app_client, sender, "b@example.com", code)
    _forget_recent_sends(app_client)

    app_client.post("/auth/password-reset/request", json={"email": "b@example.com"})
    resp = app_client.post(
        "/auth/password-reset/confirm",
        json={
            "email": "b@example.com",
            "code": sender.last_code("b@example.com"),
            "new_password": "another long password",
        },
    )

    assert resp.status_code == 200
    reset_session = {"Authorization": f"Bearer {resp.json()['token']}"}
    assert (_bonus(app_client, a), _bonus(app_client, reset_session)) == (5, 5)


def test_a_friend_is_still_paid_after_the_referrer_deletes_their_account(app_client, sender):
    a = _register_verified(app_client, sender, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]
    c = _register(app_client, "c@example.com", code)

    deleted = app_client.request(
        "DELETE", "/me", json={"password": DEFAULT_PASSWORD}, headers=a
    )
    assert deleted.status_code == 204
    _verify(app_client, sender, "c@example.com", c)

    assert _bonus(app_client, c) == 5


def test_eleventh_verified_friend_is_paid_but_the_referrer_is_not(app_client, sender):
    a = _register_verified(app_client, sender, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]
    for i in range(10):
        _register_verified(app_client, sender, f"f{i}@example.com", code)
    assert _bonus(app_client, a) == 50

    eleventh = _register_verified(app_client, sender, "f10@example.com", code)

    assert _bonus(app_client, eleventh) == 5
    after = _me(app_client, a)
    assert after["usage"]["bonus_credits"] == 50
    assert after["referral"]["rewards"] == 10
