import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.user_store import TooManyReports, UserNotFound
from image_edit_server.repos.user_store import SqliteUserStore

NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
WINDOW = timedelta(hours=24)
HOUR = timedelta(hours=1)


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def user(users):
    return users.create_user("ana@example.com", "hash")


def _strikes(users, user, *ages_hours):
    for age in ages_hours:
        users.record_strike(user.id, NOW - timedelta(hours=age), WINDOW)


def _report(users, user, report_id, at=NOW, limit=20, job="job-1", source="none", image=None):
    users.add_report(report_id, user.id, job, "other", "", source, image, at, limit)


def test_two_strikes_do_not_suspend(users, user):
    _strikes(users, user, 5, 1)

    assert users.suspended_until(user.id, NOW, WINDOW, 3) is None


def test_three_strikes_suspend_until_a_window_after_the_third_most_recent(users, user):
    _strikes(users, user, 10, 5, 1)

    assert users.suspended_until(user.id, NOW, WINDOW, 3) == NOW - 10 * HOUR + WINDOW


def test_the_third_most_recent_strike_counts_when_there_are_more_than_three(users, user):
    _strikes(users, user, 20, 10, 5, 1)

    assert users.suspended_until(user.id, NOW, WINDOW, 3) == NOW - 10 * HOUR + WINDOW


def test_the_pause_ends_when_the_oldest_strike_ages_out(users, user):
    _strikes(users, user, 10, 5, 1)

    after = NOW + timedelta(hours=14, minutes=1)

    assert users.suspended_until(user.id, after, WINDOW, 3) is None


def test_a_strike_exactly_a_window_old_no_longer_counts(users, user):
    _strikes(users, user, 24, 5, 1)

    assert users.suspended_until(user.id, NOW, WINDOW, 3) is None


def test_strikes_belong_to_one_account(users, user):
    other = users.create_user("ben@example.com", "hash")
    _strikes(users, user, 3, 2, 1)

    assert users.suspended_until(other.id, NOW, WINDOW, 3) is None


def test_recording_a_strike_prunes_rows_older_than_the_window(users, user):
    _strikes(users, user, 30, 28)
    users.record_strike(user.id, NOW, WINDOW)

    count = users._conn.execute("SELECT COUNT(*) FROM safety_strikes").fetchone()[0]
    assert count == 1


def test_a_strike_for_a_deleted_account_raises_user_not_found(users, user):
    users.delete_user(user.id)

    with pytest.raises(UserNotFound):
        users.record_strike(user.id, NOW, WINDOW)


def test_the_twenty_first_report_in_a_day_is_refused_and_nothing_is_stored(users, user):
    for i in range(20):
        _report(users, user, f"r{i}", at=NOW - timedelta(minutes=i))

    with pytest.raises(TooManyReports):
        _report(users, user, "extra")

    assert len(users.list_open_reports()) == 20
    assert users.get_report("extra") is None


def test_reports_older_than_a_day_do_not_count_against_the_cap(users, user):
    for i in range(20):
        _report(users, user, f"r{i}", at=NOW - timedelta(hours=25))

    _report(users, user, "fresh")

    assert users.get_report("fresh") is not None


def test_the_cap_is_per_account(users, user):
    other = users.create_user("ben@example.com", "hash")
    _report(users, user, "a", limit=1)

    _report(users, other, "b", limit=1)

    assert users.get_report("b") is not None


def test_two_threads_adding_the_last_report_create_exactly_one(users, user):
    for i in range(19):
        _report(users, user, f"r{i}")
    outcomes = []
    barrier = threading.Barrier(2)

    def add(report_id):
        barrier.wait()
        try:
            _report(users, user, report_id)
            outcomes.append("ok")
        except TooManyReports:
            outcomes.append("refused")

    threads = [threading.Thread(target=add, args=(f"t{i}",)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["ok", "refused"]
    assert len(users.list_open_reports()) == 20


def test_open_reports_are_listed_newest_first(users, user):
    _report(users, user, "old", at=NOW - 2 * HOUR)
    _report(users, user, "new", at=NOW)
    _report(users, user, "mid", at=NOW - HOUR)

    assert [r.id for r in users.list_open_reports()] == ["new", "mid", "old"]


def test_a_resolved_report_leaves_the_open_list_and_keeps_its_outcome(users, user):
    _report(users, user, "r1")

    assert users.resolve_report("r1", "removed", NOW) is True

    assert users.list_open_reports() == []
    report = users.get_report("r1")
    assert (report.outcome, report.resolved_at) == ("removed", NOW)


def test_resolving_an_unknown_or_resolved_report_returns_false(users, user):
    _report(users, user, "r1")
    users.resolve_report("r1", "removed", NOW)

    assert users.resolve_report("r1", "again", NOW) is False
    assert users.resolve_report("nope", "x", NOW) is False
    assert users.get_report("r1").outcome == "removed"


def test_expired_reports_are_those_at_least_the_max_age_old_resolved_or_not(users, user):
    _report(users, user, "old", at=NOW - timedelta(days=31))
    _report(users, user, "old-resolved", at=NOW - timedelta(days=31))
    users.resolve_report("old-resolved", "removed", NOW)
    _report(users, user, "young", at=NOW - timedelta(days=29))

    expired = users.expired_reports(NOW, timedelta(days=30))

    assert sorted(r.id for r in expired) == ["old", "old-resolved"]


def test_delete_report_removes_the_row(users, user):
    _report(users, user, "r1")

    users.delete_report("r1")

    assert users.get_report("r1") is None


def test_deleting_the_user_cascades_to_strikes_and_reports(users, user):
    _strikes(users, user, 3, 2, 1)
    _report(users, user, "r1", source="server", image="r1.png")

    users.delete_user(user.id)

    assert users.list_open_reports() == []
    assert users._conn.execute("SELECT COUNT(*) FROM safety_strikes").fetchone()[0] == 0


def test_report_image_names_for_one_reporter_or_everyone(users, user):
    other = users.create_user("ben@example.com", "hash")
    _report(users, user, "a", source="server", image="a.png")
    _report(users, user, "b")
    _report(users, other, "c", source="device", image="c.png")

    assert users.report_image_names(user.id) == ["a.png"]
    assert sorted(users.report_image_names()) == ["a.png", "c.png"]


def test_an_invalid_image_source_is_rejected_by_the_database(users, user):
    with pytest.raises(sqlite3.IntegrityError):
        _report(users, user, "r1", source="cloud")


def test_a_report_from_a_deleted_account_raises_user_not_found(users, user):
    users.delete_user(user.id)

    with pytest.raises(UserNotFound):
        _report(users, user, "r1")
