import threading
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    hash_code,
)
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.user_store import EmailTakenError
from image_edit_server.repos.user_store import SqliteUserStore

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LIMITS = CodeLimits(
    ttl=timedelta(minutes=15), resend_interval=timedelta(seconds=60), max_per_hour=5
)
EMAIL = "ana@example.com"
BONUS = 5
MAX = 10


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _start(users, code="111111", password_hash="hash-1", at=T0, email=EMAIL):
    purpose = CodePurpose.REGISTRATION
    return users.start_registration(
        email, password_hash, None, hash_code(email, purpose, code), at, LIMITS
    )


def _confirm(users, code="111111", at=T0, email=EMAIL):
    return users.confirm_registration(email, code, at, 5, BONUS, MAX)


def _count(users, table) -> int:
    return users._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_start_stores_a_pending_row_and_a_code_but_no_account(users):
    result = _start(users)

    assert result.issued is True
    row = users._conn.execute(
        "SELECT email, password_hash, referral_code FROM pending_registrations"
    ).fetchone()
    assert row == (EMAIL, "hash-1", None)
    assert _count(users, "email_codes") == 1
    assert _count(users, "email_sends") == 1
    assert users.get_by_email(EMAIL) is None


def test_a_second_start_after_a_minute_replaces_the_row_and_the_code(users):
    _start(users, code="111111", password_hash="hash-1")

    later = T0 + timedelta(seconds=61)
    assert _start(users, code="222222", password_hash="hash-2", at=later).issued

    assert _count(users, "pending_registrations") == 1
    assert _confirm(users, "111111", later)[0] is ConsumeResult.WRONG
    result, user = _confirm(users, "222222", later)
    assert result is ConsumeResult.OK
    assert users.get_password_hash(user.id) == "hash-2"


def test_a_second_start_within_a_minute_is_limited_and_keeps_the_first(users):
    _start(users, code="111111", password_hash="hash-1")

    soon = T0 + timedelta(seconds=20)
    result = _start(users, code="222222", password_hash="hash-2", at=soon)

    assert (result.issued, result.retry_after_seconds) == (False, 40)
    stored = users._conn.execute(
        "SELECT password_hash FROM pending_registrations"
    ).fetchone()[0]
    assert stored == "hash-1"
    result, user = _confirm(users, "111111", soon)
    assert result is ConsumeResult.OK
    assert users.get_password_hash(user.id) == "hash-1"


def test_confirm_creates_a_verified_account_with_the_pending_password(users):
    _start(users)

    result, user = _confirm(users)

    assert result is ConsumeResult.OK
    assert (user.email, user.has_password) == (EMAIL, True)
    assert users.get_password_hash(user.id) == "hash-1"
    assert len(user.referral_code) == 8
    assert users._conn.execute("SELECT email_verified, created_via FROM users").fetchone() == (
        1,
        "password",
    )
    assert _count(users, "pending_registrations") == 0


def test_a_wrong_code_counts_an_attempt_and_creates_nothing(users):
    _start(users)

    result, user = _confirm(users, "000000")

    assert (result, user) == (ConsumeResult.WRONG, None)
    attempts = users._conn.execute("SELECT attempts FROM email_codes").fetchone()[0]
    assert attempts == 1
    assert users.get_by_email(EMAIL) is None
    assert _count(users, "pending_registrations") == 1


def test_five_wrong_codes_make_the_correct_one_expired(users):
    _start(users)
    for _ in range(5):
        _confirm(users, "000000")

    assert _confirm(users) == (ConsumeResult.EXPIRED, None)


def test_an_expired_code_creates_nothing(users):
    _start(users)

    result, user = _confirm(users, at=T0 + timedelta(minutes=16))

    assert (result, user) == (ConsumeResult.EXPIRED, None)
    assert users.get_by_email(EMAIL) is None


def test_confirming_with_no_pending_registration_is_expired(users):
    assert _confirm(users) == (ConsumeResult.EXPIRED, None)


def test_a_code_with_no_pending_row_is_expired_and_creates_nothing(users):
    _start(users)
    users._conn.execute("DELETE FROM pending_registrations")

    assert _confirm(users) == (ConsumeResult.EXPIRED, None)
    assert users.get_by_email(EMAIL) is None


def test_an_email_taken_meanwhile_raises_and_discards_the_pending_row(users):
    _start(users)
    users.create_user(EMAIL, "someone-elses")

    with pytest.raises(EmailTakenError):
        _confirm(users)

    assert _count(users, "pending_registrations") == 0
    existing = users.get_by_email(EMAIL)
    assert users.get_password_hash(existing.id) == "someone-elses"


def test_start_for_an_email_that_has_an_account_is_refused_and_writes_nothing(users):
    users.create_user(EMAIL, "hash")

    with pytest.raises(EmailTakenError):
        _start(users)

    assert _count(users, "pending_registrations") == 0
    assert _count(users, "email_codes") == 0


def test_a_provider_creating_the_account_discards_the_pending_row(users):
    _start(users)
    identity = ProviderIdentity("google", "g-1", EMAIL, True, T0)

    user, created = users.sign_in_with_identity(identity, T0)

    assert created is True
    assert _count(users, "pending_registrations") == 0
    with pytest.raises(EmailTakenError):
        _confirm(users)
    assert users.get_by_email(EMAIL).id == user.id
    assert users.get_password_hash(user.id) == ""


def test_two_threads_confirming_the_same_registration_create_one_account(users):
    _start(users)
    barrier = threading.Barrier(6)
    results = []

    def run():
        barrier.wait()
        results.append(_confirm(users)[0])

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert _count(users, "users") == 1
    assert results.count(ConsumeResult.OK) == 1


def test_pending_rows_older_than_24_hours_are_pruned_by_the_next_start(users):
    _start(users, email="old@example.com")
    _start(users, email="mid@example.com", at=T0 + timedelta(hours=23))

    _start(users, email="new@example.com", at=T0 + timedelta(hours=25))

    emails = {
        row[0] for row in users._conn.execute("SELECT email FROM pending_registrations")
    }
    assert emails == {"mid@example.com", "new@example.com"}
