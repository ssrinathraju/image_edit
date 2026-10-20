from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from image_edit_server.configs.settings import Settings
from image_edit_server.core.safety import ImageClassifier, TermMatcher
from image_edit_server.core.user_store import UserStore

logger = logging.getLogger(__name__)


def log_safety_event(event: str, user_id: str, reference: str = "") -> None:
    """Log a safety decision with the event, the account and the job or report id; never content or scores."""
    logger.info("safety event=%s account=%s ref=%s", event, user_id, reference)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SafetyService:
    """Prompt screening, image classification and strike bookkeeping in one place."""

    def __init__(
        self,
        settings: Settings,
        users: UserStore,
        matcher: TermMatcher,
        upload_classifier: ImageClassifier,
        output_classifier: ImageClassifier,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._settings = settings
        self._users = users
        self._matcher = matcher
        self._upload_classifier = upload_classifier
        self._output_classifier = output_classifier
        self._clock = clock

    def is_prompt_blocked(self, prompt: str) -> bool:
        return self._matcher.matches(prompt)

    async def is_upload_flagged(self, image_bytes: bytes) -> bool:
        """Score an uploaded photo off the event loop; a classifier error propagates."""
        score = await asyncio.to_thread(self._upload_classifier.score, image_bytes)
        return score >= self._settings.SAFETY_NSFW_THRESHOLD

    async def is_output_flagged(self, image_bytes: bytes) -> bool:
        """Score a generated image off the event loop; a classifier error propagates."""
        score = await asyncio.to_thread(self._output_classifier.score, image_bytes)
        return score >= self._settings.SAFETY_NSFW_THRESHOLD

    def record_strike(self, user_id: str) -> None:
        self._users.record_strike(user_id, self._clock(), self._window())

    def suspended_until(self, user_id: str) -> Optional[datetime]:
        return self._users.suspended_until(
            user_id, self._clock(), self._window(), self._settings.STRIKE_LIMIT
        )

    def _window(self) -> timedelta:
        return timedelta(hours=self._settings.STRIKE_WINDOW_HOURS)
