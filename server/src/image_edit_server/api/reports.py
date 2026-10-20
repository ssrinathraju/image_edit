from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, UploadFile, status

from image_edit_server.api.deps import AuthDep
from image_edit_server.schemas.api import ReportCreated
from image_edit_server.services.safety.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service() -> ReportService:
    raise RuntimeError("report service is not configured; override get_report_service")


ReportServiceDep = Annotated[ReportService, Depends(get_report_service)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReportCreated)
async def create_report(
    user: AuthDep,
    reports: ReportServiceDep,
    job_id: Annotated[str, Form()] = "",
    category: Annotated[str, Form()] = "",
    note: Annotated[Optional[str], Form()] = None,
    image: Optional[UploadFile] = None,
) -> ReportCreated:
    data = await image.read() if image is not None else None
    report_id = await reports.create_report(
        user, job_id, category, note, data, (image.content_type or "") if image else ""
    )
    return ReportCreated(report_id=report_id)
