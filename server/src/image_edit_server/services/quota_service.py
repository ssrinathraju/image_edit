from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from image_edit_server.configs.settings import Settings
from image_edit_server.core.plans import ALL_PLANS, daily_limit, plan_limits
from image_edit_server.core.user_store import UserStore
from image_edit_server.schemas.user import UsageResponse, User

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class QuotaService:
    def __init__(
        self,
        users: UserStore,
        settings: Settings,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._users = users
        self._settings = settings
        self._clock = clock

    def _limit_for(self, user: User) -> int:
        if user.plan not in ALL_PLANS:
            logger.warning("unknown_plan user=%s; treating it as free", user.id)
        return daily_limit(user.plan, self._settings)

    def reserve(self, user: User) -> str:
        """Spend one generation; raises QuotaExceeded when none is left."""
        limit = self._limit_for(user)
        return self._users.reserve_generation(user.id, limit, self._clock())

    def has_remaining(self, user: User) -> bool:
        """Read-only look: is any generation left? Reserving is still the atomic step."""
        limit = self._limit_for(user)
        return self._users.usage_snapshot(user.id, limit, self._clock()).remaining > 0

    def release(self, reservation_id: str) -> None:
        self._users.refund_generation(reservation_id)

    def settle(self, reservation_id: str) -> None:
        self._users.settle_generation(reservation_id)

    def refund_interrupted(self) -> int:
        """Return generations whose jobs died with the previous server process."""
        return self._users.refund_unsettled_generations()

    def summary(self, user: User) -> UsageResponse:
        limit = self._limit_for(user)
        snapshot = self._users.usage_snapshot(user.id, limit, self._clock())
        return UsageResponse(
            daily_limit=snapshot.daily_limit,
            used_today=snapshot.used_today,
            bonus_credits=snapshot.bonus_credits,
            remaining=snapshot.remaining,
            resets_at=snapshot.resets_at.isoformat(),
            plan_limits=plan_limits(self._settings),
        )
