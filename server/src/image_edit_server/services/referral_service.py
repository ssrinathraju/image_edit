from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from fastapi import HTTPException

from image_edit_server.configs.settings import Settings
from image_edit_server.core.referral_codes import REDEEM_WINDOW
from image_edit_server.core.user_store import (
    InvalidReferralCode,
    ReferralNotAllowed,
    UserStore,
)
from image_edit_server.schemas.api import ErrorBody
from image_edit_server.schemas.user import ReferralResponse, User


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReferralService:
    def __init__(
        self,
        settings: Settings,
        users: UserStore,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._settings = settings
        self._users = users
        self._clock = clock

    def summary(self, user: User) -> ReferralResponse:
        return ReferralResponse(
            code=user.referral_code,
            rewards=user.referral_rewards,
            max_rewards=self._settings.REFERRAL_MAX_REWARDS,
            bonus_per_referral=self._settings.REFERRAL_BONUS,
        )

    def redeem(self, user: User, code: str) -> None:
        """Pay both accounts for a code entered after a provider sign-up."""
        try:
            self._users.redeem_referral(
                user.id,
                code,
                self._clock(),
                REDEEM_WINDOW,
                self._settings.REFERRAL_BONUS,
                self._settings.REFERRAL_MAX_REWARDS,
            )
        except ReferralNotAllowed:
            raise _error(
                409,
                "referral_not_allowed",
                "only an account created through Google or Apple in the last 24 hours,"
                " without a referral yet, can redeem a code",
            )
        except InvalidReferralCode:
            raise _error(400, "invalid_referral_code", "this referral code was not recognised")


def _error(status: int, code: str, detail: str) -> HTTPException:
    return HTTPException(status, ErrorBody(error=code, detail=detail).model_dump())
