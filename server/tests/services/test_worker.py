import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from pathlib import Path

from image_edit_server.configs.settings import Settings
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.core.safety import TermMatcher
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services.safety.safety_service import SafetyService
from image_edit_server.services.worker import run_worker
from tests.helpers import FakeClassifier


def _safety(users=None, output=None):
    return SafetyService(
        Settings(),
        users or SqliteUserStore(":memory:"),
        TermMatcher(["blockedword"]),
        FakeClassifier(),
        output or FakeClassifier(),
    )


class _FailingPipeline:
    async def run(self, faces, prompt, output_path):
        raise RuntimeError("intentional failure")


async def _drain(store, settings, pipeline, timeout=2.0, **worker_kwargs):
    """Run the worker until all queued jobs are terminal, then cancel."""
    worker_kwargs.setdefault("safety", _safety())
    task = asyncio.create_task(run_worker(store, pipeline, settings, **worker_kwargs))
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
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")


async def test_job_whose_owner_is_gone_is_dropped_without_running(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    orphan = store.create(Job(id="", prompt="p", user_id="gone"))
    kept = store.create(Job(id="", prompt="p", user_id="here"))
    file_storage.save_upload(orphan, 0, b"face", str(tmp_path))
    pipeline = _CountingPipeline()

    task = asyncio.create_task(
        run_worker(store, pipeline, settings, _safety(), lambda user_id: user_id == "here")
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
        run_worker(store, pipeline, settings, _safety(users), refund=users.refund_generation)
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


async def _run_for(store, pipeline, settings, seconds=0.5, **callbacks):
    callbacks.setdefault("safety", _safety())
    task = asyncio.create_task(run_worker(store, pipeline, settings, **callbacks))
    await asyncio.sleep(seconds)
    died = task.done()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    return died


class _FailOnceThenSucceed:
    def __init__(self):
        self.calls = 0

    async def run(self, faces, prompt, output_path):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("first job fails")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")


async def test_a_refund_that_raises_does_not_kill_the_worker(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    first = store.create(Job(id="", prompt="p", reservation_id="r1"))
    second = store.create(Job(id="", prompt="p", reservation_id="r2"))

    def locked_refund(_reservation_id):
        raise RuntimeError("database is locked")

    died = await _run_for(
        store, _FailOnceThenSucceed(), settings, refund=locked_refund
    )

    assert not died
    assert store.get(first).status == JobStatus.failed
    assert store.get(second).status == JobStatus.succeeded


async def test_a_failing_owner_lookup_does_not_kill_the_worker(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="p", user_id="u1"))

    def broken_lookup(_user_id):
        raise RuntimeError("database is locked")

    died = await _run_for(
        store, StubPipeline(), settings, user_exists=broken_lookup
    )

    assert not died
    assert store.get(job_id).status == JobStatus.succeeded


async def test_a_failing_settle_does_not_fail_the_job(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="p", reservation_id="r1"))

    def broken_settle(_reservation_id):
        raise RuntimeError("database is locked")

    await _run_for(store, StubPipeline(), settings, settle=broken_settle)

    assert store.get(job_id).status == JobStatus.succeeded


async def test_success_settles_the_reservation(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    store.create(Job(id="", prompt="p", reservation_id="r1"))
    settled: list = []

    await _run_for(store, StubPipeline(), settings, settle=settled.append)

    assert settled == ["r1"]


FINISH_TIME = datetime(2026, 10, 20, 9, 30, tzinfo=timezone.utc)


async def test_a_succeeded_job_records_when_it_finished(tmp_path):
    from image_edit_server.services.pipelines.stub import StubPipeline

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, StubPipeline(), clock=lambda: FINISH_TIME)

    assert store.get(job_id).status == JobStatus.succeeded
    assert store.get(job_id).finished_at == FINISH_TIME


async def test_a_failed_job_records_when_it_finished(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, _FailingPipeline(), clock=lambda: FINISH_TIME)

    assert store.get(job_id).status == JobStatus.failed
    assert store.get(job_id).finished_at == FINISH_TIME


async def test_a_job_that_has_not_finished_has_no_finish_time(tmp_path):
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))

    assert store.get(job_id).finished_at is None


# ── output screening ──


async def _screened_run(tmp_path, output_classifier, pipeline=None, strike_hook=None):
    """One job for a real account, with its reservation, through a worker that screens outputs."""
    from image_edit_server.services.pipelines.stub import StubPipeline

    users = SqliteUserStore(":memory:")
    user = users.create_user("ana@example.com", "hash")
    safety = _safety(users, output_classifier)
    if strike_hook is not None:
        safety.record_strike = strike_hook
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    reservation = users.reserve_generation(user.id, 3, datetime.now(timezone.utc))
    job_id = store.create(
        Job(id="", prompt="p", user_id=user.id, reservation_id=reservation)
    )
    await _drain(
        store, settings, pipeline or StubPipeline(), safety=safety,
        refund=users.refund_generation, settle=users.settle_generation,
    )
    return store, job_id, users, user


def _usage(users, user) -> int:
    return users.usage_snapshot(user.id, 3, datetime.now(timezone.utc)).used_today


def _strikes_of(users, user) -> int:
    return users._conn.execute(
        "SELECT COUNT(*) FROM safety_strikes WHERE user_id = ?", (user.id,)
    ).fetchone()[0]


async def test_a_safe_output_succeeds_lands_in_outputs_and_leaves_no_staging(tmp_path):
    store, job_id, users, user = await _screened_run(tmp_path, FakeClassifier(0.1))

    assert store.get(job_id).status == JobStatus.succeeded
    assert (tmp_path / "outputs" / f"{job_id}.png").is_file()
    assert not (tmp_path / "staging" / f"{job_id}.png").exists()
    assert _usage(users, user) == 1


