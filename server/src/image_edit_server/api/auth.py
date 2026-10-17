from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response, status

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
    ResetConfirm,
    ResetRequest,
    User,
    VerifyEmailRequest,
    VerifyEmailResponse,
)

router = APIRouter(tags=["auth"])

def _auth_response(token: str, user: User) -> AuthResponse:
    return AuthResponse(
        token=token, id=user.id, email=user.email, email_verified=user.email_verified
    )


# Hashing is CPU-bound, so these are plain `def` handlers that run in the thread pool.


@router.post("/auth/register", status_code=status.HTTP_201_CREATED, response_model=AuthResponse)
def register(
    body: Credentials, auth: AuthServiceDep, background: BackgroundTasks
) -> AuthResponse:
    token, user = auth.register(body.email, body.password, body.referral_code, background)
    return _auth_response(token, user)


@router.post("/auth/login", response_model=AuthResponse)
def login(body: Credentials, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.login(body.email, body.password)
    return _auth_response(token, user)


@router.post("/auth/verify-email", response_model=VerifyEmailResponse)
def verify_email(
    body: VerifyEmailRequest, user: AuthDep, auth: AuthServiceDep
) -> VerifyEmailResponse:
    auth.verify_email(user, body.code)
    return VerifyEmailResponse(email_verified=True)


@router.post("/auth/verify-email/resend", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    user: AuthDep, auth: AuthServiceDep, background: BackgroundTasks
) -> dict:
    auth.resend_verification(user, background)
    return {}


@router.post("/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    body: ResetRequest, auth: AuthServiceDep, background: BackgroundTasks
) -> dict:
    auth.request_password_reset(body.email, background)
    return {}


@router.post("/auth/password-reset/confirm", response_model=AuthResponse)
def confirm_password_reset(body: ResetConfirm, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.confirm_password_reset(body.email, body.code, body.new_password)
    return _auth_response(token, user)


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
        email_verified=user.email_verified,
        plan=user.plan,
        usage=quota.summary(user),
        referral=referrals.summary(user),
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(body: DeleteAccountRequest, user: AuthDep, auth: AuthServiceDep) -> Response:
    auth.delete_account(user, body.password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
