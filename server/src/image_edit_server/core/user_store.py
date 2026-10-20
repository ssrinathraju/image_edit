from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Protocol

from image_edit_server.core.email_codes import (
    CodeLimits,
    CodePurpose,
    ConsumeResult,
    IssueResult,
)
from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.schemas.report import Report
from image_edit_server.schemas.user import UsageSnapshot, User


class EmailTakenError(Exception):
    """Raised when creating a user whose email already has an account."""


class RegistrationChanged(Exception):
    """Raised when the pending registration no longer matches what the caller checked."""


@dataclass(frozen=True)
class PendingRegistration:
    """The pending row as read when its code was accepted."""

    password_hash: str
    created_at: str


class QuotaExceeded(Exception):
    """Raised when an account has no daily allowance or bonus credits left."""


class TooManyReports(Exception):
    """Raised when an account has reached its daily report limit."""


class InvalidReferralCode(Exception):
    """Raised when a referral code matches no account."""


class UserNotFound(Exception):
    """Raised when an operation targets an account that no longer exists."""


class ProviderEmailMissing(Exception):
    """Raised when an unlinked provider identity arrives without an email."""


class ProviderEmailUnverified(Exception):
    """Raised when the provider does not vouch for the email of an unlinked identity."""


class ProviderAlreadyLinked(Exception):
    """Raised when linking would give an account a second identity of one provider."""


class ReferralNotAllowed(Exception):
    """Raised when an account may not redeem a referral code (late, repeated or password-made)."""


class AgeRequired(Exception):
    """Raised when a provider sign-in would create an account but sent no date of birth."""


class UnderAgeSignUp(Exception):
    """Raised when a provider sign-in would create an account for someone under 18."""


class UserStore(Protocol):
    def create_user(self, email: str, password_hash: str) -> User:
        """Create a bare verified user (no referral); raises EmailTakenError on a duplicate."""
        ...

    def start_registration(
        self,
        email: str,
        password_hash: str,
        referral_code: Optional[str],
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        """Hold a registration as pending and store its code, unless a sending limit applies.

        Raises EmailTakenError or InvalidReferralCode; nothing is written then. When
        a limit applies the earlier pending registration and code are kept.
        """
        ...

    def check_registration_code(
        self, email: str, code: str, now: datetime, max_attempts: int
    ) -> tuple[ConsumeResult, Optional[PendingRegistration]]:
        """Check the registration code without using it up.

        Returns (ok, pending) or (wrong | expired, None). A correct code with no
        pending row counts as expired, unless an account has the email: then
        EmailTakenError is raised.
        """
        ...

    def complete_registration(
        self,
        email: str,
        checked: PendingRegistration,
        password_matches: bool,
        now: datetime,
        bonus: int,
        max_rewards: int,
    ) -> User:
        """Create the verified account if the pending row is still `checked` and the password matched.

        Raises RegistrationChanged, after discarding the pending row and its code, on a
        mismatch or a changed row. Raises EmailTakenError, after discarding the pending
        row, when an account has the email.
        """
        ...

    def prune_email_rows(self, now: datetime) -> None:
        """Delete expired codes, send rows past the send window and stale pending registrations."""
        ...

    def issue_code(
        self,
        email: str,
        purpose: CodePurpose,
        code_hash: str,
        now: datetime,
        limits: CodeLimits,
    ) -> IssueResult:
        """Store a new code in place of any earlier one, unless a sending limit applies."""
        ...

    def consume_code(
        self,
        email: str,
        purpose: CodePurpose,
        code: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        """Check a code; a wrong one counts an attempt, a correct one is used up."""
        ...

    def reset_password(
        self,
        email: str,
        code: str,
        new_hash: str,
        now: datetime,
        max_attempts: int,
    ) -> ConsumeResult:
        """Consume a reset code and, on ok, change the password and drop every
        session of the account, all in one transaction."""
        ...

    def reserve_generation(self, user_id: str, daily_limit: int, now: datetime) -> str:
        """Spend one generation (daily first, then bonus); returns a reservation id.

        Raises QuotaExceeded when nothing is left and UserNotFound for a gone user.
        """
        ...

    def refund_generation(self, reservation_id: str) -> None:
        """Return a reserved generation to the source it came from; idempotent."""
        ...

    def settle_generation(self, reservation_id: str) -> None:
        """Mark a reservation as finished so a restart will not refund it."""
        ...

    def refund_unsettled_generations(self) -> int:
        """Refund every reservation that is neither settled nor refunded.

        Only valid at startup, when no job can still be in flight. Returns the
        number of reservations refunded.
        """
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

    def sign_in_with_identity(
        self,
        identity: ProviderIdentity,
        now: datetime,
        adult_confirmed: Optional[bool] = None,
    ) -> tuple[User, bool]:
        """Find the linked account, link by email, or create one; returns (user, created).

        `adult_confirmed` matters only when an account would be created: None raises
        AgeRequired, False raises UnderAgeSignUp, True creates it with its age confirmed.
        Creating an account discards any pending registration for its email. Raises
        ProviderEmailMissing, ProviderEmailUnverified, ProviderAlreadyLinked,
        AgeRequired or UnderAgeSignUp before writing anything.
        """
        ...

    def confirm_age(self, user_id: str, now: datetime) -> None:
        """Record that the account's age was confirmed at `now`."""
        ...

    def set_consent(self, user_id: str, version: str, now: datetime) -> None:
        """Record that the account accepted consent `version` at `now`."""
        ...

    def clear_consent(self, user_id: str) -> None:
        """Remove the account's recorded consent; a no-op when there is none."""
        ...

    def has_identity(self, user_id: str, provider: str, subject: str) -> bool: ...

    def list_providers(self, user_id: str) -> list[str]:
        """The provider names linked to the account, sorted."""
        ...

    def set_apple_refresh_token(self, user_id: str, token: str) -> None: ...

    def get_apple_refresh_token(self, user_id: str) -> Optional[str]: ...

    def redeem_referral(
        self,
        user_id: str,
        code: str,
        now: datetime,
        window: timedelta,
        bonus: int,
        max_rewards: int,
    ) -> None:
        """Link a provider-made account to a referrer and pay both at once.

        Raises ReferralNotAllowed, InvalidReferralCode or UserNotFound; nothing is
        written then.
        """
        ...

    def record_strike(self, user_id: str, now: datetime, window: timedelta) -> None:
        """Record a blocked result and prune strikes older than the window; raises UserNotFound."""
        ...

    def suspended_until(
        self, user_id: str, now: datetime, window: timedelta, threshold: int
    ) -> Optional[datetime]:
        """The time the pause ends (window after the threshold-th most recent strike), or None."""
        ...

    def add_report(
        self,
        report_id: str,
        reporter_id: str,
        job_id: str,
        category: str,
        note: str,
        image_source: str,
        image_name: Optional[str],
        now: datetime,
        daily_limit: int,
    ) -> None:
        """Insert a report; raises TooManyReports at the daily cap and UserNotFound for a deleted reporter."""
        ...

    def get_report(self, report_id: str) -> Optional[Report]: ...

    def list_open_reports(self) -> list[Report]:
        """Unresolved reports, newest first."""
        ...

    def resolve_report(self, report_id: str, outcome: str, now: datetime) -> bool:
        """Mark an open report resolved; False when it is unknown or already resolved."""
        ...

    def expired_reports(self, now: datetime, max_age: timedelta) -> list[Report]: ...

    def delete_report(self, report_id: str) -> None: ...

    def report_image_names(self, reporter_id: Optional[str] = None) -> list[str]:
        """Report image file names, for one reporter or for every report."""
        ...