async def test_a_flagged_output_fails_is_deleted_refunded_and_struck(tmp_path):
    store, job_id, users, user = await _screened_run(tmp_path, FakeClassifier(0.95))

    job = store.get(job_id)
    assert (job.status, job.error) == (JobStatus.failed, "content_blocked")
    assert job.result_url is None and job.finished_at is not None
    assert not (tmp_path / "outputs" / f"{job_id}.png").exists()
    assert not (tmp_path / "staging" / f"{job_id}.png").exists()
    assert _usage(users, user) == 0
    assert _strikes_of(users, user) == 1


async def test_a_classifier_error_fails_closed_with_a_refund_and_no_strike(tmp_path):
    broken = FakeClassifier()
    broken.error = RuntimeError("model crashed")

    store, job_id, users, user = await _screened_run(tmp_path, broken)

    job = store.get(job_id)
    assert (job.status, job.error) == (JobStatus.failed, "safety_check_failed")
    assert not (tmp_path / "outputs" / f"{job_id}.png").exists()
    assert not (tmp_path / "staging" / f"{job_id}.png").exists()
    assert _usage(users, user) == 0
    assert _strikes_of(users, user) == 0


async def test_a_flagged_output_is_not_settled(tmp_path):
    store, job_id, users, user = await _screened_run(tmp_path, FakeClassifier(0.95))

    assert _usage(users, user) == 0
    assert users.refund_unsettled_generations() == 0


async def test_a_raising_record_strike_does_not_stop_the_worker(tmp_path):
    def locked(_user_id):
        raise RuntimeError("database is locked")

    class _FlaggedThenSafe(FakeClassifier):
        def score(self, image_bytes):
            self.seen.append(image_bytes)
            return 0.95 if len(self.seen) == 1 else 0.0

    class _Writes:
        async def run(self, faces, prompt, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"png")

    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    first = store.create(Job(id="", prompt="p", reservation_id="r1"))
    second = store.create(Job(id="", prompt="p", reservation_id="r2"))
    safety = _safety(output=_FlaggedThenSafe())
    safety.record_strike = locked

    died = await _run_for(store, _Writes(), settings, safety=safety)

    assert not died
    assert store.get(first).error == "content_blocked"
    assert store.get(second).status == JobStatus.succeeded


async def test_a_job_deleted_during_the_check_leaves_no_files(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    holder = {"id": store.create(Job(id="", prompt="p"))}

    class _DeleteWhileChecking(FakeClassifier):
        def score(self, image_bytes):
            store.delete(holder["id"])
            return 0.0

    class _Writes:
        async def run(self, faces, prompt, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"png")

    await _drain(
        store, settings, _Writes(), safety=_safety(output=_DeleteWhileChecking())
    )

    assert not (tmp_path / "outputs").exists() or not list((tmp_path / "outputs").glob("*"))
    assert not list((tmp_path / "staging").glob("*"))


async def test_the_pipeline_writes_to_staging_not_to_outputs(tmp_path):
    seen = []

    class _Recording:
        async def run(self, faces, prompt, output_path):
            seen.append(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"png")

    await _screened_run(tmp_path, FakeClassifier(0.0), pipeline=_Recording())

    assert seen[0].parent == tmp_path / "staging"


def test_clearing_staging_removes_leftover_files(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "a.png").write_bytes(b"x")
    (staging / "b.png").write_bytes(b"x")

    assert file_storage.clear_staging(str(tmp_path)) == 2
    assert list(staging.iterdir()) == []
    assert file_storage.clear_staging(str(tmp_path / "missing")) == 0


WRITTEN_AT = datetime(2026, 10, 22, 10, 0, tzinfo=timezone.utc)


class _BackdatedPipeline:
    """Writes the staged image with a fixed mtime, as a slow pipeline would."""

    async def run(self, faces, prompt, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"png")
        os.utime(output_path, (WRITTEN_AT.timestamp(), WRITTEN_AT.timestamp()))


async def test_succeeded_job_expires_at_is_output_mtime_plus_retention(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path), OUTPUT_RETENTION_HOURS=48)
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, _BackdatedPipeline())

    assert store.get(job_id).expires_at == WRITTEN_AT + timedelta(hours=48)


async def test_expires_at_falls_back_to_finished_at_when_stat_fails(tmp_path, monkeypatch, caplog):
    settings = Settings(STORAGE_ROOT=str(tmp_path), OUTPUT_RETENTION_HOURS=48)
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))
    real_promote = file_storage.promote_staged_output

    def promote_and_hide(job_id, storage_root=None):
        real_promote(job_id, storage_root)
        return tmp_path / "missing.png"

    monkeypatch.setattr(file_storage, "promote_staged_output", promote_and_hide)
    finished = datetime(2026, 10, 22, 11, 0, tzinfo=timezone.utc)

    await _drain(store, settings, _BackdatedPipeline(), clock=lambda: finished)

    job = store.get(job_id)
    assert job.status == JobStatus.succeeded
    assert job.expires_at == finished + timedelta(hours=48)
    assert f"expires_at_fallback job={job_id}" in caplog.text


async def test_failed_job_has_no_expires_at(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))

    await _drain(store, settings, _FailingPipeline())

    assert store.get(job_id).expires_at is None


async def test_blocked_job_has_no_expires_at(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    store = InMemoryJobStore()
    job_id = store.create(Job(id="", prompt="sunset"))
    await _drain(
        store, settings, _BackdatedPipeline(), safety=_safety(output=FakeClassifier(0.95))
    )

    job = store.get(job_id)
    assert job.status == JobStatus.failed
    assert job.expires_at is None
