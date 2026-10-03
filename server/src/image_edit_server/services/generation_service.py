from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile

from image_edit_server.configs.settings import Settings
from image_edit_server.core.job_store import JobStore
from image_edit_server.repos import file_storage
from image_edit_server.schemas.api import ErrorBody, JobStatusResponse
from image_edit_server.schemas.job import Job, JobStatus

logger = logging.getLogger(__name__)

_SETTINGS = Settings()


async def submit(
    faces: list[UploadFile],
    prompt: str,
    store: JobStore,
    settings: Settings = _SETTINGS,
) -> str:
    """Validate inputs, persist uploads, create a queued job. Return job_id."""
    _validate_face_count(faces, settings)
    face_data = await _read_and_validate_faces(faces, settings)
    _validate_prompt(prompt, settings)

    job = Job(id="", prompt=prompt)
    job_id = store.create(job)

    for i, data in enumerate(face_data):
        path = file_storage.save_upload(job_id, i, data, settings.STORAGE_ROOT)
        job.face_paths.append(str(path))

    logger.info("Enqueued job %s with %d face(s)", job_id, len(faces))
    return job_id


def get_status(job_id: str, store: JobStore) -> Optional[JobStatusResponse]:
    """Return status response or None if job_id is unknown."""
    job = store.get(job_id)
    if job is None:
        return None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        result_url=job.result_url,
        error=job.error,
    )


# ── private helpers ──────────────────────────────────────────────────────────

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
