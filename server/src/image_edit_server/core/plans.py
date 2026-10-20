from __future__ import annotations

from image_edit_server.configs.settings import Settings

FREE = "free"
PREMIUM = "premium"
ALL_PLANS = (FREE, PREMIUM)


def effective_plan(plan: str) -> str:
    """Return the plan itself when it is known, otherwise free."""
    return plan if plan in ALL_PLANS else FREE


def daily_limit(plan: str, settings: Settings) -> int:
    """Return the daily generation allowance of a plan; an unknown plan counts as free."""
    return plan_limits(settings)[effective_plan(plan)]


def plan_limits(settings: Settings) -> dict[str, int]:
    return {FREE: settings.FREE_DAILY_LIMIT, PREMIUM: settings.PREMIUM_DAILY_LIMIT}
