from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import HTTPException
from ulid import ULID

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.core.user_store import TooManyReports, UserNotFound, UserStore
from image_edit_server.repos import file_storage
from image_edit_server.schemas.api import ErrorBody
from image_edit_server.schemas.job import JobStatus
from image_edit_server.schemas.report import (
    MAX_NOTE_CHARS,
    REPORT_CATEGORIES,
    SOURCE_DEVICE,
    SOURCE_NONE,
    SOURCE_SERVER,
)
from image_edit_server.schemas.user import User
from image_edit_server.services.safety.safety_service import log_safety_event

logger = logging.getLogger(__name__)

MAX_JOB_ID_CHARS = 64


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _error(status: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status, ErrorBody(error=code, detail=detail).model_dump())


class ReportService:
    def __init__(
        self,
        settings: Settings,
        users: UserStore,
        store: JobStore,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._settings = settings
        self._users = users
        self._store = store
        self._clock = clock

    async def create_report(
        self,
        user: User,
        job_id: str,
        category: str,
        note: Optional[str],
        image: Optional[bytes],
        image_content_type: str,
    ) -> str:
        """Validate, keep an image copy, store the report and return its id."""
        note_text = note or ""
        self._validate_fields(job_id, category, note_text)
        has_server_copy = self._has_server_copy_or_404(user, job_id)
        report_id = str(ULID())
        image_name = f"{report_id}.png"
        source = await self._keep_image(
            job_id if has_server_copy else None, image_name, image, image_content_type
        )
        stored_name = image_name if source != SOURCE_NONE else None
        try:
            await asyncio.to_thread(
                self._users.add_report,
                report_id, user.id, job_id, category, note_text, source,
                stored_name, self._clock(), self._settings.REPORTS_PER_DAY,
            )
        except (TooManyReports, UserNotFound) as error:
            await self._discard_image(image_name)
            raise _refusal_for(error) from error
        except Exception:
            await self._discard_image(image_name)
            raise
        log_safety_event("report_created", user.id, report_id)
        return report_id

    def _validate_fields(self, job_id: str, category: str, note: str) -> None:
        if not job_id or len(job_id) > MAX_JOB_ID_CHARS:
            raise _error(400, "invalid_report", f"job_id must be 1..{MAX_JOB_ID_CHARS} characters")
        if category not in REPORT_CATEGORIES:
            raise _error(400, "invalid_report", f"category must be one of {list(REPORT_CATEGORIES)}")
        if len(note) > MAX_NOTE_CHARS:
            raise _error(400, "invalid_report", f"note exceeds {MAX_NOTE_CHARS} characters")

    def _has_server_copy_or_404(self, user: User, job_id: str) -> bool:
        """True when the reporter's own job succeeded (its image may still exist); 404 for someone else's job."""
        job = self._store.get(job_id)
        if job is None:
            return False
        if job.user_id != user.id:
            raise _error(404, "not_found", f"job '{job_id}' not found")
        return job.status == JobStatus.succeeded

    async def _keep_image(
        self,
        server_job_id: Optional[str],
        image_name: str,
        image: Optional[bytes],
        content_type: str,
    ) -> str:
        root = self._settings.STORAGE_ROOT
        if server_job_id is not None:
            try:
                await asyncio.to_thread(
                    file_storage.copy_output_to_report, server_job_id, image_name, root
                )
                return SOURCE_SERVER
            except FileNotFoundError:
                pass  # the 24-hour sweep got there first; use the device's copy
        if image is None:
            return SOURCE_NONE
        self._validate_device_image(image, content_type)
        await asyncio.to_thread(file_storage.save_report_image, image_name, image, root)
        return SOURCE_DEVICE

    def _validate_device_image(self, image: bytes, content_type: str) -> None:
        accepted = self._settings.accepted_image_types_set()
        if content_type not in accepted:
            raise _error(
                400, "invalid_image",
                f"unsupported content type '{content_type}'; accepted: {sorted(accepted)}",
            )
        if len(image) > self._settings.MAX_UPLOAD_BYTES:
            raise _error(
                400, "invalid_image",
                f"upload exceeds maximum size of {self._settings.MAX_UPLOAD_BYTES} bytes",
            )

    async def _discard_image(self, image_name: str) -> None:
        await asyncio.to_thread(
            file_storage.delete_report_image, image_name, self._settings.STORAGE_ROOT
        )


def _refusal_for(error: Exception) -> HTTPException:
    if isinstance(error, TooManyReports):
        return _error(429, "too_many_reports", "the daily report limit has been reached")
    return _error(401, "unauthorized", "a valid session is required")
