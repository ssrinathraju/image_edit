from __future__ import annotations

import math
import threading
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

HOUR = timedelta(hours=1)
DAY = timedelta(hours=24)
MAX_PER_HOUR = 5
MAX_PER_DAY = 10


class SignupLimiter:
    """Counts accepted sign-ups per network address in a sliding window, in memory only."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._times: dict[str, deque[datetime]] = {}

    def check(self, address: str, now: datetime) -> Optional[int]:
        """None when a sign-up is allowed, otherwise the seconds until it would be; counts nothing."""
        with self._lock:
            return self._wait(address, now)

    def reserve(self, address: str, now: datetime) -> Optional[int]:
        """Atomically check and count one sign-up; None when counted, else the seconds to wait.

        Release the reservation with `release` if the sign-up then fails. Each call also drops
        every entry older than a day, which costs O(addresses seen in the last 24 hours) under
        the lock.
        """
        with self._lock:
            for known in list(self._times):
                self._recent(known, now)
            wait = self._wait(address, now)
            if wait is None:
                self._times.setdefault(address, deque()).append(now)
            return wait

    def release(self, address: str, at: datetime) -> None:
        """Undo one reservation made at `at`; a no-op when it is already gone."""
        with self._lock:
            times = self._times.get(address)
            if times is None or at not in times:
                return
            times.remove(at)
            if not times:
                del self._times[address]

    def _wait(self, address: str, now: datetime) -> Optional[int]:
        times = self._recent(address, now)
        waits = [
            _seconds_until(times[-limit] + window, now)
            for window, limit in ((HOUR, MAX_PER_HOUR), (DAY, MAX_PER_DAY))
            if sum(1 for t in times if t > now - window) >= limit
        ]
        return max(waits) if waits else None

    def _recent(self, address: str, now: datetime) -> deque[datetime]:
        times = self._times.get(address, deque())
        while times and times[0] <= now - DAY:
            times.popleft()
        if not times:
            self._times.pop(address, None)
        return times


def _seconds_until(moment: datetime, now: datetime) -> int:
    return max(1, math.ceil((moment - now).total_seconds()))
