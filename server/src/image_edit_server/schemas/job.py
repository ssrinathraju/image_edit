from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


@dataclass
class Job:
    id: str
    status: JobStatus = JobStatus.queued
    result_url: Optional[str] = None
    error: Optional[str] = None
    prompt: str = ""
    face_paths: list[str] = field(default_factory=list)
