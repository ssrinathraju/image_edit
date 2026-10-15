from __future__ import annotations

from fastapi import APIRouter, Response, status

from image_edit_server.api.deps import (
    AuthDep,
    AuthServiceDep,
    QuotaDep,
    ReferralDep,
    TokenDep,
)
from image_edit_server.schemas.user import (
    AuthResponse,
    Credentials,
    DeleteAccountRequest,
    MeResponse,
)

router = APIRouter(tags=["auth"])

# Hashing is CPU-bound, so these are plain `def` handlers that run in the thread pool.


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(body: Credentials, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.register(body.email, body.password, body.referral_code)
    return AuthResponse(token=token, id=user.id, email=user.email)


@router.post("/auth/login", response_model=AuthResponse)
def login(body: Credentials, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.login(body.email, body.password)
    return AuthResponse(token=token, id=user.id, email=user.email)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: TokenDep, _user: AuthDep, auth: AuthServiceDep) -> Response:
    auth.logout(token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def get_me(user: AuthDep, quota: QuotaDep, referrals: ReferralDep) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        plan=user.plan,
        usage=quota.summary(user),
        referral=referrals.summary(user),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: DeleteAccountRequest, user: AuthDep, auth: AuthServiceDep) -> Response:
    auth.delete_account(user, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
