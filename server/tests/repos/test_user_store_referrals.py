import pytest

from image_edit_server.core.user_store import EmailTakenError, InvalidReferralCode
from image_edit_server.repos.user_store import SqliteUserStore

BONUS = 5
MAX = 10


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _register(users, email, code=None):
    return users.register_user(email, "hash", code)


def _verify(users, user, max_rewards=MAX) -> bool:
    return users.mark_email_verified(user.id, BONUS, max_rewards)


def _bonus(users, user) -> int:
    return users.get_by_id(user.id).bonus_credits


def test_registration_pays_nobody(users):
    referrer = _register(users, "a@example.com")

    friend = _register(users, "b@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)
    assert _bonus(users, friend) == 0
    assert users.get_by_id(friend.id).email_verified is False


def test_verification_pays_both_accounts(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "b@example.com", referrer.referral_code)

    assert _verify(users, friend) is True

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)
    assert _bonus(users, friend) == BONUS
    assert users.get_by_id(friend.id).email_verified is True


def test_a_second_verification_pays_nothing(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "b@example.com", referrer.referral_code)
    _verify(users, friend)

    assert _verify(users, friend) is False

    assert _bonus(users, referrer) == BONUS
    assert _bonus(users, friend) == BONUS


def test_an_account_without_a_referral_gets_nothing(users):
    user = _register(users, "a@example.com")

    assert _verify(users, user) is True

    assert _bonus(users, user) == 0
    assert users.get_by_id(user.id).email_verified is True


def test_verifying_an_unknown_user_returns_false(users):
    assert users.mark_email_verified("nobody", BONUS, MAX) is False


def test_code_matching_ignores_case_and_spaces(users):
    referrer = _register(users, "a@example.com")

    friend = _register(users, "b@example.com", f"  {referrer.referral_code.lower()} ")
    _verify(users, friend)

    assert users.get_by_id(referrer.id).referral_rewards == 1


def test_blank_code_means_no_referral(users):
    friend = _register(users, "b@example.com", "   ")
    _verify(users, friend)

    assert _bonus(users, friend) == 0


def test_unknown_code_writes_nothing(users):
    with pytest.raises(InvalidReferralCode):
        _register(users, "b@example.com", "NOSUCH22")

    assert users.get_by_email("b@example.com") is None


def test_duplicate_email_leaves_the_referrer_unrewarded(users):
    referrer = _register(users, "a@example.com")
    _register(users, "taken@example.com")

    with pytest.raises(EmailTakenError):
        _register(users, "taken@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)


def test_cap_rewards_only_the_friend(users):
    referrer = _register(users, "a@example.com")
    for i in range(2):
        _verify(users, _register(users, f"f{i}@example.com", referrer.referral_code), max_rewards=2)

    late = _register(users, "late@example.com", referrer.referral_code)
    _verify(users, late, max_rewards=2)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (2 * BONUS, 2)
    assert _bonus(users, late) == BONUS


def test_deleting_a_friend_does_not_reopen_the_cap(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code)
    _verify(users, friend, max_rewards=1)

    users.delete_user(friend.id)
    other = _register(users, "g@example.com", referrer.referral_code)
    _verify(users, other, max_rewards=1)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)


def test_a_deleted_referrer_still_lets_the_friend_be_paid(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code)

    users.delete_user(referrer.id)
    row = users._conn.execute(
        "SELECT referred_by FROM users WHERE id = ?", (friend.id,)
    ).fetchone()
    assert row[0] is None
    _verify(users, friend)

    assert _bonus(users, friend) == BONUS


def test_every_account_gets_a_distinct_code(users):
    codes = {_register(users, f"u{i}@example.com").referral_code for i in range(25)}

    assert len(codes) == 25


def test_a_referral_code_collision_is_not_reported_as_a_taken_email(users, monkeypatch):
    import sqlite3

    existing = _register(users, "a@example.com")
    monkeypatch.setattr(users, "_unused_code", lambda: existing.referral_code)

    with pytest.raises(sqlite3.IntegrityError):
        _register(users, "b@example.com")

    assert users.get_by_email("b@example.com") is None
