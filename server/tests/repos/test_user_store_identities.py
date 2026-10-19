import threading
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.user_store import (
    AgeRequired,
    ProviderAlreadyLinked,
    ProviderEmailMissing,
    ProviderEmailUnverified,
    UnderAgeSignUp,
)
from image_edit_server.repos.user_store import SqliteUserStore

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _identity(
    provider="google",
    subject="g-1",
    email="ana@example.com",
    verified=True,
) -> ProviderIdentity:
    return ProviderIdentity(provider, subject, email, verified, NOW)


def _sign_in(users, identity):
    return users.sign_in_with_identity(identity, NOW, adult_confirmed=True)


def _count(users, table) -> int:
    return users._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_a_new_identity_creates_a_verified_account_with_no_password(users):
    user, created = _sign_in(users, _identity(email="Ana@Example.com"))

    assert created is True
    assert user.email == "ana@example.com"
    assert user.has_password is False
    assert len(user.referral_code) == 8
    assert users.get_password_hash(user.id) == ""
    assert users.list_providers(user.id) == ["google"]


def test_a_linked_identity_returns_its_user_with_an_unchanged_email(users):
    first, _ = _sign_in(users, _identity())

    again, created = _sign_in(users, _identity(email="changed@example.com", verified=False))

    assert (again.id, created) == (first.id, False)
    assert users.get_by_id(first.id).email == "ana@example.com"
    assert _count(users, "users") == 1


def test_a_mixed_case_email_links_to_a_password_account_and_keeps_its_password(users):
    existing = users.create_user("ana@example.com", "hash")

    user, created = _sign_in(users, _identity(email="ANA@example.com"))

    assert (user.id, created) == (existing.id, False)
    assert users.get_password_hash(existing.id) == "hash"
    assert users.get_by_id(existing.id).has_password is True
    assert users.list_providers(existing.id) == ["google"]


def test_linking_changes_nothing_else_about_the_account(users):
    existing = users.create_user("ana@example.com", "hash")
    users.create_session(existing.id, timedelta(days=1))
    before = users.get_by_id(existing.id)

    _sign_in(users, _identity())

    assert users.get_by_id(existing.id) == before
    assert _count(users, "sessions") == 1
    assert users.get_password_hash(existing.id) == "hash"


def test_an_apple_relay_email_becomes_the_account_email(users):
    relay = "abc123@privaterelay.appleid.com"

    user, created = _sign_in(users, _identity("apple", "a-1", relay))

    assert (created, user.email) == (True, relay)


def test_an_unknown_identity_without_an_email_is_refused(users):
    with pytest.raises(ProviderEmailMissing):
        _sign_in(users, _identity("apple", "a-1", email=None))

    assert _count(users, "users") == 0


def test_an_unverified_email_writes_nothing(users):
    users.create_user("ana@example.com", "hash")

    with pytest.raises(ProviderEmailUnverified):
        _sign_in(users, _identity(verified=False))

    assert _count(users, "identities") == 0


def test_a_linked_apple_identity_without_an_email_still_signs_in(users):
    first, _ = _sign_in(users, _identity("apple", "a-1", "relay@privaterelay.appleid.com"))

    again, created = _sign_in(users, _identity("apple", "a-1", email=None))

    assert (again.id, created) == (first.id, False)


def test_a_second_identity_of_the_same_provider_is_refused_and_changes_nothing(users):
    user, _ = _sign_in(users, _identity(subject="g-1"))

    with pytest.raises(ProviderAlreadyLinked):
        _sign_in(users, _identity(subject="g-2"))

    assert users.list_providers(user.id) == ["google"]
    assert _count(users, "identities") == 1


def test_two_threads_signing_in_the_same_new_identity_create_one_account(users):
    barrier = threading.Barrier(4)
    results = []

    def run():
        barrier.wait()
        results.append(_sign_in(users, _identity()))

    threads = [threading.Thread(target=run) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _count(users, "users") == 1
    assert len({user.id for user, _ in results}) == 1
    assert sorted(created for _, created in results) == [False, False, False, True]


def test_identities_are_deleted_with_their_user(users):
    user, _ = _sign_in(users, _identity())

    users.delete_user(user.id)

    assert _count(users, "identities") == 0
    assert _sign_in(users, _identity())[1] is True


def test_has_identity_matches_provider_and_subject_for_that_user_only(users):
    user, _ = _sign_in(users, _identity())
    other, _ = _sign_in(users, _identity(subject="g-2", email="ben@example.com"))

    assert users.has_identity(user.id, "google", "g-1") is True
    assert users.has_identity(user.id, "google", "g-2") is False
    assert users.has_identity(other.id, "google", "g-1") is False
    assert users.has_identity(user.id, "apple", "g-1") is False


def test_providers_are_listed_sorted(users):
    user, _ = _sign_in(users, _identity())
    _sign_in(users, _identity("apple", "a-1"))

    assert users.list_providers(user.id) == ["apple", "google"]


def test_the_apple_refresh_token_is_stored_for_the_apple_identity_only(users):
    user, _ = _sign_in(users, _identity())
    _sign_in(users, _identity("apple", "a-1"))
    assert users.get_apple_refresh_token(user.id) is None

    users.set_apple_refresh_token(user.id, "refresh-1")

    assert users.get_apple_refresh_token(user.id) == "refresh-1"
    google_token = users._conn.execute(
        "SELECT apple_refresh_token FROM identities WHERE provider = 'google'"
    ).fetchone()[0]
    assert google_token is None


def test_setting_an_apple_token_without_an_apple_identity_stores_nothing(users):
    user, _ = _sign_in(users, _identity())

    users.set_apple_refresh_token(user.id, "refresh-1")

    assert users.get_apple_refresh_token(user.id) is None


def test_the_apple_refresh_token_is_gone_after_the_user_is_deleted(users):
    user, _ = _sign_in(users, _identity("apple", "a-1"))
    users.set_apple_refresh_token(user.id, "refresh-1")

    users.delete_user(user.id)

    assert users.get_apple_refresh_token(user.id) is None
    assert _count(users, "identities") == 0


def test_creating_an_account_without_an_age_decision_raises_age_required_and_writes_nothing(users):
    with pytest.raises(AgeRequired):
        users.sign_in_with_identity(_identity(), NOW)

    assert _count(users, "users") == 0
    assert _count(users, "identities") == 0


def test_creating_an_account_for_a_minor_raises_under_age_and_writes_nothing(users):
    with pytest.raises(UnderAgeSignUp):
        users.sign_in_with_identity(_identity(), NOW, adult_confirmed=False)

    assert _count(users, "users") == 0


def test_an_adult_decision_creates_the_account_with_its_age_confirmed(users):
    user, created = users.sign_in_with_identity(_identity(), NOW, adult_confirmed=True)

    assert created is True
    assert user.age_confirmed_at == NOW.isoformat()


def test_a_linked_identity_ignores_the_age_decision(users):
    users.sign_in_with_identity(_identity(), NOW, adult_confirmed=True)

    user, created = users.sign_in_with_identity(_identity(), NOW)

    assert created is False
    assert user.email == "ana@example.com"


def test_linking_by_email_ignores_the_age_decision_and_leaves_the_age_unconfirmed(users):
    existing = users.create_user("ana@example.com", "hash")

    user, created = users.sign_in_with_identity(_identity(), NOW)

    assert (user.id, created) == (existing.id, False)
    assert user.age_confirmed is False
