from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.services.safety.safety_service import SafetyService, log_safety_event

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _call_safely(action: Callable[[str], object], argument: str, what: str) -> bool:
    """Run a bookkeeping call that must never take the worker down with it."""
    try:
        action(argument)
        return True
    except Exception:
        logger.exception("Worker bookkeeping failed: %s (%s)", what, argument)
        return False


async def run_worker(
    store: JobStore,
    pipeline: GenerationPipeline,
    settings: Settings,
    safety: SafetyService,
    user_exists: Optional[Callable[[str], bool]] = None,
    refund: Optional[Callable[[str], None]] = None,
    settle: Optional[Callable[[str], None]] = None,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """Pull queued jobs and process them one at a time. Runs until cancelled."""
    while True:
        jobs = list(store.list_queued())
        if not jobs:
            await asyncio.sleep(0.5)
            continue

        job = jobs[0]
        job_id = job.id
        if user_exists is not None and not _owner_exists(user_exists, job.user_id):
            # The owner deleted their account after submitting; drop the job.
            store.delete(job_id)
            file_storage.delete_inputs(job_id, settings.STORAGE_ROOT)
            logger.info("Dropped job %s: its owner no longer exists", job_id)
            continue
        store.update(job_id, status=JobStatus.running)
        logger.info("Processing job %s", job_id)

        out_path = Path(settings.STORAGE_ROOT) / "outputs" / f"{job_id}.png"
        staged_path = file_storage.staging_path(job_id, settings.STORAGE_ROOT)
        face_paths = [Path(p) for p in job.face_paths]

        try:
            await pipeline.run(face_paths, job.prompt, staged_path)
            if store.get(job_id) is None:
                logger.info("Job %s was deleted while running; output discarded", job_id)
                continue
            verdict = await _check_output(staged_path, safety)
            if store.get(job_id) is None:
                logger.info("Job %s was deleted while running; output discarded", job_id)
                continue
            if verdict is _Verdict.safe:
                promoted = file_storage.promote_staged_output(job_id, settings.STORAGE_ROOT)
                finished_at = clock()
                store.update(
                    job_id,
                    status=JobStatus.succeeded,
                    result_url=f"/images/{job_id}.png",
                    finished_at=finished_at,
                    expires_at=_expiry_of(promoted, job_id, finished_at, settings),
                )
                logger.info("Job %s succeeded", job_id)
                if settle is not None and job.reservation_id:
                    _call_safely(settle, job.reservation_id, "settle generation")
                continue
            _fail_blocked_output(job, verdict, store, safety, refund, clock)
        except Exception:
            logger.exception("Job %s failed", job_id)
            store.update(
                job_id,
                status=JobStatus.failed,
                error="pipeline_failed",
                finished_at=clock(),
            )
            if refund is not None and job.reservation_id:
                _call_safely(refund, job.reservation_id, "refund generation")
        finally:
            file_storage.delete_inputs(job_id, settings.STORAGE_ROOT)
            file_storage.delete_staged(job_id, settings.STORAGE_ROOT)
            if store.get(job_id) is None:
                # Owner deleted the account mid-run; never leave an output behind,
                # whether the pipeline succeeded, failed, or wrote a partial file.
                out_path.unlink(missing_ok=True)


def _expiry_of(promoted: Path, job_id: str, finished_at: datetime, settings: Settings) -> datetime:
    """The sweep ages images by mtime, so expiry is mtime plus retention."""
    retention = timedelta(hours=settings.OUTPUT_RETENTION_HOURS)
    try:
        return datetime.fromtimestamp(promoted.stat().st_mtime, timezone.utc) + retention
    except OSError:
        logger.warning("expires_at_fallback job=%s", job_id)
        return finished_at + retention


class _Verdict(Enum):
    safe = "safe"
    flagged = "content_blocked"
    check_failed = "safety_check_failed"


async def _check_output(staged_path: Path, safety: SafetyService) -> _Verdict:
    """Fails closed: any error reading or scoring the image is a failed check, not a pass."""
    try:
        image_bytes = await asyncio.to_thread(staged_path.read_bytes)
        flagged = await safety.is_output_flagged(image_bytes)
    except Exception:
        logger.exception("Output safety check errored for %s", staged_path.stem)
        return _Verdict.check_failed
    return _Verdict.flagged if flagged else _Verdict.safe


def _fail_blocked_output(
    job: Job,
    verdict: _Verdict,
    store: JobStore,
    safety: SafetyService,
    refund: Optional[Callable[[str], None]],
    clock: Callable[[], datetime],
) -> None:
    store.update(
        job.id, status=JobStatus.failed, error=verdict.value, finished_at=clock()
    )
    log_safety_event(
        "output_blocked" if verdict is _Verdict.flagged else "safety_check_failed",
        job.user_id,
        job.id,
    )
    if refund is not None and job.reservation_id:
        _call_safely(refund, job.reservation_id, "refund generation")
    if verdict is _Verdict.flagged:
        _call_safely(safety.record_strike, job.user_id, "record strike")


def _owner_exists(user_exists: Callable[[str], bool], user_id: str) -> bool:
    """A failing lookup counts as "exists": better to run a job than to drop it."""
    try:
        return user_exists(user_id)
    except Exception:
        logger.exception("Worker bookkeeping failed: owner lookup (%s)", user_id)
        return True
