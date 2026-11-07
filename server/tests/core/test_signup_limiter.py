import threading
from collections import deque
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core import signup_limiter as limits
from image_edit_server.core.signup_limiter import SignupLimiter

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
ADDRESS = "203.0.113.5"

pytestmark = pytest.mark.real_signup_limits


def test_the_shipped_caps_are_five_an_hour_and_ten_a_day():
    assert limits.MAX_PER_HOUR == 5
    assert limits.MAX_PER_DAY == 10


@pytest.fixture
def limiter() -> SignupLimiter:
    return SignupLimiter()


def _record_at(limiter, offsets_minutes, address=ADDRESS):
    for minutes in offsets_minutes:
        limiter.reserve(address, T0 + timedelta(minutes=minutes))


def test_the_first_five_in_an_hour_are_allowed(limiter):
    _record_at(limiter, [0, 1, 2, 3])

    assert limiter.check(ADDRESS, T0 + timedelta(minutes=4)) is None


def test_the_sixth_in_an_hour_is_refused_until_the_oldest_leaves(limiter):
    _record_at(limiter, [0, 5, 10, 15, 20])

    wait = limiter.check(ADDRESS, T0 + timedelta(minutes=30))

    assert wait == 30 * 60


def test_only_the_oldest_entry_that_must_leave_sets_the_hourly_wait(limiter):
    limiter._times[ADDRESS] = deque(T0 + timedelta(minutes=m) for m in range(6))
    # six inside the hour: the fifth most recent (minute 1) must leave
    assert limiter.check(ADDRESS, T0 + timedelta(minutes=10)) == 51 * 60


def test_the_hourly_limit_lifts_after_the_wait(limiter):
    _record_at(limiter, [0, 5, 10, 15, 20])

    assert limiter.check(ADDRESS, T0 + timedelta(minutes=60, seconds=1)) is None


def test_the_eleventh_in_a_day_is_refused_with_the_daily_wait(limiter):
    _record_at(limiter, [h * 60 for h in range(0, 20, 2)])  # ten, two hours apart

    wait = limiter.check(ADDRESS, T0 + timedelta(hours=19, minutes=30))

    assert wait == int(timedelta(hours=4, minutes=30).total_seconds())


def test_refused_requests_are_not_counted(limiter):
    _record_at(limiter, [0, 1, 2, 3, 4])
    for minute in range(5, 20):
        assert limiter.check(ADDRESS, T0 + timedelta(minutes=minute)) is not None

    # had refusals counted, the window would stay full after the first five leave
    assert limiter.check(ADDRESS, T0 + timedelta(minutes=64, seconds=30)) is None


def test_other_addresses_are_independent(limiter):
    _record_at(limiter, [0, 1, 2, 3, 4])

    assert limiter.check("198.51.100.7", T0 + timedelta(minutes=5)) is None


def test_entries_older_than_a_day_are_dropped(limiter):
    _record_at(limiter, [0, 1, 2], address="old")
    limiter.reserve(ADDRESS, T0 + timedelta(hours=25))

    assert "old" not in limiter._times
    assert limiter.check("old", T0 + timedelta(hours=25)) is None


def test_concurrent_reservations_never_exceed_the_hourly_cap(limiter):
    barrier = threading.Barrier(40)
    results = []

    def attempt():
        barrier.wait()
        results.append(limiter.reserve(ADDRESS, T0))

    threads = [threading.Thread(target=attempt) for _ in range(40)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(None) == 5
    assert len(limiter._times[ADDRESS]) == 5


def test_a_refused_reservation_returns_the_wait_and_counts_nothing(limiter):
    _record_at(limiter, [0, 5, 10, 15, 20])

    assert limiter.reserve(ADDRESS, T0 + timedelta(minutes=30)) == 30 * 60
    assert len(limiter._times[ADDRESS]) == 5


def test_releasing_a_reservation_frees_its_slot(limiter):
    _record_at(limiter, [0, 1, 2, 3])
    assert limiter.reserve(ADDRESS, T0 + timedelta(minutes=4)) is None
    assert limiter.check(ADDRESS, T0 + timedelta(minutes=5)) is not None

    limiter.release(ADDRESS, T0 + timedelta(minutes=4))

    assert limiter.check(ADDRESS, T0 + timedelta(minutes=5)) is None


def test_releasing_the_last_reservation_forgets_the_address(limiter):
    limiter.reserve(ADDRESS, T0)

    limiter.release(ADDRESS, T0)
    limiter.release(ADDRESS, T0)

    assert ADDRESS not in limiter._times
