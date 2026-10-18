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


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


EMAIL = "a@example.com"


def _reset(users, code, at=T0):
    return users.reset_password(EMAIL, code, "new-hash", at, 5)


def _issue_reset_code(users, code="111111"):
    purpose = CodePurpose.PASSWORD_RESET
    users.issue_code(EMAIL, purpose, hash_code(EMAIL, purpose, code), T0, LIMITS)


def test_success_changes_the_hash_and_drops_every_session(users):
    user = users.create_user(EMAIL, "old-hash")
    users.create_session(user.id, timedelta(days=1))
    users.create_session(user.id, timedelta(days=1))
    _issue_reset_code(users)

    result = _reset(users, "111111", T0 + timedelta(minutes=1))

    assert result is ConsumeResult.OK
    assert users.get_password_hash(user.id) == "new-hash"
    assert users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_a_reset_leaves_other_accounts_sessions_alone(users):
    users.create_user(EMAIL, "old-hash")
    other = users.create_user("b@example.com", "h")
    users.create_session(other.id, timedelta(days=1))
    _issue_reset_code(users)

    _reset(users, "111111")

    assert users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1


def test_a_wrong_code_changes_nothing_and_counts_an_attempt(users):
    user = users.create_user(EMAIL, "old-hash")
    users.create_session(user.id, timedelta(days=1))
    _issue_reset_code(users)

    result = _reset(users, "000000")

    assert result is ConsumeResult.WRONG
    assert users.get_password_hash(user.id) == "old-hash"
    assert users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    attempts = users._conn.execute("SELECT attempts FROM email_codes").fetchone()[0]
    assert attempts == 1


def test_an_expired_code_changes_nothing(users):
    user = users.create_user(EMAIL, "old-hash")
    _issue_reset_code(users)

    result = _reset(users, "111111", T0 + timedelta(minutes=16))

    assert result is ConsumeResult.EXPIRED
    assert users.get_password_hash(user.id) == "old-hash"


def test_a_registration_code_cannot_reset_a_password(users):
    user = users.create_user(EMAIL, "old-hash")
    purpose = CodePurpose.REGISTRATION
    users.issue_code(EMAIL, purpose, hash_code(EMAIL, purpose, "111111"), T0, LIMITS)

    assert _reset(users, "111111") is ConsumeResult.EXPIRED
    assert users.get_password_hash(user.id) == "old-hash"
