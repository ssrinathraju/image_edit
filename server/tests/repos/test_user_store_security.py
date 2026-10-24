import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    hash_code,
)
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.user_store import (
    EmailChange,
    EmailTakenError,
    LastSignInMethod,
    ProviderAlreadyLinked,
    ProviderInUse,
    ProviderNotLinked,
)
from image_edit_server.repos.user_store import SqliteUserStore

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LIMITS = CodeLimits(
    ttl=timedelta(minutes=15), resend_interval=timedelta(seconds=60), max_per_hour=5
)
MAX_ATTEMPTS = 5
CHANGE = CodePurpose.EMAIL_CHANGE
NEW = "new@example.com"


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def ana(users):
    return users.create_user("ana@example.com", "hash-1")


def _identity(provider="google", subject="g-1", email="ana@example.com") -> ProviderIdentity:
    return ProviderIdentity(provider, subject, email, True, T0)


def _request(users, user, code="123456", email=NEW, at=T0):
    return users.request_email_change(
        user.id, email, hash_code(email, CHANGE, code), at, LIMITS
    )


def _confirm(users, user, code="123456", at=T0, keep="keep"):
    return users.confirm_email_change(user.id, code, at, MAX_ATTEMPTS, keep)


def _session_valid(users, token) -> bool:
    return users.get_user_by_session(token) is not None


# ── set_password ──


def test_set_password_keeps_only_the_given_session(users, ana):
    keep = users.create_session(ana.id, timedelta(days=1))
    other = users.create_session(ana.id, timedelta(days=1))

    users.set_password(ana.id, "hash-2", keep)

    assert users.get_password_hash(ana.id) == "hash-2"
    assert _session_valid(users, keep)
    assert not _session_valid(users, other)


def test_set_password_leaves_other_accounts_sessions(users, ana):
    ben = users.create_user("ben@example.com", "hash-b")
    ben_token = users.create_session(ben.id, timedelta(days=1))
    keep = users.create_session(ana.id, timedelta(days=1))

    users.set_password(ana.id, "hash-2", keep)

    assert _session_valid(users, ben_token)


# ── email change ──


def test_a_request_stores_the_pending_address_without_changing_the_email(users, ana):
    result = _request(users, ana)

    assert result.issued
    assert users.get_pending_email_change(ana.id) == NEW
    assert users.get_by_id(ana.id).email == "ana@example.com"


def test_a_second_request_replaces_the_pending_address(users, ana):
    _request(users, ana, email="first@example.com")
    _request(users, ana, email="second@example.com", at=T0 + timedelta(minutes=2))

    assert users.get_pending_email_change(ana.id) == "second@example.com"


def test_a_request_for_a_taken_address_writes_nothing(users, ana):
    users.create_user(NEW, "hash-b")

    with pytest.raises(EmailTakenError):
        _request(users, ana)

    assert users.get_pending_email_change(ana.id) is None


def test_a_limited_request_keeps_the_earlier_pending_change(users, ana):
    _request(users, ana, code="111111")

    result = _request(users, ana, code="222222", at=T0 + timedelta(seconds=20))

    assert not result.issued and result.retry_after_seconds == 40
    assert _confirm(users, ana, code="111111")[0] is ConsumeResult.OK


def test_confirming_changes_the_email_and_keeps_only_this_session(users, ana):
    keep = users.create_session(ana.id, timedelta(days=1))
    other = users.create_session(ana.id, timedelta(days=1))
    _request(users, ana)

    result, change = _confirm(users, ana, keep=keep)

    assert result is ConsumeResult.OK
    assert change == EmailChange("ana@example.com", NEW)
    assert users.get_by_id(ana.id).email == NEW
    assert users.get_by_email("ana@example.com") is None
    assert users.get_pending_email_change(ana.id) is None
    assert _session_valid(users, keep) and not _session_valid(users, other)


def test_a_code_works_only_once(users, ana):
    _request(users, ana)
    _confirm(users, ana)

    result, change = _confirm(users, ana)

    assert result is ConsumeResult.EXPIRED and change is None


