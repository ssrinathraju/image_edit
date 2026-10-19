from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    hash_code,
)
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.core.referral_codes import REDEEM_WINDOW
from image_edit_server.core.user_store import (
    EmailTakenError,
    InvalidReferralCode,
    ReferralNotAllowed,
    UserNotFound,
)
from image_edit_server.repos.user_store import SqliteUserStore
from tests.helpers import confirm_in_store

BONUS = 5
MAX = 10
T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
LIMITS = CodeLimits(
    ttl=timedelta(minutes=15), resend_interval=timedelta(seconds=60), max_per_hour=5
)
CODE = "111111"


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _start(users, email, code=None):
    purpose = CodePurpose.REGISTRATION
    return users.start_registration(
        email, "hash", code, hash_code(email, purpose, CODE), T0, LIMITS
    )


def _confirm(users, email, max_rewards=MAX):
    return confirm_in_store(users, email, CODE, T0, 5, BONUS, max_rewards)


def _register(users, email, code=None, max_rewards=MAX):
    """Start and confirm a registration; returns the created user."""
    _start(users, email, code)
    result, user = _confirm(users, email, max_rewards)
    assert result is ConsumeResult.OK
    return user


def _bonus(users, user) -> int:
    return users.get_by_id(user.id).bonus_credits


