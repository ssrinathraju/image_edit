import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.plans import ALL_PLANS, FREE, PREMIUM, daily_limit, plan_limits


def test_limits_per_plan():
    settings = Settings()

    assert daily_limit(FREE, settings) == 3
    assert daily_limit(PREMIUM, settings) == 30
    assert plan_limits(settings) == {"free": 3, "premium": 30}
    assert ALL_PLANS == (FREE, PREMIUM)


def test_limits_follow_settings():
    settings = Settings(FREE_DAILY_LIMIT=1, PREMIUM_DAILY_LIMIT=2)

    assert plan_limits(settings) == {"free": 1, "premium": 2}


def test_unknown_plan_raises():
    with pytest.raises(ValueError, match="gold"):
        daily_limit("gold", Settings())
