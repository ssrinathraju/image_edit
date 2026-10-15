from __future__ import annotations

from image_edit_server.configs.settings import Settings

FREE = "free"
PREMIUM = "premium"
ALL_PLANS = (FREE, PREMIUM)


def daily_limit(plan: str, settings: Settings) -> int:
    """Return the daily generation allowance of a plan; unknown plans raise."""
    limits = plan_limits(settings)
    if plan not in limits:
        raise ValueError(f"unknown plan {plan!r}; expected one of {list(ALL_PLANS)}")
    return limits[plan]


def plan_limits(settings: Settings) -> dict[str, int]:
    return {FREE: settings.FREE_DAILY_LIMIT, PREMIUM: settings.PREMIUM_DAILY_LIMIT}
