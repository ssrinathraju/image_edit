from __future__ import annotations

import logging
from pathlib import Path

from image_edit_server.core.job_store import JobStore
from image_edit_server.repos import file_storage

logger = logging.getLogger(__name__)


def purge_user_jobs(user_id: str, store: JobStore, storage_root: str) -> None:
    """Delete every job of the user together with its output and input files."""
    for job in store.list_for_user(user_id):
        output = file_storage.output_path(job.id, storage_root)
        Path(output).unlink(missing_ok=True)
        file_storage.delete_inputs(job.id, storage_root)
        store.delete(job.id)
        logger.info("Purged job %s of user %s", job.id, user_id)
