import threading
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.user_store import QuotaExceeded, UserNotFound
from image_edit_server.repos.user_store import SqliteUserStore

LIMIT = 3
NOON = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def user(users):
    return users.create_user("ana@example.com", "hash")


def _grant_bonus(users, user_id: str, credits: int) -> None:
    users._conn.execute(
        "UPDATE users SET bonus_credits = ? WHERE id = ?", (credits, user_id)
    )
    users._conn.commit()


def _reserve_n(users, user, n: int, now=NOON) -> list:
    return [users.reserve_generation(user.id, LIMIT, now) for _ in range(n)]


def test_daily_use_then_bonus_use_then_quota_exceeded(users, user):
    _grant_bonus(users, user.id, 2)

    _reserve_n(users, user, 3)
    assert users.usage_snapshot(user.id, LIMIT, NOON).bonus_credits == 2
    _reserve_n(users, user, 2)
    assert users.usage_snapshot(user.id, LIMIT, NOON).bonus_credits == 0

    with pytest.raises(QuotaExceeded):
        users.reserve_generation(user.id, LIMIT, NOON)


def test_snapshot_arithmetic_and_reset_time(users, user):
    _grant_bonus(users, user.id, 5)
    _reserve_n(users, user, 2)

    snapshot = users.usage_snapshot(user.id, LIMIT, NOON)

    assert (snapshot.daily_limit, snapshot.used_today, snapshot.bonus_credits) == (3, 2, 5)
    assert snapshot.remaining == 6
    assert snapshot.resets_at == datetime(2026, 3, 11, tzinfo=timezone.utc)


def test_allowance_resets_at_utc_midnight(users, user):
    _reserve_n(users, user, 3, now=datetime(2026, 3, 10, 23, 59, tzinfo=timezone.utc))
    with pytest.raises(QuotaExceeded):
        users.reserve_generation(user.id, LIMIT, datetime(2026, 3, 10, 23, 59, 30, tzinfo=timezone.utc))

    users.reserve_generation(user.id, LIMIT, datetime(2026, 3, 11, 0, 0, tzinfo=timezone.utc))


def test_day_boundary_uses_utc_not_the_callers_offset(users, user):
    plus_five = timezone(timedelta(hours=5))
    # 02:00 on the 11th at +05:00 is still 21:00 on the 10th in UTC.
    late = datetime(2026, 3, 11, 2, 0, tzinfo=plus_five)
    _reserve_n(users, user, 3, now=late)

    with pytest.raises(QuotaExceeded):
        users.reserve_generation(user.id, LIMIT, datetime(2026, 3, 10, 22, 0, tzinfo=timezone.utc))


def test_refund_of_a_daily_reservation_restores_the_allowance(users, user):
    ids = _reserve_n(users, user, 3)

    users.refund_generation(ids[0])

    assert users.usage_snapshot(user.id, LIMIT, NOON).used_today == 2
    users.reserve_generation(user.id, LIMIT, NOON)


def test_refund_of_a_bonus_reservation_returns_the_credit(users, user):
    _grant_bonus(users, user.id, 1)
    ids = _reserve_n(users, user, 4)

    users.refund_generation(ids[3])

    assert users.usage_snapshot(user.id, LIMIT, NOON).bonus_credits == 1


def test_refund_is_idempotent(users, user):
    _grant_bonus(users, user.id, 1)
    ids = _reserve_n(users, user, 4)

    users.refund_generation(ids[3])
    users.refund_generation(ids[3])
    users.refund_generation("unknown-reservation")

    assert users.usage_snapshot(user.id, LIMIT, NOON).bonus_credits == 1


def test_refund_from_a_previous_day_does_not_change_today(users, user):
    yesterday = NOON - timedelta(days=1)
    old = _reserve_n(users, user, 1, now=yesterday)
    _reserve_n(users, user, 2)

    users.refund_generation(old[0])

    assert users.usage_snapshot(user.id, LIMIT, NOON).used_today == 2


def test_reserving_for_a_deleted_user_is_a_typed_error(users, user):
    users.delete_user(user.id)

    with pytest.raises(UserNotFound):
        users.reserve_generation(user.id, LIMIT, NOON)


def test_two_threads_racing_for_the_last_generation_one_wins(users, user):
    _reserve_n(users, user, LIMIT - 1)
    barrier = threading.Barrier(2)
    outcomes: list = []

    def attempt():
        barrier.wait()
        try:
            users.reserve_generation(user.id, LIMIT, NOON)
            outcomes.append("ok")
        except QuotaExceeded:
            outcomes.append("refused")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(outcomes) == ["ok", "refused"]
