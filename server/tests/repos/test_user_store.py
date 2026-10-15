from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.user_store import EmailTakenError
from image_edit_server.repos.user_store import SqliteUserStore

TTL = timedelta(days=30)


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def users(clock) -> SqliteUserStore:
    return SqliteUserStore(":memory:", clock=clock)


def test_create_and_look_up_user(users):
    user = users.create_user("ana@example.com", "hash-1")

    assert users.get_by_email("ana@example.com") == user
    assert users.get_by_id(user.id) == user
    assert users.get_password_hash(user.id) == "hash-1"
    assert users.get_by_email("nobody@example.com") is None


def test_duplicate_email_raises_typed_error(users):
    users.create_user("ana@example.com", "hash-1")

    with pytest.raises(EmailTakenError):
        users.create_user("ana@example.com", "hash-2")


def test_session_resolves_to_its_user(users):
    user = users.create_user("ana@example.com", "hash-1")
    token = users.create_session(user.id, TTL)

    assert users.get_user_by_session(token) == user
    assert users.get_user_by_session("unknown-token") is None


def test_session_expires_after_ttl(users, clock):
    user = users.create_user("ana@example.com", "hash-1")
    token = users.create_session(user.id, TTL)

    clock.now += TTL - timedelta(seconds=1)
    assert users.get_user_by_session(token) == user
    clock.now += timedelta(seconds=1)
    assert users.get_user_by_session(token) is None


def test_delete_session_leaves_other_sessions(users):
    user = users.create_user("ana@example.com", "hash-1")
    first = users.create_session(user.id, TTL)
    second = users.create_session(user.id, TTL)

    users.delete_session(first)

    assert users.get_user_by_session(first) is None
    assert users.get_user_by_session(second) == user


def test_delete_user_cascades_to_sessions(users):
    user = users.create_user("ana@example.com", "hash-1")
    token = users.create_session(user.id, TTL)

    users.delete_user(user.id)

    assert users.get_by_id(user.id) is None
    assert users.get_user_by_session(token) is None


def test_token_is_not_stored_in_plain_text(users):
    user = users.create_user("ana@example.com", "hash-1")
    token = users.create_session(user.id, TTL)

    rows = users._conn.execute("SELECT token_hash FROM sessions").fetchall()
    assert token not in [r[0] for r in rows]


def test_creating_a_session_prunes_expired_ones(users, clock):
    user = users.create_user("ana@example.com", "hash-1")
    users.create_session(user.id, TTL)
    users.create_session(user.id, TTL)
    clock.now += TTL + timedelta(seconds=1)

    live = users.create_session(user.id, TTL)

    rows = users._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert rows == 1
    assert users.get_user_by_session(live) == user
