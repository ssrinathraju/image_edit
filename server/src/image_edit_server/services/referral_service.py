from __future__ import annotations

from image_edit_server.configs.settings import Settings
from image_edit_server.schemas.user import ReferralResponse, User


class ReferralService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def summary(self, user: User) -> ReferralResponse:
        return ReferralResponse(
            code=user.referral_code,
            rewards=user.referral_rewards,
            max_rewards=self._settings.REFERRAL_MAX_REWARDS,
            bonus_per_referral=self._settings.REFERRAL_BONUS,
        )
