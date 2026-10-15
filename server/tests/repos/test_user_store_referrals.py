import pytest

from image_edit_server.core.user_store import EmailTakenError, InvalidReferralCode
from image_edit_server.repos.user_store import SqliteUserStore

BONUS = 5
MAX = 10


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _register(users, email, code=None, max_rewards=MAX):
    return users.register_user(email, "hash", code, BONUS, max_rewards)


def test_valid_code_rewards_both_accounts(users):
    referrer = _register(users, "a@example.com")

    friend = _register(users, "b@example.com", referrer.referral_code)

    assert friend.bonus_credits == BONUS
    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)
    assert users.get_by_id(friend.id).bonus_credits == BONUS


def test_code_matching_ignores_case_and_spaces(users):
    referrer = _register(users, "a@example.com")

    _register(users, "b@example.com", f"  {referrer.referral_code.lower()} ")

    assert users.get_by_id(referrer.id).referral_rewards == 1


def test_blank_code_means_no_referral(users):
    friend = _register(users, "b@example.com", "   ")

    assert friend.bonus_credits == 0


def test_unknown_code_writes_nothing(users):
    with pytest.raises(InvalidReferralCode):
        _register(users, "b@example.com", "NOSUCH22")

    assert users.get_by_email("b@example.com") is None


def test_duplicate_email_rolls_back_the_referrers_reward(users):
    referrer = _register(users, "a@example.com")
    _register(users, "taken@example.com")

    with pytest.raises(EmailTakenError):
        _register(users, "taken@example.com", referrer.referral_code)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (0, 0)


def test_cap_rewards_only_the_friend(users):
    referrer = _register(users, "a@example.com")
    for i in range(2):
        _register(users, f"f{i}@example.com", referrer.referral_code, max_rewards=2)

    friend = _register(users, "late@example.com", referrer.referral_code, max_rewards=2)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (2 * BONUS, 2)
    assert friend.bonus_credits == BONUS


def test_deleting_a_friend_does_not_reopen_the_cap(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code, max_rewards=1)

    users.delete_user(friend.id)
    _register(users, "g@example.com", referrer.referral_code, max_rewards=1)

    after = users.get_by_id(referrer.id)
    assert (after.bonus_credits, after.referral_rewards) == (BONUS, 1)


def test_deleting_the_referrer_clears_referred_by(users):
    referrer = _register(users, "a@example.com")
    friend = _register(users, "f@example.com", referrer.referral_code)

    users.delete_user(referrer.id)

    row = users._conn.execute(
        "SELECT referred_by FROM users WHERE id = ?", (friend.id,)
    ).fetchone()
    assert row[0] is None


def test_every_account_gets_a_distinct_code(users):
    codes = {_register(users, f"u{i}@example.com").referral_code for i in range(25)}

    assert len(codes) == 25
