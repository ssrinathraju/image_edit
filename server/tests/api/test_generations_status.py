import pytest

from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.job import Job, JobStatus


def test_queued_job_status(client, store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)

    resp = client.get(f"/generations/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"


def test_running_job_status(client, store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.running)

    resp = client.get(f"/generations/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_succeeded_job_returns_result_url(client, store):
    job = Job(id="", prompt="test")
    job_id = store.create(job)
    store.update(job_id, status=JobStatus.succeeded, result_url=f"/images/{job_id}.png")

    resp = client.get(f"/generations/{job_id}")
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "succeeded"
    assert body["result_url"] == f"/images/{job_id}.png"


def test_failed_job_returns_error(client, store):
    job = Job(id="", prompt="test")
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
