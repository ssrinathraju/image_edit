from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol

from image_edit_server.schemas.job import Job


class JobStore(Protocol):
    def create(self, job: Job) -> str:
        """Persist a new job and return its id."""
        ...

    def get(self, job_id: str) -> Optional[Job]:
        """Return the job with the given id, or None if not found."""
        ...

    def update(self, job_id: str, **fields: Any) -> None:
        """Update named fields on an existing job in-place."""
        ...

    def list_queued(self) -> Iterable[Job]:
        """Return all jobs whose status is queued."""
        ...

    def list_for_user(self, user_id: str) -> Iterable[Job]:
        """Return all jobs owned by the user."""
        ...

    def delete(self, job_id: str) -> None:
        """Remove the job; unknown ids are ignored."""
        ...
