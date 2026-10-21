from datetime import datetime, timezone

import pytest

from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.job import Job, JobStatus


def test_queued_job_status(client, store, user_id):
    job = Job(id="", prompt="test", user_id=user_id)
    job_id = store.create(job)

    resp = client.get(f"/generations/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_running_job_status(client, store, user_id):
    job = Job(id="", prompt="test", user_id=user_id)
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.running)

    resp = client.get(f"/generations/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_succeeded_job_returns_result_url(client, store, user_id):
    job = Job(id="", prompt="test", user_id=user_id)
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.succeeded, result_url=f"/images/{job_id}.png")

    resp = client.get(f"/generations/{job_id}")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "succeeded"
    assert body["result_url"] == f"/images/{job_id}.png"


def test_failed_job_returns_error(client, store, user_id):
    job = Job(id="", prompt="test", user_id=user_id)
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.failed, error="pipeline_failed")

    resp = client.get(f"/generations/{job_id}")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "failed"
    assert body["error"] == "pipeline_failed"


def test_unknown_job_returns_404(client):
    resp = client.get("/generations/does-not-exist")
    assert resp.status_code == 404


def test_status_without_token_is_401(anon_client, store, user_id):
    job_id = store.create(Job(id="", prompt="test", user_id=user_id))

    resp = anon_client.get(f"/generations/{job_id}")

    assert resp.status_code == 401


def test_other_users_job_is_404_not_403(client, store, second_user_headers):
    job_id = client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("f.png", b"x", "image/png"))],
    ).json()["job_id"]

    other = client.get(f"/generations/{job_id}", headers=second_user_headers)

    assert other.status_code == 404
    assert client.get(f"/generations/{job_id}").status_code == 200


def test_succeeded_job_reports_expires_at_in_utc_iso(client, store, user_id):
    job_id = store.create(Job(id="", prompt="test", user_id=user_id))
    expiry = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
    store.update(
        job_id,
        status=JobStatus.succeeded,
        result_url=f"/images/{job_id}.png",
        expires_at=expiry,
    )

    body = client.get(f"/generations/{job_id}").json()

    assert body["expires_at"] in ("2026-10-23T10:00:00Z", "2026-10-23T10:00:00+00:00")


@pytest.mark.parametrize("status", [JobStatus.queued, JobStatus.running, JobStatus.failed])
def test_unfinished_or_failed_job_has_null_expires_at(client, store, user_id, status):
    job_id = store.create(Job(id="", prompt="test", user_id=user_id))
    store.update(job_id, status=status)

    body = client.get(f"/generations/{job_id}").json()

    assert body["expires_at"] is None
