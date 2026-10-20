from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

from image_edit_server.configs.settings import Settings
from image_edit_server.core.user_store import UserStore
from image_edit_server.repos import file_storage

logger = logging.getLogger(__name__)

SECONDS_PER_MINUTE = 60
# A report image is copied before its row is written, so a file with no row yet is
# normal for a moment; only older ones are orphans of a crashed account deletion.
ORPHAN_GRACE_SECONDS = 3600


@dataclass(frozen=True)
class ReportSweepResult:
    reports_removed: int = 0
    orphan_images_removed: int = 0
    errors: int = 0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _remove_expired_reports(
    users: UserStore, settings: Settings, now: datetime
) -> tuple[int, int]:
    removed = errors = 0
    max_age = timedelta(days=settings.REPORT_RETENTION_DAYS)
    for report in users.expired_reports(now, max_age):
        try:
            if report.image_name:
                file_storage.delete_report_image(report.image_name, settings.STORAGE_ROOT)
            users.delete_report(report.id)
            removed += 1
        except Exception:
            errors += 1
            logger.exception("Could not expire report %s", report.id)
    return removed, errors


def _remove_orphan_images(
    users: UserStore, settings: Settings, now: datetime
) -> tuple[int, int]:
    known = set(users.report_image_names())
    removed = errors = 0
    for path in file_storage.list_report_image_files(settings.STORAGE_ROOT):
        try:
            is_orphan = path.name not in known
            if is_orphan and now.timestamp() - path.stat().st_mtime >= ORPHAN_GRACE_SECONDS:
                path.unlink(missing_ok=True)
                removed += 1
        except Exception:
            errors += 1
            logger.exception("Could not check report image %s", path.name)
    return removed, errors


def _sweep_reports_blocking(
    users: UserStore, settings: Settings, now: datetime
) -> ReportSweepResult:
    reports_removed, expiry_errors = _remove_expired_reports(users, settings, now)
    orphans_removed, orphan_errors = _remove_orphan_images(users, settings, now)
    return ReportSweepResult(reports_removed, orphans_removed, expiry_errors + orphan_errors)


async def sweep_reports(users: UserStore, settings: Settings, now: datetime) -> ReportSweepResult:
    """Delete reports older than the retention with their images, and report images that have no report."""
    result = await asyncio.to_thread(_sweep_reports_blocking, users, settings, now)
    if result.reports_removed or result.orphan_images_removed:
        logger.info(
            "Report sweep removed %d expired report(s) and %d orphan image(s)",
            result.reports_removed,
            result.orphan_images_removed,
        )
    return result


async def run_report_retention(
    users: UserStore,
    settings: Settings,
    clock: Callable[[], datetime] = _utc_now,
) -> None:
    """Sweep reports forever at the retention interval; a failed pass never ends the loop."""
    while True:
        await asyncio.sleep(settings.RETENTION_SWEEP_MINUTES * SECONDS_PER_MINUTE)
        try:
            await sweep_reports(users, settings, clock())
        except Exception:
            logger.exception("Report sweep failed; will retry next interval")
