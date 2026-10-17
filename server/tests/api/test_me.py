from datetime import datetime, timezone

from tests.helpers import grant_bonus


def test_fresh_account_reports_plan_usage_and_a_referral_code(client):
    body = client.get("/me").json()

    assert body["plan"] == "free"
    assert body["usage"]["daily_limit"] == 3
    assert body["usage"]["used_today"] == 0
    assert body["usage"]["remaining"] == 3
    assert body["usage"]["plan_limits"] == {"free": 3, "premium": 30}
    assert body["usage"]["resets_at"].endswith("T00:00:00+00:00")
    assert len(body["referral"]["code"]) == 8
    assert body["referral"] == {
        "code": body["referral"]["code"],
        "rewards": 0,
        "max_rewards": 10,
        "bonus_per_referral": 5,
    }


def test_used_two_with_five_credits_has_six_remaining(client, user_store, user_id):
    now = datetime.now(timezone.utc)
    for _ in range(2):
        user_store.reserve_generation(user_id, 3, now)
    grant_bonus(user_store, user_id, 5)

    usage = client.get("/me").json()["usage"]

    assert (usage["daily_limit"], usage["used_today"], usage["bonus_credits"]) == (3, 2, 5)
    assert usage["remaining"] == 6


def test_premium_plan_is_reported_after_the_operator_change(client, user_store):
    user_store.set_plan("ana@example.com", "premium")

    body = client.get("/me").json()

    assert body["plan"] == "premium"
    assert body["usage"]["daily_limit"] == 30


def test_no_password_material_is_returned(client):
    text = client.get("/me").text.lower()

    assert "password" not in text
    assert "hash" not in text


def test_a_client_cannot_choose_its_plan(anon_client, user_store):
    resp = anon_client.post(
        "/auth/register",
        json={"email": "eve@example.com", "password": "correct horse battery", "plan": "premium"},
    )
    headers = {"Authorization": f"Bearer {resp.json()['token']}"}

    anon_client.post(
        "/generations", data={"prompt": "x", "plan": "premium"}, headers=headers
    )

    assert anon_client.get("/me", headers=headers).json()["plan"] == "free"


def test_me_reports_unverified_then_verified(unverified_client, user_store):
    assert unverified_client.get("/me").json()["email_verified"] is False

    user_store.mark_email_verified(unverified_client.get("/me").json()["id"], 0, 0)

    assert unverified_client.get("/me").json()["email_verified"] is True


def test_me_never_contains_a_code(unverified_client, sender):
    code = sender.last_code("una@example.com")

    assert code not in unverified_client.get("/me").text
