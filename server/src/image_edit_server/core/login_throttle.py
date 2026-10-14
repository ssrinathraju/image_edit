from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Callable


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LoginThrottle:
    """Counts consecutive failed logins per email and locks the email out."""

    def __init__(
        self,
        max_failures: int,
        lockout: timedelta,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._max_failures = max_failures
        self._lockout = lockout
        self._clock = clock
        self._lock = threading.Lock()
        self._failures: dict[str, tuple[int, datetime]] = {}

    def is_locked(self, email: str) -> bool:
        with self._lock:
            entry = self._failures.get(email)
            if entry is None:
                return False
            count, last_failure = entry
            if self._clock() - last_failure >= self._lockout:
                del self._failures[email]
                return False
            return count >= self._max_failures

    def record_failure(self, email: str) -> None:
        with self._lock:
            now = self._clock()
            count, last_failure = self._failures.get(email, (0, now))
            if now - last_failure >= self._lockout:
                count = 0
            self._failures[email] = (count + 1, now)

    def reset(self, email: str) -> None:
        with self._lock:
            self._failures.pop(email, None)
