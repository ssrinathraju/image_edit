"""Register → generate → fetch image → delete account → everything is gone."""
import io
import time

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import DEFAULT_PASSWORD, RecordingSender, register_headers
from tests.integration.test_generation_flow import SMALL_PNG


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def app_client(tmp_path, templates_dir, sender):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    with TestClient(create_app(settings=settings, sender=sender)) as client:
        yield client


def _generate(client, headers) -> dict:
    resp = client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("face.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=headers,
    )
    job_id = resp.json()["job_id"]
    for _ in range(40):
        body = client.get(f"/generations/{job_id}", headers=headers).json()
        if body["status"] in ("succeeded", "failed"):
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def test_deleting_the_account_removes_sessions_login_and_images(app_client, sender, tmp_path):
    headers = register_headers(app_client, "ana@example.com", consent=True)
    body = _generate(app_client, headers)
    assert body["status"] == "succeeded"
    assert app_client.get(body["result_url"]).status_code == 200

    resp = app_client.request(
        "DELETE", "/me", json={"password": DEFAULT_PASSWORD}, headers=headers
    )

    assert resp.status_code == 204
    assert app_client.get("/me", headers=headers).status_code == 401
    login = app_client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 401
    assert app_client.get(body["result_url"]).status_code == 404
