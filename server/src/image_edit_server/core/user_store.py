from __future__ import annotations

from datetime import timedelta
from typing import Optional, Protocol

from image_edit_server.schemas.user import User


class EmailTakenError(Exception):
    """Raised when creating a user whose email already has an account."""


class UserStore(Protocol):
    def create_user(self, email: str, password_hash: str) -> User:
        """Create a user; raises EmailTakenError when the email exists."""
        ...

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