def test_starting_a_registration_pays_nobody_and_creates_no_account(users):
    referrer = _register(users, "a@example.com")

    _start(users, "b@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)
    assert users.get_by_email("b@example.com") is None


def test_confirming_pays_both_accounts(users):
    referrer = _register(users, "a@example.com")

    friend = _register(users, "b@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)
    assert _bonus(users, friend) == BONUS


def test_a_registration_without_a_referral_gets_nothing(users):
    user = _register(users, "a@example.com")

    assert _bonus(users, user) == 0


def test_code_matching_ignores_case_and_spaces(users):
    referrer = _register(users, "a@example.com")

    _register(users, "b@example.com", f"  {referrer.referral_code.lower()} ")

    assert users.get_by_id(referrer.id).referral_rewards == 1


def test_blank_code_means_no_referral(users):
    friend = _register(users, "b@example.com", "   ")

    assert _bonus(users, friend) == 0


def test_unknown_code_writes_nothing(users):
    with pytest.raises(InvalidReferralCode):
        _start(users, "b@example.com", "NOSUCH22")

    assert users._conn.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[0] == 0
    assert users._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0] == 0


def test_duplicate_email_leaves_the_referrer_unrewarded(users):
    referrer = _register(users, "a@example.com")
    _register(users, "taken@example.com")

    with pytest.raises(EmailTakenError):
        _start(users, "taken@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)


def test_cap_rewards_only_the_friend(users):
    referrer = _register(users, "a@example.com")
    for i in range(2):
        _register(users, f"f{i}@example.com", referrer.referral_code, max_rewards=2)

    late = _register(users, "late@example.com", referrer.referral_code, max_rewards=2)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (2 * BONUS, 2)
    assert _bonus(users, late) == BONUS


def test_deleting_a_friend_does_not_reopen_the_cap(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code, max_rewards=1)

    users.delete_user(friend.id)
    _register(users, "g@example.com", referrer.referral_code, max_rewards=1)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)


def test_a_referrer_deleted_before_confirming_still_lets_the_friend_be_paid(users):
    referrer = _register(users, "a@example.com")
    _start(users, "f@example.com", referrer.referral_code)

    users.delete_user(referrer.id)
    result, friend = _confirm(users, "f@example.com")

    assert result is ConsumeResult.OK
    assert _bonus(users, friend) == BONUS
    row = users._conn.execute(
        "SELECT referred_by FROM users WHERE id = ?", (friend.id,)
    ).fetchone()
    assert row[0] is None


def test_a_later_password_reset_pays_nothing_more(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code)
    purpose = CodePurpose.PASSWORD_RESET
    users.issue_code(friend.email, purpose, hash_code(friend.email, purpose, CODE), T0, LIMITS)

    users.reset_password(friend.email, CODE, "new-hash", T0, 5)

    assert _bonus(users, friend) == BONUS
    assert _bonus(users, referrer) == BONUS


def test_every_account_gets_a_distinct_code(users):
    codes = {users.create_user(f"u{i}@example.com", "h").referral_code for i in range(25)}

    assert len(codes) == 25


def test_a_referral_code_collision_is_not_reported_as_a_taken_email(users, monkeypatch):
    import sqlite3

    existing = users.create_user("a@example.com", "h")
    monkeypatch.setattr(users, "_unused_code", lambda: existing.referral_code)

    with pytest.raises(sqlite3.IntegrityError):
        users.create_user("b@example.com", "h")

    assert users.get_by_email("b@example.com") is None


# ── redeeming a code after a provider sign-up ──

CREATED = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def _provider_user(users, subject="g-1", email="new@example.com"):
    identity = ProviderIdentity("google", subject, email, True, CREATED)
    return users.sign_in_with_identity(identity, CREATED, adult_confirmed=True)[0]


def _redeem_after(users, user, code, hours=1):
    users.redeem_referral(
        user.id, code, CREATED + timedelta(hours=hours), REDEEM_WINDOW, BONUS, MAX
    )


def test_success_pays_both_accounts(users):
    friend = users.create_user("friend@example.com", "hash")
    user = _provider_user(users)

    _redeem_after(users, user, friend.referral_code)

    assert _bonus(users, user) == BONUS
    after = users.get_by_id(friend.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)


def test_a_lowercase_code_with_spaces_is_accepted(users):
    friend = users.create_user("friend@example.com", "hash")
    user = _provider_user(users)

    _redeem_after(users, user, f"  {friend.referral_code.lower()} ")

    assert _bonus(users, user) == BONUS


def test_a_second_redemption_is_refused(users):
    friend = users.create_user("friend@example.com", "hash")
    other = users.create_user("other@example.com", "hash")
    user = _provider_user(users)
    _redeem_after(users, user, friend.referral_code)

    with pytest.raises(ReferralNotAllowed):
        _redeem_after(users, user, other.referral_code)

    assert _bonus(users, other) == 0
    assert _bonus(users, user) == BONUS


def test_a_password_created_account_is_refused(users):
    friend = users.create_user("friend@example.com", "hash")
    mine = users.create_user("mine@example.com", "hash")

    with pytest.raises(ReferralNotAllowed):
        users.redeem_referral(
            mine.id, friend.referral_code, datetime.now(timezone.utc), REDEEM_WINDOW, BONUS, MAX
        )

    assert _bonus(users, mine) == 0


def test_an_account_already_linked_to_a_referrer_is_refused(users):
    friend = users.create_user("friend@example.com", "hash")
    other = users.create_user("other@example.com", "hash")
    user = _provider_user(users)
    users._conn.execute("UPDATE users SET referred_by = ? WHERE id = ?", (friend.id, user.id))

    with pytest.raises(ReferralNotAllowed):
        _redeem_after(users, user, other.referral_code)

    assert _bonus(users, user) == 0


def test_twenty_three_hours_is_accepted_and_twenty_five_refused(users):
    friend = users.create_user("friend@example.com", "hash")
    early = _provider_user(users, "g-1", "early@example.com")
    late = _provider_user(users, "g-2", "late@example.com")

    _redeem_after(users, early, friend.referral_code, hours=23)
    with pytest.raises(ReferralNotAllowed):
        _redeem_after(users, late, friend.referral_code, hours=25)

    assert _bonus(users, early) == BONUS
    assert _bonus(users, late) == 0


def test_the_accounts_own_code_and_an_unknown_code_change_nothing(users):
    user = _provider_user(users)
    own = users.get_by_id(user.id).referral_code

    for code in (own, "ZZZZZZZZ", ""):
        with pytest.raises(InvalidReferralCode):
            _redeem_after(users, user, code)

    after = users.get_by_id(user.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)
    friend = users.create_user("friend@example.com", "hash")
    _redeem_after(users, user, friend.referral_code)
    assert _bonus(users, user) == BONUS


def test_the_referrer_cap_stops_rewarding_the_referrer_only(users):
    friend = users.create_user("friend@example.com", "hash")
    users._conn.execute(
        "UPDATE users SET referral_rewards = ?, bonus_credits = 0 WHERE id = ?",
        (MAX, friend.id),
    )
    user = _provider_user(users)

    _redeem_after(users, user, friend.referral_code)

    after = users.get_by_id(friend.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, MAX)
    assert _bonus(users, user) == BONUS


def test_a_missing_user_is_reported(users):
    with pytest.raises(UserNotFound):
        users.redeem_referral("nobody", "AAAAAAAA", CREATED, REDEEM_WINDOW, BONUS, MAX)
