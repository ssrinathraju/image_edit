"""Generate, age the result past retention, sweep, and check everything 404s."""
import asyncio
import io
import os
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from image_edit_server.api.generations import get_store
from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from image_edit_server.repos import file_storage
from image_edit_server.services.retention_service import sweep
from tests.helpers import register_headers
from tests.integration.test_generation_flow import SMALL_PNG


def _generate(client, headers) -> dict:
    resp = client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", io.BytesIO(SMALL_PNG), "image/png"))],
        headers=headers,
    )
    job_id = resp.json()["job_id"]
    for _ in range(50):
        body = client.get(f"/generations/{job_id}", headers=headers).json()
        if body["status"] == "succeeded":
            return body
        time.sleep(0.1)
    raise AssertionError("job did not finish")


def _run_sweep(store, settings):
    # A private loop: asyncio.run() would unset the main thread's loop and
    # break every later test on this Python.
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(sweep(store, settings, datetime.now(timezone.utc)))
    finally:
        loop.close()


def _age(path, hours):
    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def test_expired_result_and_its_job_disappear_but_a_young_one_stays(tmp_path, templates_dir):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    app = create_app(settings)
    with TestClient(app) as client:
        headers = register_headers(client, "ana@example.com")
        old, young = _generate(client, headers), _generate(client, headers)
        assert client.get(old["result_url"]).status_code == 200
        _age(file_storage.output_path(old["job_id"], str(tmp_path)), hours=25)

        store = app.dependency_overrides[get_store]()
        _run_sweep(store, settings)

        assert client.get(old["result_url"]).status_code == 404
        gone = client.get(f"/generations/{old['job_id']}", headers=headers)
        assert gone.status_code == 404
        assert client.get(young["result_url"]).status_code == 200
        kept = client.get(f"/generations/{young['job_id']}", headers=headers)
        assert kept.status_code == 200
        assert kept.json()["status"] == "succeeded"


def test_leftover_faces_are_removed_when_the_app_restarts(tmp_path, templates_dir):
    settings = Settings(STORAGE_ROOT=str(tmp_path), TEMPLATES_DIR=str(templates_dir))
    leftover = file_storage.save_upload("died-with-the-server", 0, b"face", str(tmp_path))
    assert leftover.exists()

    with TestClient(create_app(settings)):
        pass

    assert not file_storage.input_dir("died-with-the-server", str(tmp_path)).exists()
