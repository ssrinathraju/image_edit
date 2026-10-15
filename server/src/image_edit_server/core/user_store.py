from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Protocol

from image_edit_server.schemas.user import UsageSnapshot, User


class EmailTakenError(Exception):
    """Raised when creating a user whose email already has an account."""


class QuotaExceeded(Exception):
    """Raised when an account has no daily allowance or bonus credits left."""


class InvalidReferralCode(Exception):
    """Raised when registering with a referral code that matches no account."""


class UserNotFound(Exception):
    """Raised when an operation targets an account that no longer exists."""


class UserStore(Protocol):
    def create_user(self, email: str, password_hash: str) -> User:
        """Create a bare user (no referral); raises EmailTakenError on a duplicate."""
        ...

    def register_user(
        self,
        email: str,
        password_hash: str,
        referral_code: Optional[str],
        bonus: int,
        max_rewards: int,
    ) -> User:
        """Create a user and apply a referral reward in one transaction.

        Raises EmailTakenError or InvalidReferralCode; nothing is written then.
        """
        ...

    def reserve_generation(self, user_id: str, daily_limit: int, now: datetime) -> str:
        """Spend one generation (daily first, then bonus); returns a reservation id.

        Raises QuotaExceeded when nothing is left and UserNotFound for a gone user.
        """
        ...

    def refund_generation(self, reservation_id: str) -> None:
        """Return a reserved generation to the source it came from; idempotent."""
        ...

    def usage_snapshot(
        self, user_id: str, daily_limit: int, now: datetime
    ) -> UsageSnapshot: ...

    def get_by_email(self, email: str) -> Optional[User]: ...

    def get_by_id(self, user_id: str) -> Optional[User]: ...

    def get_password_hash(self, user_id: str) -> Optional[str]: ...

    def delete_user(self, user_id: str) -> None:
        """Delete the user and, by cascade, all of their sessions."""
        ...

    def create_session(self, user_id: str, ttl: timedelta) -> str:
        """Issue a session and return its token; only a hash of it is stored."""
        ...

    def get_user_by_session(self, token: str) -> Optional[User]:
        """Return the owner of a live session, or None if unknown or expired."""
        ...

    def delete_session(self, token: str) -> None: ...
