from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services.auth_service import AuthService

PASSWORD = "correct horse battery"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def purged() -> list[str]:
    return []


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def auth(users, purged) -> AuthService:
    settings = Settings()
    throttle = LoginThrottle(
        settings.LOGIN_MAX_FAILURES, timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    )
    return AuthService(users, throttle, settings, purged.append)


def _error(excinfo) -> tuple[int, str]:
    return excinfo.value.status_code, excinfo.value.detail["error"]


def test_register_returns_token_that_resolves_to_the_user(auth, users):
    token, user = auth.register("ana@example.com", PASSWORD)

    assert users.get_user_by_session(token) == user


def test_register_stores_email_lowercase_and_trimmed(auth):
    _, user = auth.register("  Ana@Example.COM ", PASSWORD)

    assert user.email == "ana@example.com"


def test_register_duplicate_in_other_case_is_409(auth):
    auth.register("ana@example.com", PASSWORD)

    with pytest.raises(HTTPException) as excinfo:
        auth.register("ANA@example.com", PASSWORD)

    assert _error(excinfo) == (409, "email_taken")


def test_register_short_password_is_400_and_creates_nothing(auth, users):
    with pytest.raises(HTTPException) as excinfo:
        auth.register("ana@example.com", "short")

    assert _error(excinfo) == (400, "invalid_credentials_format")
    assert users.get_by_email("ana@example.com") is None


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.com", "", "a@" + "x" * 260 + ".com"])
def test_register_malformed_email_is_400(auth, email):
    with pytest.raises(HTTPException) as excinfo:
        auth.register(email, PASSWORD)

    assert _error(excinfo) == (400, "invalid_credentials_format")


def test_register_overlong_password_is_400(auth):
    with pytest.raises(HTTPException) as excinfo:
        auth.register("ana@example.com", "x" * 129)

    assert _error(excinfo) == (400, "invalid_credentials_format")


def test_login_with_correct_password_returns_a_session(auth, users):
    auth.register("ana@example.com", PASSWORD)

    token, user = auth.login("Ana@example.com", PASSWORD)

    assert users.get_user_by_session(token) == user


def test_wrong_password_and_unknown_email_are_indistinguishable(auth):
    auth.register("ana@example.com", PASSWORD)

    with pytest.raises(HTTPException) as wrong_password:
        auth.login("ana@example.com", "wrong password")
    with pytest.raises(HTTPException) as unknown_email:
        auth.login("nobody@example.com", PASSWORD)

    assert _error(wrong_password) == (401, "invalid_credentials")
    assert wrong_password.value.detail == unknown_email.value.detail
    assert unknown_email.value.status_code == 401


def test_sixth_attempt_is_throttled_even_with_the_right_password(auth):
    auth.register("ana@example.com", PASSWORD)
    for _ in range(5):
        with pytest.raises(HTTPException):
            auth.login("ana@example.com", "wrong password")

    with pytest.raises(HTTPException) as excinfo:
        auth.login("ana@example.com", PASSWORD)

    assert _error(excinfo) == (429, "too_many_attempts")


def test_success_resets_the_failure_count(auth):
    auth.register("ana@example.com", PASSWORD)
    for _ in range(2):
        with pytest.raises(HTTPException):
            auth.login("ana@example.com", "wrong password")
    auth.login("ana@example.com", PASSWORD)

    for _ in range(4):
        with pytest.raises(HTTPException) as excinfo:
            auth.login("ana@example.com", "wrong password")
        assert excinfo.value.status_code == 401

    token, _ = auth.login("ana@example.com", PASSWORD)
    assert token


def test_logout_revokes_only_that_session(auth, users):
    first, user = auth.register("ana@example.com", PASSWORD)
    second, _ = auth.login("ana@example.com", PASSWORD)

    auth.logout(first)

    assert users.get_user_by_session(first) is None
    assert users.get_user_by_session(second) == user


def test_delete_with_wrong_password_deletes_nothing(auth, users, purged):
    token, user = auth.register("ana@example.com", PASSWORD)

    with pytest.raises(HTTPException) as excinfo:
        auth.delete_account(user, "wrong password")

    assert _error(excinfo) == (403, "invalid_password")
    assert purged == []
    assert users.get_user_by_session(token) == user


def test_delete_with_right_password_removes_user_sessions_and_jobs(auth, users, purged):
    token, user = auth.register("ana@example.com", PASSWORD)

    auth.delete_account(user, PASSWORD)

    assert purged == [user.id]
    assert users.get_by_email("ana@example.com") is None
    assert users.get_user_by_session(token) is None
