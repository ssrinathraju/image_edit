"""A refers B; both get credits; the cap stops rewarding the referrer only."""
import io

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import DEFAULT_PASSWORD
from tests.integration.test_generation_flow import SMALL_PNG


@pytest.fixture
def app_client(tmp_path, templates_dir):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    with TestClient(create_app(settings)) as client:
        yield client


def _register(client, email, code=None) -> dict:
    body = {"email": email, "password": DEFAULT_PASSWORD}
    if code:
        body["referral_code"] = code
    resp = client.post("/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _verify(client, headers) -> None:
    from image_edit_server.api.deps import get_user_store

    users = client.app.dependency_overrides[get_user_store]()
    users.mark_email_verified(_me(client, headers)["id"], 5, 10)


def _me(client, headers) -> dict:
    return client.get("/me", headers=headers).json()


def _submit(client, headers):
    return client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=headers,
    )


def test_referral_rewards_both_and_bonus_covers_the_fourth(app_client):
    a = _register(app_client, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]

    b = _register(app_client, "b@example.com", code.lower())
    _verify(app_client, b)

    assert _me(app_client, a)["usage"]["bonus_credits"] == 5
    assert _me(app_client, b)["usage"]["bonus_credits"] == 5
    assert [_submit(app_client, b).status_code for _ in range(4)] == [202] * 4
    usage = _me(app_client, b)["usage"]
    assert (usage["used_today"], usage["bonus_credits"]) == (3, 4)


def test_eleventh_friend_is_rewarded_but_the_referrer_is_not(app_client):
    a = _register(app_client, "a@example.com")
    code = _me(app_client, a)["referral"]["code"]
    for i in range(10):
        _verify(app_client, _register(app_client, f"f{i}@example.com", code))
    assert _me(app_client, a)["usage"]["bonus_credits"] == 50

    eleventh = _register(app_client, "f10@example.com", code)
    _verify(app_client, eleventh)

    assert _me(app_client, eleventh)["usage"]["bonus_credits"] == 5
    after = _me(app_client, a)
    assert after["usage"]["bonus_credits"] == 50
    assert after["referral"]["rewards"] == 10
