from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from image_edit_server.core.referral_codes import normalize_code
from image_edit_server.core.user_store import (
    InvalidReferralCode,
    ReferralNotAllowed,
    UserNotFound,
)

PASSWORD_ORIGIN = "password"


class ReferralsMixin:
    def _find_referrer(self, code: str) -> Optional[str]:
        if not code:
            return None
        row = self._conn.execute(
            "SELECT id FROM users WHERE referral_code = ?", (code,)
        ).fetchone()
        if row is None:
            raise InvalidReferralCode(code)
        return row[0]

    def _reward_referrer(self, referrer_id: str, bonus: int, max_rewards: int) -> None:
        self._conn.execute(
            "UPDATE users SET bonus_credits = bonus_credits + ?,"
            " referral_rewards = referral_rewards + 1"
            " WHERE id = ? AND referral_rewards < ?",
            (bonus, referrer_id, max_rewards),
        )

    def redeem_referral(
        self,
        user_id: str,
        code: str,
        now: datetime,
        window: timedelta,
        bonus: int,
        max_rewards: int,
    ) -> None:
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT created_via, created_at, referral_redeemed, referred_by,"
                " referral_code FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise UserNotFound(user_id)
            created_via, created_at, redeemed, referred_by, own_code = row
            allowed = (
                created_via != PASSWORD_ORIGIN
                and datetime.fromisoformat(created_at) > now - window
                and not redeemed
                and referred_by is None
            )
            if not allowed:
                raise ReferralNotAllowed(user_id)
            wanted = normalize_code(code)
            referrer = self._find_referrer(wanted)
            if referrer is None or wanted == own_code:
                raise InvalidReferralCode(wanted)
            self._conn.execute(
                "UPDATE users SET referred_by = ?, referral_redeemed = 1,"
                " bonus_credits = bonus_credits + ? WHERE id = ?",
                (referrer, bonus, user_id),
            )
            self._reward_referrer(referrer, bonus, max_rewards)
