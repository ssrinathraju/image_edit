"""Forgot the password: request a reset, read the emailed code, sign back in."""
import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import (
    DEFAULT_PASSWORD,
    RecordingSender,
    forget_recent_sends,
    register_headers,
)

NEW_PASSWORD = "a brand new password"
EMAIL = "ana@example.com"


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def app_client(tmp_path, templates_dir, sender):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    with TestClient(create_app(settings, sender=sender)) as client:
        yield client


def test_register_reset_and_sign_in_with_the_new_password(app_client, sender):
    old_headers = register_headers(app_client, EMAIL)
    forget_recent_sends(app_client)

    assert app_client.post("/auth/password-reset/request", json={"email": EMAIL}).status_code == 202
    confirm = app_client.post(
        "/auth/password-reset/confirm",
        json={"email": EMAIL, "code": sender.last_code(EMAIL), "new_password": NEW_PASSWORD},
    )

    assert confirm.status_code == 200
    login = app_client.post("/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD})
    assert login.status_code == 200
    assert app_client.get("/me", headers=old_headers).status_code == 401
    old_login = app_client.post("/auth/login", json={"email": EMAIL, "password": DEFAULT_PASSWORD})
    assert old_login.status_code == 401
