import threading
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
MAX_ATTEMPTS = 5
VERIFY = CodePurpose.VERIFY_EMAIL
RESET = CodePurpose.PASSWORD_RESET


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def uid(users) -> str:
    return users.create_user("ana@example.com", "hash").id


def _issue(users, uid, code, at=T0, purpose=VERIFY):
    return users.issue_code(uid, purpose, hash_code(uid, purpose, code), at, LIMITS)


def _consume(users, uid, code, at=T0, purpose=VERIFY):
    return users.consume_code(uid, purpose, code, at, MAX_ATTEMPTS)


def _minutes(n: float) -> datetime:
    return T0 + timedelta(minutes=n)


def test_a_new_code_replaces_the_old_one(users, uid):
    _issue(users, uid, "111111")
    _issue(users, uid, "222222", _minutes(2))

    assert _consume(users, uid, "111111", _minutes(3)) is ConsumeResult.WRONG
    assert _consume(users, uid, "222222", _minutes(3)) is ConsumeResult.OK


def test_purposes_are_independent(users, uid):
    _issue(users, uid, "111111", purpose=VERIFY)
    _issue(users, uid, "222222", _minutes(2), purpose=RESET)

    assert _consume(users, uid, "111111", _minutes(3), purpose=RESET) is ConsumeResult.WRONG
    assert _consume(users, uid, "222222", _minutes(3), purpose=VERIFY) is ConsumeResult.WRONG
    assert _consume(users, uid, "111111", _minutes(3), purpose=VERIFY) is ConsumeResult.OK
    assert _consume(users, uid, "222222", _minutes(3), purpose=RESET) is ConsumeResult.OK


def test_a_used_code_is_rejected_the_second_time(users, uid):
    _issue(users, uid, "111111")

    assert _consume(users, uid, "111111") is ConsumeResult.OK
    assert _consume(users, uid, "111111") is ConsumeResult.EXPIRED


def test_a_code_that_was_never_issued_is_expired(users, uid):
    assert _consume(users, uid, "111111") is ConsumeResult.EXPIRED


def test_a_code_is_accepted_at_14_minutes_and_expired_at_16(users, uid):
    _issue(users, uid, "111111")

    assert _consume(users, uid, "111111", _minutes(16)) is ConsumeResult.EXPIRED
    assert _consume(users, uid, "111111", _minutes(14)) is ConsumeResult.OK


def test_five_wrong_attempts_make_the_correct_code_expired(users, uid):
    _issue(users, uid, "111111")

    results = [_consume(users, uid, "000000") for _ in range(5)]

    assert results == [ConsumeResult.WRONG] * 5
    assert _consume(users, uid, "111111") is ConsumeResult.EXPIRED


def test_a_new_code_resets_the_attempt_count(users, uid):
    _issue(users, uid, "111111")
    for _ in range(5):
        _consume(users, uid, "000000")

    _issue(users, uid, "222222", _minutes(2))

    assert _consume(users, uid, "222222", _minutes(2)) is ConsumeResult.OK


def test_a_second_send_within_a_minute_is_limited_and_keeps_the_first_code(users, uid):
    assert _issue(users, uid, "111111").issued

    result = _issue(users, uid, "222222", T0 + timedelta(seconds=20))

    assert (result.issued, result.retry_after_seconds) == (False, 40)
    assert _consume(users, uid, "222222", T0 + timedelta(seconds=21)) is ConsumeResult.WRONG
    assert _consume(users, uid, "111111", T0 + timedelta(seconds=21)) is ConsumeResult.OK


def test_the_hourly_cap_counts_both_purposes(users, uid):
    for i, purpose in enumerate([VERIFY, VERIFY, VERIFY, RESET, RESET]):
        assert _issue(users, uid, "111111", _minutes(i * 2), purpose=purpose).issued

    result = _issue(users, uid, "222222", _minutes(20), purpose=RESET)

    assert result.issued is False
    assert result.retry_after_seconds == 40 * 60


def test_the_cap_frees_up_after_61_minutes(users, uid):
    for i in range(5):
        _issue(users, uid, "111111", _minutes(i * 2))

    assert _issue(users, uid, "222222", _minutes(30)).issued is False
    assert _issue(users, uid, "222222", _minutes(61)).issued is True


def test_the_longer_of_the_two_limits_sets_retry_after(users, uid):
    for i in range(5):
        _issue(users, uid, "111111", _minutes(i * 2))

    result = _issue(users, uid, "222222", _minutes(8) + timedelta(seconds=30))

    assert result.retry_after_seconds == 52 * 60 - 30


def test_old_send_rows_are_pruned_on_the_next_send(users, uid):
    for i in range(3):
        _issue(users, uid, "111111", _minutes(i * 2))

    _issue(users, uid, "222222", _minutes(120))

    assert users._conn.execute("SELECT COUNT(*) FROM email_sends").fetchone()[0] == 1


def test_codes_and_sends_are_removed_with_the_user(users, uid):
    _issue(users, uid, "111111")

    users.delete_user(uid)

    assert users._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0] == 0
    assert users._conn.execute("SELECT COUNT(*) FROM email_sends").fetchone()[0] == 0


def test_the_stored_hash_does_not_contain_the_digits(users, uid):
    _issue(users, uid, "123456")

    stored = users._conn.execute("SELECT code_hash FROM email_codes").fetchone()[0]

    assert "123456" not in stored
    assert stored == hash_code(uid, VERIFY, "123456")


def test_two_threads_consuming_the_same_code_get_exactly_one_ok(users, uid):
    _issue(users, uid, "111111")
    results = []
    barrier = threading.Barrier(8)

    def attempt():
        barrier.wait()
        results.append(_consume(users, uid, "111111"))

    threads = [threading.Thread(target=attempt) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results.count(ConsumeResult.OK) == 1
