import asyncio
from datetime import datetime, timezone

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


class _DeletingPipeline:
    """Writes an output, and the job's owner deletes the account mid-run."""

    def __init__(self, store, job_id_holder):
        self._store = store
        self._holder = job_id_holder

    async def run(self, faces, prompt, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        self._store.delete(self._holder["id"])


async def test_job_deleted_mid_run_leaves_no_output(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    holder = {}
    holder["id"] = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, _DeletingPipeline(store, holder))

    assert store.get(holder["id"]) is None
    assert not (tmp_path / "outputs" / f"{holder['id']}.png").exists()


class _PartialThenFailPipeline:
    """Writes a partial output, then the owner deletes the account, then it fails."""

    def __init__(self, store, holder):
        self._store = store
        self._holder = holder

    async def run(self, faces, prompt, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"partial")
        self._store.delete(self._holder["id"])
        raise RuntimeError("intentional failure")


async def test_failed_job_deleted_mid_run_leaves_no_output(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    holder = {}
    holder["id"] = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, _PartialThenFailPipeline(store, holder))

    assert not (tmp_path / "outputs" / f"{holder['id']}.png").exists()


class _CountingPipeline:
    def __init__(self):
        self.runs = 0

    async def run(self, faces, prompt, output_path):
        self.runs += 1


async def test_job_whose_owner_is_gone_is_dropped_without_running(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    orphan = store.create(Job(id="", prompt="p", user_id="gone"))
    kept = store.create(Job(id="", prompt="p", user_id="here"))
    file_storage.save_upload(orphan, 0, b"face", str(tmp_path))
    pipeline = _CountingPipeline()

    task = asyncio.create_task(
        run_worker(store, pipeline, settings, lambda user_id: user_id == "here")
    )
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert store.get(orphan) is None
    assert not (tmp_path / "inputs" / orphan).exists()
    assert store.get(kept).status == JobStatus.succeeded
    assert pipeline.runs == 1


async def _run_with_refund(tmp_path, pipeline, grant_bonus_credit=False):
    from image_edit_server.repos.user_store import SqliteUserStore
    from tests.helpers import grant_bonus

    users = SqliteUserStore(":memory:")
    user = users.create_user("ana@example.com", "hash")
    if grant_bonus_credit:
        grant_bonus(users, user.id, 1)
        for _ in range(3):
            users.reserve_generation(user.id, 3, datetime.now(timezone.utc))
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    reservation = users.reserve_generation(user.id, 3, datetime.now(timezone.utc))
    store.create(Job(id="", prompt="p", user_id=user.id, reservation_id=reservation))

    task = asyncio.create_task(
        run_worker(store, pipeline, settings, refund=users.refund_generation)
    )
    await asyncio.sleep(0.4)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return users, user


async def test_failed_job_restores_the_daily_generation(tmp_path):
    users, user = await _run_with_refund(tmp_path, _FailingPipeline())

    assert users.usage_snapshot(user.id, 3, datetime.now(timezone.utc)).used_today == 0


async def test_succeeded_job_is_not_refunded(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    users, user = await _run_with_refund(tmp_path, StubPipeline())

    assert users.usage_snapshot(user.id, 3, datetime.now(timezone.utc)).used_today == 1


async def test_failed_job_paid_with_a_bonus_credit_restores_the_credit(tmp_path):
    users, user = await _run_with_refund(
        tmp_path, _FailingPipeline(), grant_bonus_credit=True
    )

    snapshot = users.usage_snapshot(user.id, 3, datetime.now(timezone.utc))
    assert snapshot.bonus_credits == 1
