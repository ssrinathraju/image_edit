import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.repos import file_storage
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.services import report_retention
from image_edit_server.services.report_retention import run_report_retention, sweep_reports
from image_edit_server.services.retention_service import sweep

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
DAY = timedelta(days=1)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(STORAGE_ROOT=str(tmp_path), REPORT_RETENTION_DAYS=30, OUTPUT_RETENTION_HOURS=24)


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def user(users):
    return users.create_user("ana@example.com", "hash")


def _report(users, user, settings, report_id, age_days, with_image=True):
    name = f"{report_id}.png" if with_image else None
    if with_image:
        file_storage.save_report_image(name, b"png", settings.STORAGE_ROOT)
    users.add_report(
        report_id, user.id, "job", "other", "", "device" if with_image else "none",
        name, NOW - age_days * DAY, 1000,
    )
    return file_storage.report_image_path(f"{report_id}.png", settings.STORAGE_ROOT)


async def test_a_31_day_old_report_and_its_image_are_removed(users, user, settings):
    image = _report(users, user, settings, "old", 31)

    result = await sweep_reports(users, settings, NOW)

    assert users.get_report("old") is None
    assert not image.exists()
    assert result.reports_removed == 1


async def test_a_29_day_old_report_is_kept(users, user, settings):
    image = _report(users, user, settings, "young", 29)

    await sweep_reports(users, settings, NOW)

    assert users.get_report("young") is not None
    assert image.exists()


async def test_a_resolved_old_report_is_removed_too(users, user, settings):
    image = _report(users, user, settings, "done", 40)
    users.resolve_report("done", "removed", NOW)

    await sweep_reports(users, settings, NOW)

    assert users.get_report("done") is None
    assert not image.exists()


async def test_an_old_report_without_an_image_is_removed(users, user, settings):
    _report(users, user, settings, "bare", 31, with_image=False)

    await sweep_reports(users, settings, NOW)

    assert users.get_report("bare") is None


async def test_the_retention_period_comes_from_settings(users, user, tmp_path):
    short = Settings(STORAGE_ROOT=str(tmp_path), REPORT_RETENTION_DAYS=2)
    _report(users, user, short, "a", 3)

    await sweep_reports(users, short, NOW)

    assert users.get_report("a") is None


async def test_a_reported_image_survives_the_24_hour_output_sweep(users, user, settings):
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="p", user_id=user.id))
    store.update(job_id, status=JobStatus.succeeded)
    output = file_storage.output_path(job_id, settings.STORAGE_ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"png")
    stamp = NOW.timestamp() - 48 * 3600
    os.utime(output, (stamp, stamp))
    file_storage.copy_output_to_report(job_id, "r1.png", settings.STORAGE_ROOT)
    users.add_report("r1", user.id, job_id, "other", "", "server", "r1.png", NOW - timedelta(hours=40), 20)

    await sweep(store, settings, NOW)

    assert not output.exists()
    reported = file_storage.report_image_path("r1.png", settings.STORAGE_ROOT)
    assert reported.read_bytes() == b"png"
    assert users.get_report("r1") is not None


async def test_an_image_with_no_report_is_removed_once_past_the_grace_period(users, user, settings):
    orphan = file_storage.report_image_path("orphan.png", settings.STORAGE_ROOT)
    fresh = file_storage.report_image_path("fresh.png", settings.STORAGE_ROOT)
    file_storage.save_report_image("orphan.png", b"x", settings.STORAGE_ROOT)
    file_storage.save_report_image("fresh.png", b"x", settings.STORAGE_ROOT)
    os.utime(orphan, (NOW.timestamp() - 7200, NOW.timestamp() - 7200))
    os.utime(fresh, (NOW.timestamp() - 60, NOW.timestamp() - 60))
    kept = _report(users, user, settings, "kept", 1)
    os.utime(kept, (NOW.timestamp() - 7200, NOW.timestamp() - 7200))

    result = await sweep_reports(users, settings, NOW)

    assert not orphan.exists()
    assert fresh.exists() and kept.exists()
    assert result.orphan_images_removed == 1


async def test_one_failing_report_does_not_stop_the_sweep(users, user, settings, monkeypatch, caplog):
    first = _report(users, user, settings, "a-bad", 31)
    second = _report(users, user, settings, "b-good", 31)
    real_delete = file_storage.delete_report_image

    def flaky_delete(name, root=None):
        if name == "a-bad.png":
            raise OSError("disk on fire")
        real_delete(name, root)

    monkeypatch.setattr(file_storage, "delete_report_image", flaky_delete)

    result = await sweep_reports(users, settings, NOW)

    assert users.get_report("b-good") is None
    assert not second.exists()
    assert users.get_report("a-bad") is not None
    assert result.errors == 1
    assert "Could not expire report a-bad" in caplog.text


async def test_a_failing_pass_does_not_end_the_loop(users, settings, monkeypatch):
    calls = []

    async def flaky(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("disk on fire")

    monkeypatch.setattr(report_retention, "sweep_reports", flaky)
    real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await real_sleep(0)

    monkeypatch.setattr(report_retention.asyncio, "sleep", fast_sleep)

    task = asyncio.create_task(run_report_retention(users, settings, lambda: NOW))
    for _ in range(20):
        await real_sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 2
