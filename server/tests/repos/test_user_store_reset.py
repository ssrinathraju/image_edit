from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    hash_code,
)
from image_edit_server.repos.user_store import SqliteUserStore

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LIMITS = CodeLimits(
    ttl=timedelta(minutes=15), resend_interval=timedelta(seconds=60), max_per_hour=5
)
BONUS = 5


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _reset(users, user_id, code, at=T0):
    return users.reset_password(user_id, code, "new-hash", at, 5, BONUS, 10)


def _issue_reset_code(users, user_id, code="111111"):
    purpose = CodePurpose.PASSWORD_RESET
    users.issue_code(user_id, purpose, hash_code(user_id, purpose, code), T0, LIMITS)


def test_success_changes_the_hash_drops_sessions_verifies_and_pays_the_referral(users):
    referrer = users.create_user("a@example.com", "h")
    friend = users.register_user("f@example.com", "old-hash", referrer.referral_code)
    users.create_session(friend.id, timedelta(days=1))
    users.create_session(friend.id, timedelta(days=1))
    _issue_reset_code(users, friend.id)

    result = _reset(users, friend.id, "111111", T0 + timedelta(minutes=1))

    assert result is ConsumeResult.OK
    assert users.get_password_hash(friend.id) == "new-hash"
    assert users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    after = users.get_by_id(friend.id)
    assert (after.email_verified, after.bonus_credits) == (True, BONUS)
    assert users.get_by_id(referrer.id).bonus_credits == BONUS


def test_a_wrong_code_changes_nothing_and_counts_an_attempt(users):
    user = users.create_user("a@example.com", "old-hash")
    users.create_session(user.id, timedelta(days=1))
    _issue_reset_code(users, user.id)

    result = _reset(users, user.id, "000000")

    assert result is ConsumeResult.WRONG
    assert users.get_password_hash(user.id) == "old-hash"
    assert users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    assert users.get_by_id(user.id).email_verified is False
    attempts = users._conn.execute("SELECT attempts FROM email_codes").fetchone()[0]
    assert attempts == 1


def test_an_expired_code_changes_nothing(users):
    user = users.create_user("a@example.com", "old-hash")
    _issue_reset_code(users, user.id)

    result = _reset(users, user.id, "111111", T0 + timedelta(minutes=16))

    assert result is ConsumeResult.EXPIRED
    assert users.get_password_hash(user.id) == "old-hash"
    assert users.get_by_id(user.id).email_verified is False


def test_a_verified_account_is_not_paid_again_by_a_reset(users):
    referrer = users.create_user("a@example.com", "h")
    friend = users.register_user("f@example.com", "old-hash", referrer.referral_code)
    users.mark_email_verified(friend.id, BONUS, 10)
    _issue_reset_code(users, friend.id)

    _reset(users, friend.id, "111111")

    assert users.get_by_id(friend.id).bonus_credits == BONUS
    assert users.get_by_id(referrer.id).bonus_credits == BONUS