def test_a_wrong_code_changes_nothing_and_counts_an_attempt(users, ana):
    _request(users, ana)

    result, change = _confirm(users, ana, code="000000")

    assert result is ConsumeResult.WRONG and change is None
    assert users.get_by_id(ana.id).email == "ana@example.com"
    assert users.get_pending_email_change(ana.id) == NEW
    assert _confirm(users, ana)[0] is ConsumeResult.OK


def test_five_wrong_codes_use_the_code_up(users, ana):
    _request(users, ana)
    for _ in range(MAX_ATTEMPTS):
        _confirm(users, ana, code="000000")

    assert _confirm(users, ana)[0] is ConsumeResult.EXPIRED


def test_an_expired_code_is_refused(users, ana):
    _request(users, ana)

    result, _ = _confirm(users, ana, at=T0 + timedelta(minutes=16))

    assert result is ConsumeResult.EXPIRED
    assert users.get_by_id(ana.id).email == "ana@example.com"


def test_confirming_without_a_pending_change_is_expired(users, ana):
    assert _confirm(users, ana)[0] is ConsumeResult.EXPIRED


def test_an_address_taken_meanwhile_gives_taken_and_discards_the_pending_change(users, ana):
    _request(users, ana)
    users.create_user(NEW, "hash-b")

    with pytest.raises(EmailTakenError):
        _confirm(users, ana)

    assert users.get_by_id(ana.id).email == "ana@example.com"
    assert users.get_pending_email_change(ana.id) is None
    assert _confirm(users, ana)[0] is ConsumeResult.EXPIRED


def test_the_unique_constraint_is_the_final_guard(users, ana, monkeypatch):
    _request(users, ana)
    monkeypatch.setattr(users, "_email_has_account", lambda email: False)
    users.create_user(NEW, "hash-b")

    with pytest.raises(EmailTakenError):
        _confirm(users, ana)

    assert users.get_by_id(ana.id).email == "ana@example.com"


def test_deleting_the_account_removes_its_pending_change_and_code(users, ana):
    _request(users, ana)

    users.delete_user(ana.id)

    count = users._conn.execute("SELECT COUNT(*) FROM pending_email_changes").fetchone()[0]
    codes = users._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0]
    assert (count, codes) == (0, 0)


def test_stale_pending_changes_are_pruned_after_a_day(users, ana):
    _request(users, ana)

    users.prune_email_rows(T0 + timedelta(hours=25))

    assert users.get_pending_email_change(ana.id) is None


def test_email_change_codes_count_toward_the_hourly_cap(users, ana):
    for minute in range(4):
        users.issue_code(
            NEW,
            CodePurpose.REGISTRATION,
            hash_code(NEW, CodePurpose.REGISTRATION, "111111"),
            T0 + timedelta(minutes=minute * 2),
            LIMITS,
        )
    assert _request(users, ana, at=T0 + timedelta(minutes=8)).issued

    limited = users.issue_code(
        NEW,
        CodePurpose.PASSWORD_RESET,
        hash_code(NEW, CodePurpose.PASSWORD_RESET, "222222"),
        T0 + timedelta(minutes=10),
        LIMITS,
    )

    assert not limited.issued


def test_email_change_and_registration_codes_are_separate(users, ana):
    users.issue_code(NEW, CodePurpose.REGISTRATION, hash_code(NEW, CodePurpose.REGISTRATION, "111111"), T0, LIMITS)
    _request(users, ana, at=T0 + timedelta(minutes=2))

    assert users.consume_code(NEW, CodePurpose.REGISTRATION, "123456", T0, MAX_ATTEMPTS) is ConsumeResult.WRONG
    assert users.consume_code(NEW, CodePurpose.REGISTRATION, "111111", T0, MAX_ATTEMPTS) is ConsumeResult.OK
    assert _confirm(users, ana, at=T0 + timedelta(minutes=3))[0] is ConsumeResult.OK


# ── link and unlink ──


def test_link_identity_adds_the_provider(users, ana):
    users.link_identity(ana.id, _identity(email="other@example.com"), T0)

    assert users.list_providers(ana.id) == ["google"]
    assert users.get_by_id(ana.id).email == "ana@example.com"


