from datetime import datetime, timezone

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.user_store import QuotaExceeded
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services.quota_service import QuotaService
from tests.helpers import grant_bonus

NOW = datetime(2026, 3, 10, 15, 30, tzinfo=timezone.utc)


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def quota(users) -> QuotaService:
    return QuotaService(users, Settings(), clock=lambda: NOW)


def test_summary_of_a_fresh_account(users, quota):
    user = users.create_user("ana@example.com", "hash")

    usage = quota.summary(user)

    assert (usage.daily_limit, usage.used_today, usage.bonus_credits, usage.remaining) == (3, 0, 0, 3)
    assert usage.plan_limits == {"free": 3, "premium": 30}


def test_summary_adds_bonus_credits_to_what_is_left_of_the_day(users, quota):
    user = users.create_user("ana@example.com", "hash")
    grant_bonus(users, user.id, 5)
    quota.reserve(users.get_by_id(user.id))
    quota.reserve(users.get_by_id(user.id))

    usage = quota.summary(users.get_by_id(user.id))

    assert (usage.used_today, usage.bonus_credits, usage.remaining) == (2, 5, 6)


def test_resets_at_is_the_next_midnight_utc(users, quota):
    user = users.create_user("ana@example.com", "hash")

    assert quota.summary(user).resets_at == "2026-03-11T00:00:00+00:00"


def test_premium_accounts_get_the_larger_limit(users, quota):
    user = users.create_user("ana@example.com", "hash")
    users.set_plan("ana@example.com", "premium")
    premium = users.get_by_id(user.id)

    for _ in range(4):
        quota.reserve(premium)

    usage = quota.summary(premium)
    assert (usage.daily_limit, usage.used_today, usage.remaining) == (30, 4, 26)


def test_reserve_refuses_when_nothing_is_left(users, quota):
    user = users.create_user("ana@example.com", "hash")
    for _ in range(3):
        quota.reserve(user)

    with pytest.raises(QuotaExceeded):
        quota.reserve(user)


def test_release_gives_the_generation_back(users, quota):
    user = users.create_user("ana@example.com", "hash")
    reservations = [quota.reserve(user) for _ in range(3)]

    quota.release(reservations[0])

    assert quota.summary(user).remaining == 1
