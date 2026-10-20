from image_edit_server.configs.settings import Settings
from image_edit_server.core.plans import ALL_PLANS, FREE, PREMIUM, daily_limit, effective_plan, plan_limits


def test_limits_per_plan():
    settings = Settings()

    assert daily_limit(FREE, settings) == 3
    assert daily_limit(PREMIUM, settings) == 30
    assert plan_limits(settings) == {"free": 3, "premium": 30}
    assert ALL_PLANS == (FREE, PREMIUM)


def test_limits_follow_settings():
    settings = Settings(FREE_DAILY_LIMIT=1, PREMIUM_DAILY_LIMIT=2)

    assert plan_limits(settings) == {"free": 1, "premium": 2}


def test_unknown_plan_counts_as_free_and_never_raises():
    settings = Settings()

    assert effective_plan("gold") == FREE
    assert effective_plan(PREMIUM) == PREMIUM
    assert daily_limit("gold", settings) == daily_limit(FREE, settings) == 3
