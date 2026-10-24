from datetime import timedelta

import pytest
from fastapi import HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.schemas.user import Reauth
from image_edit_server.services.auth_service import AuthService
from tests.helpers import DEFAULT_PASSWORD, RecordingSender


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def auth(users, clock, google_verifier, apple_verifier) -> AuthService:
    settings = Settings()
    throttle = LoginThrottle(
        settings.LOGIN_MAX_FAILURES, timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    )
    return AuthService(
        users,
        throttle,
        settings,
        lambda user_id: None,
        RecordingSender(),
        clock,
        verifiers={"google": google_verifier, "apple": apple_verifier},
    )


@pytest.fixture
def password_user(users):
    from image_edit_server.core.passwords import hash_password

    return users.create_user("ana@example.com", hash_password(DEFAULT_PASSWORD))


@pytest.fixture
def google_user(users, clock, google_verifier):
    google_verifier.add("signin", "g-1", email="gina@example.com")
    user, _ = users.sign_in_with_identity(google_verifier.verify("signin"), clock.now, True)
    return user


def _outcome(auth, user, **reauth):
    with pytest.raises(HTTPException) as excinfo:
        auth.reauthenticate(user, Reauth(**reauth))
    return excinfo.value.status_code, excinfo.value.detail["error"]


def test_the_right_password_passes(auth, password_user):
    auth.reauthenticate(password_user, Reauth(password=DEFAULT_PASSWORD))


def test_a_wrong_password_is_403_reauth_failed(auth, password_user):
    assert _outcome(auth, password_user, password="wrong password") == (403, "reauth_failed")


def test_wrong_passwords_count_toward_the_login_lockout(auth, password_user):
    for _ in range(5):
        assert _outcome(auth, password_user, password="wrong password")[0] == 403

    assert _outcome(auth, password_user, password=DEFAULT_PASSWORD) == (429, "too_many_attempts")
    with pytest.raises(HTTPException) as login:
        auth.login("ana@example.com", DEFAULT_PASSWORD)
    assert login.value.status_code == 429


def test_four_wrong_passwords_do_not_lock(auth, password_user):
    for _ in range(4):
        assert _outcome(auth, password_user, password="wrong password")[0] == 403

    auth.reauthenticate(password_user, Reauth(password=DEFAULT_PASSWORD))


def test_a_fresh_provider_token_passes(auth, google_user, google_verifier, clock):
    google_verifier.add("fresh", "g-1", issued_at=clock.now - timedelta(minutes=1))

    auth.reauthenticate(google_user, Reauth(provider="google", token="fresh"))


def test_a_ten_minute_old_token_is_refused(auth, google_user, google_verifier, clock):
    google_verifier.add("stale", "g-1", issued_at=clock.now - timedelta(minutes=10))

    assert _outcome(auth, google_user, provider="google", token="stale") == (403, "reauth_failed")


def test_another_accounts_identity_is_refused(auth, google_user, google_verifier):
    google_verifier.add("theirs", "someone-else")

    assert _outcome(auth, google_user, provider="google", token="theirs") == (403, "reauth_failed")


def test_a_rejected_token_is_reauth_failed(auth, google_user):
    assert _outcome(auth, google_user, provider="google", token="unknown") == (403, "reauth_failed")


def test_a_provider_only_account_sending_a_password_is_refused(auth, google_user):
    for password in ("anything at all", "not-a-real-password", ""):
        assert _outcome(auth, google_user, password=password) == (403, "reauth_failed")


def test_deletion_keeps_its_own_error_codes(auth, password_user, google_user):
    with pytest.raises(HTTPException) as by_password:
        auth.delete_account(password_user, "wrong password")
    with pytest.raises(HTTPException) as by_token:
        auth.delete_account(google_user, provider="google", token="unknown")

    assert by_password.value.detail["error"] == "invalid_password"
    assert by_token.value.detail["error"] == "invalid_provider_token"
