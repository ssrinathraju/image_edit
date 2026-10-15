from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.login_throttle import LoginThrottle

LOCKOUT = timedelta(minutes=15)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def throttle(clock) -> LoginThrottle:
    return LoginThrottle(5, LOCKOUT, clock=clock)


def _fail(throttle: LoginThrottle, email: str, times: int) -> None:
    for _ in range(times):
        throttle.record_failure(email)


def test_locks_after_five_failures(throttle):
    _fail(throttle, "a@x.com", 4)
    assert not throttle.is_locked("a@x.com")

    _fail(throttle, "a@x.com", 1)
    assert throttle.is_locked("a@x.com")


def test_unlocks_fifteen_minutes_after_last_failure(throttle, clock):
    _fail(throttle, "a@x.com", 5)

    clock.now += LOCKOUT - timedelta(seconds=1)
    assert throttle.is_locked("a@x.com")
    clock.now += timedelta(seconds=1)
    assert not throttle.is_locked("a@x.com")


def test_next_failure_after_unlock_counts_as_first(throttle, clock):
    _fail(throttle, "a@x.com", 5)
    clock.now += LOCKOUT

    _fail(throttle, "a@x.com", 1)

    assert not throttle.is_locked("a@x.com")


def test_success_resets_the_count(throttle):
    _fail(throttle, "a@x.com", 2)
    throttle.reset("a@x.com")

    _fail(throttle, "a@x.com", 4)

    assert not throttle.is_locked("a@x.com")


def test_emails_are_independent(throttle):
    _fail(throttle, "a@x.com", 5)

    assert throttle.is_locked("a@x.com")
    assert not throttle.is_locked("b@x.com")


def test_expired_entries_for_other_emails_are_dropped(throttle, clock):
    for i in range(20):
        _fail(throttle, f"user{i}@x.com", 1)
    clock.now += LOCKOUT

    _fail(throttle, "fresh@x.com", 1)

    assert list(throttle._failures) == ["fresh@x.com"]
