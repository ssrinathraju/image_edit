from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from image_edit_server.schemas.job import JobStatus


class JobSubmission(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    result_url: Optional[str] = None
    error: Optional[str] = None
    expires_at: Optional[datetime] = None


class ReportCreated(BaseModel):
    report_id: str


class ErrorBody(BaseModel):
    error: str
    detail: str
