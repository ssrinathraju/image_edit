from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.core.user_store import QuotaExceeded, UserNotFound
from image_edit_server.repos import file_storage
from image_edit_server.repos.template_catalog import TemplateCatalog
from image_edit_server.schemas.api import ErrorBody, JobStatusResponse
from image_edit_server.schemas.job import Job, JobStatus
from image_edit_server.schemas.user import User
from image_edit_server.services.quota_service import QuotaService

logger = logging.getLogger(__name__)


async def submit(
    faces: list[UploadFile],
    prompt: Optional[str],
    template_id: Optional[str],
    store: JobStore,
    catalog: TemplateCatalog,
    user: User,
    quota: QuotaService,
    settings: Settings,
) -> str:
    """Require age and consent, validate inputs, reserve a generation, persist uploads, queue a job."""
    _require_age_and_consent(user, settings)
    _validate_face_count(faces, settings)
    face_data = await _read_and_validate_faces(faces, settings)
    resolved_prompt = _resolve_prompt(prompt, template_id, catalog, settings)

    # Reserved only after validation passed, so a rejected request costs nothing.
    reservation_id = await _reserve(quota, user)
    job = Job(
        id="",
        prompt=resolved_prompt,
        template_id=template_id,
        user_id=user.id,
        reservation_id=reservation_id,
    )
    job_id: Optional[str] = None
    try:
        job_id = store.create(job)
        for i, data in enumerate(face_data):
            path = file_storage.save_upload(job_id, i, data, settings.STORAGE_ROOT)
            job.face_paths.append(str(path))
    except Exception:
        quota.release(reservation_id)
        if job_id is not None:
            store.delete(job_id)
        raise

    logger.info("Enqueued job %s with %d face(s)", job_id, len(faces))
    return job_id


def get_status(job_id: str, user_id: str, store: JobStore) -> Optional[JobStatusResponse]:
    """Return the status, or None when the job is unknown or owned by someone else."""
    job = store.get(job_id)
    if job is None or job.user_id != user_id:
        return None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        result_url=job.result_url,
        error=job.error,
    )


# ── private helpers ──────────────────────────────────────────────────────────

def _require_age_and_consent(user: User, settings: Settings) -> None:
    if not user.age_confirmed:
        raise _forbidden("age_not_confirmed", "confirm your age with POST /me/age first")
    if user.consent_version != settings.CONSENT_VERSION:
        raise _forbidden(
            "consent_required",
            f"accept face-photo consent version {settings.CONSENT_VERSION!r} first",
        )


def _forbidden(code: str, detail: str) -> HTTPException:
    return HTTPException(403, ErrorBody(error=code, detail=detail).model_dump())


async def _reserve(quota: QuotaService, user: User) -> str:
    try:
        return await asyncio.to_thread(quota.reserve, user)
    except QuotaExceeded:
        raise HTTPException(
            429,
            ErrorBody(
                error="quota_exceeded",
                detail="the daily generation limit has been reached",
            ).model_dump(),
        )
    except UserNotFound:
        raise HTTPException(
            401,
            ErrorBody(error="unauthorized", detail="a valid session is required").model_dump(),
        )


def _validate_face_count(faces: list[UploadFile], settings: Settings) -> None:
    n = len(faces)
    if n < settings.MIN_FACES or n > settings.MAX_FACES:
        raise HTTPException(
            400,
            ErrorBody(
                error="invalid_face_count",
                detail=f"expected {settings.MIN_FACES}..{settings.MAX_FACES} faces, got {n}",
            ).model_dump(),
        )


async def _read_and_validate_faces(
    faces: list[UploadFile], settings: Settings
) -> list[bytes]:
    accepted = settings.accepted_image_types_set()
    result: list[bytes] = []
    for upload in faces:
        content_type = upload.content_type or ""
        if content_type not in accepted:
            raise HTTPException(
                400,
                ErrorBody(
                    error="invalid_image",
                    detail=f"unsupported content type '{content_type}'; accepted: {sorted(accepted)}",
                ).model_dump(),
            )
        data = await upload.read()
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(
                400,
                ErrorBody(
                    error="invalid_image",
                    detail=f"upload exceeds maximum size of {settings.MAX_UPLOAD_BYTES} bytes",
                ).model_dump(),
            )
        result.append(data)
    return result


def _resolve_prompt(
    prompt: Optional[str],
    template_id: Optional[str],
    catalog: TemplateCatalog,
    settings: Settings,
) -> str:
    if template_id is None:
        text = prompt or ""
        _validate_prompt(text, settings)
        return text
    if prompt is not None:
        raise _invalid_template("provide either 'prompt' or 'template_id', not both")
    template = catalog.get(template_id)
    if template is None:
        raise _invalid_template(f"unknown template_id '{template_id}'")
    return template.prompt


def _invalid_template(detail: str) -> HTTPException:
    return HTTPException(
        400, ErrorBody(error="invalid_template", detail=detail).model_dump()
    )


def _validate_prompt(prompt: str, settings: Settings) -> None:
    if not prompt.strip():
        raise HTTPException(
            400,
            ErrorBody(error="invalid_prompt", detail="prompt must not be empty").model_dump(),
        )
    if len(prompt) > settings.MAX_PROMPT_CHARS:
        raise HTTPException(
            400,
            ErrorBody(
                error="invalid_prompt",
                detail=f"prompt exceeds maximum length of {settings.MAX_PROMPT_CHARS} characters",
            ).model_dump(),
        )
