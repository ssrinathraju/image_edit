from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import JobStatus

logger = logging.getLogger(__name__)


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
    user_exists: Optional[Callable[[str], bool]] = None,
    refund: Optional[Callable[[str], None]] = None,
    settle: Optional[Callable[[str], None]] = None,
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
        face_paths = [Path(p) for p in job.face_paths]

        try:
            await pipeline.run(face_paths, job.prompt, out_path)
            if store.get(job_id) is None:
                logger.info("Job %s was deleted while running; output discarded", job_id)
                continue
            result_url = f"/images/{job_id}.png"
            store.update(job_id, status=JobStatus.succeeded, result_url=result_url)
            logger.info("Job %s succeeded", job_id)
            if settle is not None and job.reservation_id:
                _call_safely(settle, job.reservation_id, "settle generation")
        except Exception:
            logger.exception("Job %s failed", job_id)
            store.update(job_id, status=JobStatus.failed, error="pipeline_failed")
            if refund is not None and job.reservation_id:
                _call_safely(refund, job.reservation_id, "refund generation")
        finally:
            file_storage.delete_inputs(job_id, settings.STORAGE_ROOT)
            if store.get(job_id) is None:
                # Owner deleted the account mid-run; never leave an output behind,
                # whether the pipeline succeeded, failed, or wrote a partial file.
                out_path.unlink(missing_ok=True)


def _owner_exists(user_exists: Callable[[str], bool], user_id: str) -> bool:
    """A failing lookup counts as "exists": better to run a job than to drop it."""
    try:
        return user_exists(user_id)
    except Exception:
        logger.exception("Worker bookkeeping failed: owner lookup (%s)", user_id)
        return True
