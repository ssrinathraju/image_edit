import io
import time

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.api.test_generations_quota import PNG
from tests.helpers import FakeClassifier, RecordingSender, register_headers

DEADLINE_SECONDS = 10


def _app(tmp_path, templates_dir, monkeypatch, output_classifier):
    monkeypatch.setattr(
        "image_edit_server.main._make_classifiers",
        lambda cfg: (FakeClassifier(), output_classifier),
    )
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    return create_app(settings, sender=RecordingSender())


def _submit(client, headers):
    resp = client.post(
        "/generations",
        data={"prompt": "a calm lake"},
        files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))],
        headers=headers,
    )
    assert resp.status_code == 202, resp.text
    return resp.json()["job_id"]


def _wait_for_terminal(client, headers, job_id, during=None):
    deadline = time.time() + DEADLINE_SECONDS
    while time.time() < deadline:
        body = client.get(f"/generations/{job_id}", headers=headers).json()
        if during is not None:
            during(body)
        if body["status"] in ("succeeded", "failed"):
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish in time")


def test_a_flagged_image_is_never_fetchable_even_while_it_is_being_checked(
    tmp_path, templates_dir, monkeypatch
):
    slow_flagging = FakeClassifier(score=0.95, delay=0.6)
    fetched = []

    with TestClient(_app(tmp_path, templates_dir, monkeypatch, slow_flagging)) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        job_id = _submit(client, headers)

        body = _wait_for_terminal(
            client,
            headers,
            job_id,
            during=lambda _body: fetched.append(client.get(f"/images/{job_id}.png").status_code),
        )
        final_fetch = client.get(f"/images/{job_id}.png")
        usage = client.get("/me", headers=headers).json()["usage"]

    assert body["status"] == "failed" and body["error"] == "content_blocked"
    assert len(fetched) > 1
    assert set(fetched) == {404}
    assert final_fetch.status_code == 404
    assert usage["remaining"] == 3
    assert not list((tmp_path / "s" / "staging").glob("*"))


def test_a_safe_image_is_served_once_the_job_succeeds(tmp_path, templates_dir, monkeypatch):
    with TestClient(_app(tmp_path, templates_dir, monkeypatch, FakeClassifier(0.0))) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        job_id = _submit(client, headers)

        body = _wait_for_terminal(client, headers, job_id)
        image = client.get(f"/images/{job_id}.png")

    assert body["status"] == "succeeded"
    assert image.status_code == 200


def test_three_blocked_results_pause_the_account(tmp_path, templates_dir, monkeypatch):
    with TestClient(_app(tmp_path, templates_dir, monkeypatch, FakeClassifier(1.0))) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        for _ in range(3):
            _wait_for_terminal(client, headers, _submit(client, headers))

        resp = client.post(
            "/generations",
            data={"prompt": "a calm lake"},
            files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))],
            headers=headers,
        )

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "generation_suspended"


def test_startup_clears_leftover_staging_files(tmp_path, templates_dir, monkeypatch):
    staging = tmp_path / "s" / "staging"
    staging.mkdir(parents=True)
    (staging / "leftover.png").write_bytes(b"unchecked")

    with TestClient(_app(tmp_path, templates_dir, monkeypatch, FakeClassifier())):
        assert list(staging.iterdir()) == []
