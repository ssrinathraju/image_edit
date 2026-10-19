"""Google sign-up, a referral, a generation, a repeat sign-in, linking and deletion on the real app."""
import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import DEFAULT_PASSWORD, FakeVerifier, RecordingSender, grant_consent
from tests.integration.test_generation_flow import SMALL_PNG


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def google() -> FakeVerifier:
    return FakeVerifier("google", _now)


@pytest.fixture
def app_client(tmp_path, templates_dir, sender, google):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    app = create_app(settings, sender=sender, verifiers={"google": google})
    with TestClient(app) as client:
        yield client


def _bearer(resp) -> dict:
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _google(client, token):
    return client.post("/auth/oauth/google", json={"id_token": token, "date_of_birth": "1990-01-01"})


def _register_confirmed(client, sender, email) -> dict:
    resp = client.post("/auth/register", json={"email": email, "password": DEFAULT_PASSWORD, "date_of_birth": "1990-01-01"})
    assert resp.status_code == 202, resp.text
    confirm = client.post(
        "/auth/register/confirm",
        json={"email": email, "code": sender.last_code(email), "password": DEFAULT_PASSWORD},
    )
    assert confirm.status_code == 201, confirm.text
    return _bearer(confirm)


def _bonus(client, headers) -> int:
    return client.get("/me", headers=headers).json()["usage"]["bonus_credits"]


def test_social_sign_in_flow(app_client, sender, google):
    friend = _register_confirmed(app_client, sender, "friend@example.com")
    friend_code = app_client.get("/me", headers=friend).json()["referral"]["code"]

    google.add("first-signin", "g-1", email="gina@example.com")
    created = _google(app_client, "first-signin")
    assert created.status_code == 200 and created.json()["created"] is True
    gina = _bearer(created)

    redeem = app_client.post("/me/referral", json={"code": friend_code}, headers=gina)
    assert redeem.status_code == 200
    assert _bonus(app_client, gina) == 5
    assert _bonus(app_client, friend) == 5

    grant_consent(app_client, gina)
    submit = app_client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=gina,
    )
    assert submit.status_code == 202, submit.text

    again = _google(app_client, "first-signin")
    assert (again.json()["created"], again.json()["id"]) == (False, created.json()["id"])

    pat = _register_confirmed(app_client, sender, "pat@example.com")
    pat_id = app_client.get("/me", headers=pat).json()["id"]
    google.add("pat-signin", "g-2", email="pat@example.com")
    linked = _google(app_client, "pat-signin")
    assert (linked.json()["created"], linked.json()["id"]) == (False, pat_id)
    assert app_client.get("/me", headers=_bearer(linked)).json()["providers"] == ["google"]

    google.add("fresh", "g-1", email="gina@example.com")
    deleted = app_client.request(
        "DELETE", "/me", json={"provider": "google", "token": "fresh"}, headers=gina
    )
    assert deleted.status_code == 204
    assert app_client.get("/me", headers=gina).status_code == 401
