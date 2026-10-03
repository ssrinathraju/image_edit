from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import JobStatus

logger = logging.getLogger(__name__)


async def run_worker(
    store: JobStore,
    pipeline: GenerationPipeline,
    settings: Settings,
) -> None:
    """Pull queued jobs and process them one at a time. Runs until cancelled."""
    while True:
        jobs = list(store.list_queued())
        if not jobs:
            await asyncio.sleep(0.5)
            continue

        job = jobs[0]
        job_id = job.id
        store.update(job_id, status=JobStatus.running)
        logger.info("Processing job %s", job_id)

        out_path = Path(settings.STORAGE_ROOT) / "outputs" / f"{job_id}.png"
        face_paths = [Path(p) for p in job.face_paths]

        try:
            await pipeline.run(face_paths, job.prompt, out_path)
            result_url = f"/images/{job_id}.png"
            store.update(job_id, status=JobStatus.succeeded, result_url=result_url)
            logger.info("Job %s succeeded", job_id)
        except Exception:
            logger.exception("Job %s failed", job_id)
            store.update(job_id, status=JobStatus.failed, error="pipeline_failed")
        finally:
            file_storage.delete_inputs(job_id, settings.STORAGE_ROOT)
