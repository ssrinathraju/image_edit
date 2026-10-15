from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status

from image_edit_server.api.deps import AuthDep, QuotaDep
from image_edit_server.api.templates import CatalogDep
from image_edit_server.core.job_store import JobStore
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.schemas.api import JobStatusResponse, JobSubmission
from image_edit_server.services import generation_service

router = APIRouter(prefix="/generations", tags=["generations"])

# Module-level store; replaced in tests via dependency override.
_store = InMemoryJobStore()


def get_store() -> JobStore:
    return _store


StoreDep = Annotated[JobStore, Depends(get_store)]


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=JobSubmission)
async def submit_generation(
    user: AuthDep,
    quota: QuotaDep,
    store: StoreDep,
    catalog: CatalogDep,
    prompt: Annotated[Optional[str], Form()] = None,
    template_id: Annotated[Optional[str], Form()] = None,
    faces: list[UploadFile] = [],
) -> JobSubmission:
    job_id = await generation_service.submit(
        faces, prompt, template_id, store, catalog, user, quota
    )
    return JobSubmission(job_id=job_id)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_generation_status(
    job_id: str, user: AuthDep, store: StoreDep
) -> JobStatusResponse:
    result = generation_service.get_status(job_id, user.id, store)
    if result is None:
        raise HTTPException(status_code=404, detail={"error": "not_found", "detail": f"job '{job_id}' not found"})
    return result
