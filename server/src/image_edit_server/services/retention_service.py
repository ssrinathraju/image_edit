from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Sequence, TypeVar

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import JobStatus

logger = logging.getLogger(__name__)

BATCH_SIZE = 200
SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60

_LIVE = (JobStatus.queued, JobStatus.running)
_T = TypeVar("_T")


@dataclass(frozen=True)
class SweepResult:
    outputs_removed: int = 0
    job_records_removed: int = 0
    input_folders_removed: int = 0
    errors: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _scan_outputs(storage_root: str) -> list[tuple[str, float]]:
    """Read-only look at outputs/; safe to run off the event loop."""
    outputs: list[tuple[str, float]] = []
    for path in file_storage.list_output_files(storage_root):
        try:
            outputs.append((path.stem, path.stat().st_mtime))
        except OSError:
            logger.warning("Could not stat %s; skipping it this pass", path)
    return outputs


def _scan_inputs(storage_root: str) -> list[str]:
    return file_storage.list_input_job_ids(storage_root)


async def _scan_safely(scan: Callable[[str], _T], storage_root: str, what: str) -> tuple[_T | None, int]:
    """Run one folder scan off-loop; a failure skips only that folder."""
    try:
        return await asyncio.to_thread(scan, storage_root), 0
    except Exception:
        logger.exception("Could not scan %s; skipping it this pass", what)
        return None, 1


def _batches(items: Sequence[_T]) -> Iterable[Sequence[_T]]:
    for start in range(0, len(items), BATCH_SIZE):
        yield items[start:start + BATCH_SIZE]


async def sweep(store: JobStore, settings: Settings, now: datetime) -> SweepResult:
    """One retention pass: expire old images and clear faces of vanished jobs.

    The scan runs in a thread; everything that touches the job store runs here
    on the event loop, in batches, because the store is not thread-safe.
    """
    # Scanned separately: an unreadable outputs/ must not disable the cleanup of
    # reference faces, which is the privacy-relevant half.
    outputs, outputs_scan_errors = await _scan_safely(
        _scan_outputs, settings.STORAGE_ROOT, "outputs/"
    )
    input_ids, inputs_scan_errors = await _scan_safely(
        _scan_inputs, settings.STORAGE_ROOT, "inputs/"
    )
    outputs, input_ids = outputs or [], input_ids or []
    cutoff_age = settings.OUTPUT_RETENTION_HOURS * SECONDS_PER_HOUR
    expired = [
        job_id for job_id, mtime in outputs if now.timestamp() - mtime >= cutoff_age
    ]

    outputs_removed = job_records_removed = input_folders_removed = 0
    errors = outputs_scan_errors + inputs_scan_errors

    for batch in _batches(expired):
        for job_id in batch:
            try:
                job = store.get(job_id)
                if job is not None and job.status in _LIVE:
                    continue  # never pull a live job out from under the worker
                if job is not None:
                    store.delete(job_id)
                    job_records_removed += 1
                file_storage.delete_output(job_id, settings.STORAGE_ROOT)
                outputs_removed += 1
            except Exception:
                errors += 1
                logger.exception("Could not expire output %s", job_id)
        await asyncio.sleep(0)

    for batch in _batches(input_ids):
        for job_id in batch:
            try:
                if store.get(job_id) is None:
                    file_storage.delete_inputs(job_id, settings.STORAGE_ROOT)
                    input_folders_removed += 1
            except Exception:
                errors += 1
                logger.exception("Could not remove leftover faces of %s", job_id)
        await asyncio.sleep(0)

    result = SweepResult(
        outputs_removed, job_records_removed, input_folders_removed, errors
    )
    if outputs_removed or input_folders_removed:
        logger.info(
            "Retention sweep removed %d expired image(s) and %d leftover face folder(s)",
            outputs_removed,
            input_folders_removed,
        )
    return result


async def run_retention(
    store: JobStore,
    settings: Settings,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """Sweep forever at the configured interval; a failed pass never ends the loop."""
    while True:
        await asyncio.sleep(settings.RETENTION_SWEEP_MINUTES * SECONDS_PER_MINUTE)
        try:
            await sweep(store, settings, clock())
        except Exception:
            logger.exception("Retention sweep failed; will retry next interval")
