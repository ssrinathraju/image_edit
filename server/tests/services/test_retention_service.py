import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.repos import file_storage
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.services import retention_service
from image_edit_server.services.retention_service import run_retention, sweep

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
HOUR = 3600


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(STORAGE_ROOT=str(tmp_path), OUTPUT_RETENTION_HOURS=24)


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()


def _output(settings, job_id: str, age_hours: float):
    path = file_storage.output_path(job_id, settings.STORAGE_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    stamp = NOW.timestamp() - age_hours * HOUR
    os.utime(path, (stamp, stamp))
    return path


def _job(store, status=JobStatus.succeeded) -> str:
    job_id = store.create(Job(id="", prompt="p"))
    store.update(job_id, status=status)
    return job_id


async def test_old_image_is_deleted_and_a_young_one_kept(settings, store):
    old = _output(settings, "old", age_hours=25)
    young = _output(settings, "young", age_hours=23)

    result = await sweep(store, settings, NOW)

    assert not old.exists()
    assert young.exists()
    assert result.outputs_removed == 1


async def test_an_image_exactly_at_the_limit_is_deleted(settings, store):
    at_limit = _output(settings, "edge", age_hours=24)

    await sweep(store, settings, NOW)

    assert not at_limit.exists()


async def test_the_job_record_of_an_expired_terminal_job_is_removed(settings, store):
    ok_id, failed_id = _job(store), _job(store, JobStatus.failed)
    _output(settings, ok_id, 30)
    _output(settings, failed_id, 30)

    result = await sweep(store, settings, NOW)

    assert store.get(ok_id) is None
    assert store.get(failed_id) is None
    assert result.job_records_removed == 2


async def test_a_non_expired_image_keeps_its_job(settings, store):
    job_id = _job(store)
    path = _output(settings, job_id, 1)

    await sweep(store, settings, NOW)

    assert path.exists()
    assert store.get(job_id).status == JobStatus.succeeded


@pytest.mark.parametrize("status", [JobStatus.queued, JobStatus.running])
async def test_a_live_job_and_its_file_are_left_untouched(settings, store, status):
    job_id = _job(store, status)
    path = _output(settings, job_id, 48)

    await sweep(store, settings, NOW)

    assert path.exists()
    assert store.get(job_id) is not None


async def test_an_expired_image_with_no_job_is_deleted(settings, store):
    path = _output(settings, "no-job-any-more", 100)

    await sweep(store, settings, NOW)

    assert not path.exists()


async def test_non_png_files_and_symlinks_are_left_alone(settings, store, tmp_path):
    outputs = tmp_path / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    note = outputs / "README.txt"
    note.write_text("keep me")
    target = tmp_path / "precious.png"
    target.write_bytes(b"x")
    stamp = NOW.timestamp() - 100 * HOUR
    os.utime(note, (stamp, stamp))
    os.utime(target, (stamp, stamp))
    (outputs / "link.png").symlink_to(target)

    await sweep(store, settings, NOW)

    assert note.exists()
    assert target.exists()
    assert (outputs / "link.png").is_symlink()


async def test_faces_of_a_vanished_job_are_deleted(settings, store):
    file_storage.save_upload("lost-job", 0, b"face", settings.STORAGE_ROOT)

    result = await sweep(store, settings, NOW)

    assert not file_storage.input_dir("lost-job", settings.STORAGE_ROOT).exists()
    assert result.input_folders_removed == 1


async def test_faces_of_a_live_job_are_kept(settings, store):
    job_id = _job(store, JobStatus.queued)
    file_storage.save_upload(job_id, 0, b"face", settings.STORAGE_ROOT)

    await sweep(store, settings, NOW)

    assert file_storage.input_dir(job_id, settings.STORAGE_ROOT).exists()


async def test_one_failing_delete_does_not_stop_the_rest(settings, store, monkeypatch):
    first = _output(settings, "a-first", 30)
    second = _output(settings, "b-second", 30)
    real_delete = file_storage.delete_output

    def flaky(job_id, storage_root=None):
        if job_id == "a-first":
            raise OSError("permission denied")
        real_delete(job_id, storage_root)

    monkeypatch.setattr(retention_service.file_storage, "delete_output", flaky)

    result = await sweep(store, settings, NOW)

    assert first.exists()
    assert not second.exists()
    assert (result.outputs_removed, result.errors) == (1, 1)


async def test_a_large_backlog_is_cleared_in_batches(settings, store):
    for i in range(450):
        _output(settings, f"old-{i:03d}", 48)

    result = await sweep(store, settings, NOW)

    assert result.outputs_removed == 450
    assert file_storage.list_output_files(settings.STORAGE_ROOT) == []


async def test_a_clean_pass_reports_zeroes(settings, store):
    result = await sweep(store, settings, NOW)

    assert result == retention_service.SweepResult()


# ── run_retention ───────────────────────────────────────────────────────────


async def test_a_failing_pass_does_not_end_the_loop(settings, store, monkeypatch):
    calls: list = []

    async def flaky_sweep(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("disk on fire")

    monkeypatch.setattr(retention_service, "sweep", flaky_sweep)
    sleeps: list = []
    real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        sleeps.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr(retention_service.asyncio, "sleep", fast_sleep)

    task = asyncio.create_task(run_retention(store, settings, lambda: NOW))
    for _ in range(20):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 2
    assert set(sleeps) == {settings.RETENTION_SWEEP_MINUTES * 60}


async def test_the_sleep_interval_comes_from_settings(tmp_path, store, monkeypatch):
    custom = Settings(STORAGE_ROOT=str(tmp_path), RETENTION_SWEEP_MINUTES=7)
    sleeps: list = []

    async def record_then_stop(seconds):
        sleeps.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(retention_service.asyncio, "sleep", record_then_stop)

    with pytest.raises(asyncio.CancelledError):
        await run_retention(store, custom, lambda: NOW)

    assert sleeps == [7 * 60]


async def test_cancelling_the_loop_stops_it_cleanly(settings, store):
    task = asyncio.create_task(run_retention(store, settings))
    await asyncio.sleep(0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


async def test_an_unreadable_outputs_folder_does_not_block_face_cleanup(
    settings, store, monkeypatch
):
    file_storage.save_upload("lost-job", 0, b"face", settings.STORAGE_ROOT)

    def unreadable(storage_root=None):
        raise PermissionError("outputs/ is not readable")

    monkeypatch.setattr(retention_service.file_storage, "list_output_files", unreadable)

    result = await sweep(store, settings, NOW)

    assert not file_storage.input_dir("lost-job", settings.STORAGE_ROOT).exists()
    assert (result.input_folders_removed, result.errors) == (1, 1)


async def test_an_unreadable_inputs_folder_does_not_block_image_expiry(
    settings, store, monkeypatch
):
    old = _output(settings, "old", age_hours=30)

    def unreadable(storage_root=None):
        raise PermissionError("inputs/ is not readable")

    monkeypatch.setattr(retention_service.file_storage, "list_input_job_ids", unreadable)

    result = await sweep(store, settings, NOW)

    assert not old.exists()
    assert (result.outputs_removed, result.errors) == (1, 1)


async def test_both_folders_unreadable_is_survivable(settings, store, monkeypatch):
    def unreadable(storage_root=None):
        raise PermissionError("denied")

    monkeypatch.setattr(retention_service.file_storage, "list_output_files", unreadable)
    monkeypatch.setattr(retention_service.file_storage, "list_input_job_ids", unreadable)

    result = await sweep(store, settings, NOW)

    assert result.errors == 2
    assert result.outputs_removed == result.input_folders_removed == 0
