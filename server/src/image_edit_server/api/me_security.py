from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Response, status

from image_edit_server.api.deps import AccountSecurityDep, AuthDep, TokenDep
from image_edit_server.schemas.user import (
    EmailChangeConfirm,
    EmailChangedResponse,
    EmailChangeRequest,
    LinkAppleRequest,
    LinkGoogleRequest,
    PasswordChangeRequest,
    UnlinkRequest,
)

router = APIRouter(tags=["account-security"])

# Hashing is CPU-bound, so these are plain `def` handlers that run in the thread pool.


@router.post("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    body: PasswordChangeRequest,
    user: AuthDep,
    token: TokenDep,
    security: AccountSecurityDep,
    background: BackgroundTasks,
) -> Response:
    security.change_password(user, token, body.new_password, body.reauth, background)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/email", status_code=status.HTTP_202_ACCEPTED)
def request_email_change(
    body: EmailChangeRequest,
    user: AuthDep,
    security: AccountSecurityDep,
    background: BackgroundTasks,
) -> dict:
    security.request_email_change(user, body.new_email, body.reauth, background)
    return {}


@router.post("/me/email/confirm", response_model=EmailChangedResponse)
def confirm_email_change(
    body: EmailChangeConfirm,
    user: AuthDep,
    token: TokenDep,
    security: AccountSecurityDep,
    background: BackgroundTasks,
) -> EmailChangedResponse:
    email = security.confirm_email_change(user, token, body.code, background)
    return EmailChangedResponse(email=email)


@router.post("/me/providers/google")
def link_google(body: LinkGoogleRequest, user: AuthDep, security: AccountSecurityDep) -> dict:
    security.link_provider(user, "google", body.id_token)
    return {}


@router.post("/me/providers/apple")
def link_apple(body: LinkAppleRequest, user: AuthDep, security: AccountSecurityDep) -> dict:
    security.link_provider(
        user,
        "apple",
        body.identity_token,
        nonce=body.nonce,
        authorization_code=body.authorization_code,
    )
    return {}


@router.delete("/me/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_provider(
    provider: Literal["google", "apple"],
    body: UnlinkRequest,
    user: AuthDep,
    security: AccountSecurityDep,
    background: BackgroundTasks,
) -> Response:
    security.unlink_provider(user, provider, body.reauth, background)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
