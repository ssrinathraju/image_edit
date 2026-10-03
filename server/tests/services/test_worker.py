import asyncio
import pytest
from pathlib import Path

from image_edit_server.configs.settings import Settings
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.services.worker import run_worker


class _FailingPipeline:
    async def run(self, faces, prompt, output_path):
        raise RuntimeError("intentional failure")


async def _drain(store, settings, pipeline, timeout=2.0):
    """Run the worker until all queued jobs are terminal, then cancel."""
    task = asyncio.create_task(run_worker(store, pipeline, settings))
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        jobs = list(store.list_queued())
        running = [j for j in [store.get(j.id) for j in jobs] if j and j.status == JobStatus.running]
        if not jobs and not running:
            break
        await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_successful_job(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job = Job(id="", prompt="sunset")
    job_id = store.create(job)

    await _drain(store, settings, StubPipeline())

    result = store.get(job_id)
    assert result.status == JobStatus.succeeded
    assert result.result_url == f"/images/{job_id}.png"
    assert not (tmp_path / "inputs" / job_id).exists()


async def test_failed_job_cleans_up_inputs(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job = Job(id="", prompt="sunset")
    job_id = store.create(job)

    # Save a fake input so we can verify it gets deleted
    file_storage.save_upload(job_id, 0, b"face", str(tmp_path))
    assert (tmp_path / "inputs" / job_id).exists()

    await _drain(store, settings, _FailingPipeline())

    result = store.get(job_id)
    assert result.status == JobStatus.failed
    assert result.error == "pipeline_failed"
    assert not (tmp_path / "inputs" / job_id).exists()
