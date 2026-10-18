"""Register → use the allowance → 429 → restart → still 429."""
import io
import time

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import RecordingSender, register_headers
from tests.integration.test_generation_flow import SMALL_PNG


def _submit(client, headers):
    return client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=headers,
    )


def test_limit_survives_a_server_restart(tmp_path, templates_dir):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))

    sender = RecordingSender()
    with TestClient(create_app(settings, sender=sender)) as first:
        headers = register_headers(first, "ana@example.com")
        responses = [_submit(first, headers) for _ in range(3)]
        assert [r.status_code for r in responses] == [202] * 3
        assert _submit(first, headers).status_code == 429
        # Let the jobs finish: a job lost to the restart would be refunded.
        for response in responses:
            job_id = response.json()["job_id"]
            for _ in range(50):
                status = first.get(f"/generations/{job_id}", headers=headers).json()
                if status["status"] == "succeeded":
                    break
                time.sleep(0.1)
            assert status["status"] == "succeeded"

    with TestClient(create_app(settings)) as second:
        resp = _submit(second, headers)
        me = second.get("/me", headers=headers).json()

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "quota_exceeded"
    assert me["usage"]["remaining"] == 0