def test_linked_identity_signs_in_to_the_account(users, ana):
    users.link_identity(ana.id, _identity(email="other@example.com"), T0)

    user, created = users.sign_in_with_identity(_identity(email="other@example.com"), T0)

    assert user.id == ana.id and not created


def test_link_identity_used_by_another_account_is_refused(users, ana):
    ben = users.create_user("ben@example.com", "hash-b")
    users.link_identity(ben.id, _identity(), T0)

    with pytest.raises(ProviderInUse):
        users.link_identity(ana.id, _identity(), T0)

    assert users.list_providers(ana.id) == []


def test_linking_a_second_identity_of_one_provider_is_refused(users, ana):
    users.link_identity(ana.id, _identity(subject="g-1"), T0)

    with pytest.raises(ProviderAlreadyLinked):
        users.link_identity(ana.id, _identity(subject="g-2"), T0)
    with pytest.raises(ProviderAlreadyLinked):
        users.link_identity(ana.id, _identity(subject="g-1"), T0)


def test_link_identity_without_an_email_is_allowed(users, ana):
    users.link_identity(ana.id, _identity(email=None), T0)

    assert users.list_providers(ana.id) == ["google"]


def test_unlink_removes_the_identity_when_a_password_remains(users, ana):
    users.link_identity(ana.id, _identity(), T0)

    assert users.unlink_identity(ana.id, "google") is None

    assert users.list_providers(ana.id) == []
    user, created = users.sign_in_with_identity(_identity(email="fresh@example.com"), T0, True)
    assert created and user.id != ana.id


def test_unlink_returns_the_apple_refresh_token(users, ana):
    users.link_identity(ana.id, _identity("apple", "a-1"), T0)
    users.set_apple_refresh_token(ana.id, "refresh-1")

    assert users.unlink_identity(ana.id, "apple") == "refresh-1"


def test_unlink_is_allowed_when_another_provider_remains(users):
    user, _ = users.sign_in_with_identity(_identity(), T0, True)
    users.link_identity(user.id, _identity("apple", "a-1"), T0)

    users.unlink_identity(user.id, "google")

    assert users.list_providers(user.id) == ["apple"]


def test_unlinking_the_last_method_is_refused_and_changes_nothing(users):
    user, _ = users.sign_in_with_identity(_identity(), T0, True)

    with pytest.raises(LastSignInMethod):
        users.unlink_identity(user.id, "google")

    assert users.list_providers(user.id) == ["google"]


def test_unlink_of_a_provider_the_account_lacks_is_not_linked(users, ana):
    with pytest.raises(ProviderNotLinked):
        users.unlink_identity(ana.id, "google")


def test_deleting_the_account_removes_nothing_it_should_keep(users, ana):
    users.link_identity(ana.id, _identity(), T0)

    users.delete_user(ana.id)

    assert users._conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0


# ── migration ──


def _tables(path) -> set:
    conn = sqlite3.connect(path)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


@pytest.fixture
def v6_db(tmp_path) -> str:
    path = str(tmp_path / "v6.db")
    first = SqliteUserStore(path)
    first.create_user("ana@example.com", "hash-1")
    first.close()
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE pending_email_changes")
    conn.execute("PRAGMA user_version = 6")
    conn.commit()
    conn.close()
    return path


def test_upgrading_a_v6_database_adds_the_pending_table_and_keeps_accounts(v6_db):
    assert "pending_email_changes" not in _tables(v6_db)

    store = SqliteUserStore(v6_db)

    assert "pending_email_changes" in _tables(v6_db)
    assert store.get_by_email("ana@example.com") is not None
    conn = sqlite3.connect(v6_db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 7
    conn.close()


def test_running_the_v7_migration_twice_keeps_pending_changes(v6_db):
    first = SqliteUserStore(v6_db)
    user = first.get_by_email("ana@example.com")
    _request(first, user)
    first.close()

    second = SqliteUserStore(v6_db)

    assert second.get_pending_email_change(user.id) == NEW
