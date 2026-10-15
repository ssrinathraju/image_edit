from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException

from image_edit_server.core.user_store import UserStore
from image_edit_server.schemas.api import ErrorBody
from image_edit_server.schemas.user import User
from image_edit_server.services.auth_service import AuthService

BEARER_PREFIX = "bearer "


def get_user_store() -> UserStore:
    raise RuntimeError("user store is not configured; override get_user_store")


def get_auth_service() -> AuthService:
    raise RuntimeError("auth service is not configured; override get_auth_service")


def _unauthorized() -> HTTPException:
    return HTTPException(
        401,
        ErrorBody(error="unauthorized", detail="a valid session is required").model_dump(),
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_bearer_token(authorization: Annotated[Optional[str], Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith(BEARER_PREFIX):
        raise _unauthorized()
    token = authorization[len(BEARER_PREFIX):].strip()
    if not token:
        raise _unauthorized()
    return token


TokenDep = Annotated[str, Depends(get_bearer_token)]
UserStoreDep = Annotated[UserStore, Depends(get_user_store)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(token: TokenDep, users: UserStoreDep) -> User:
    user = users.get_user_by_session(token)
    if user is None:
        raise _unauthorized()
    return user


AuthDep = Annotated[User, Depends(get_current_user)]
