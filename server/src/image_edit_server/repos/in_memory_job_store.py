from __future__ import annotations

import asyncio
from typing import Any, Iterable, Optional

from ulid import ULID

from image_edit_server.schemas.job import Job, JobStatus


class InMemoryJobStore:
    def __init__(self) -> None:
        self._store: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    def create(self, job: Job) -> str:
        job.id = str(ULID())
        self._store[job.id] = job
        return job.id

    def get(self, job_id: str) -> Optional[Job]:
        return self._store.get(job_id)

    def update(self, job_id: str, **fields: Any) -> None:
        job = self._store.get(job_id)
        if job is None:
            return
        for key, value in fields.items():
            setattr(job, key, value)

    def list_for_user(self, user_id: str) -> Iterable[Job]:
        return [j for j in list(self._store.values()) if j.user_id == user_id]

    def delete(self, job_id: str) -> None:
        self._store.pop(job_id, None)

    def list_queued(self) -> Iterable[Job]:
        return [j for j in self._store.values() if j.status == JobStatus.queued]
