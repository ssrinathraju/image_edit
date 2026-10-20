from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Response, status

from image_edit_server.api.deps import (
    AuthDep,
    AuthServiceDep,
    QuotaDep,
    ReferralDep,
    SettingsDep,
    TokenDep,
    UserStoreDep,
)
from image_edit_server.core.plans import effective_plan
from image_edit_server.schemas.user import (
    AgeConfirmRequest,
    AppleSignInRequest,
    AuthResponse,
    ConsentRequest,
    ConsentState,
    Credentials,
    DeleteAccountRequest,
    GoogleSignInRequest,
    MeResponse,
    ReferralRedeemRequest,
    RegisterRequest,
    RegistrationConfirm,
    ResetConfirm,
    ResetRequest,
    SocialAuthResponse,
    User,
)

router = APIRouter(tags=["auth"])

def _auth_response(token: str, user: User) -> AuthResponse:
    return AuthResponse(token=token, id=user.id, email=user.email)


def _social_response(token: str, user: User, created: bool) -> SocialAuthResponse:
    return SocialAuthResponse(
        token=token,
        id=user.id,
        email=user.email,
        created=created,
    )


# Hashing is CPU-bound, so these are plain `def` handlers that run in the thread pool.


@router.post("/auth/register", status_code=status.HTTP_202_ACCEPTED)
def register(
    body: RegisterRequest, auth: AuthServiceDep, background: BackgroundTasks
) -> dict:
    auth.register(
        body.email, body.password, body.date_of_birth, body.referral_code, background
    )
    return {}


@router.post(
    "/auth/register/confirm",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthResponse,
)
def confirm_registration(body: RegistrationConfirm, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.confirm_registration(body.email, body.code, body.password)
    return _auth_response(token, user)


@router.post("/auth/login", response_model=AuthResponse)
def login(body: Credentials, auth: AuthServiceDep) -> AuthResponse:
    token, user = auth.login(body.email, body.password)
    return _auth_response(token, user)


@router.post("/auth/oauth/google", response_model=SocialAuthResponse)
def sign_in_with_google(body: GoogleSignInRequest, auth: AuthServiceDep) -> SocialAuthResponse:
    token, user, created = auth.sign_in_with_provider(
        "google", body.id_token, date_of_birth=body.date_of_birth
    )
    return _social_response(token, user, created)


@router.post("/auth/oauth/apple", response_model=SocialAuthResponse)
def sign_in_with_apple(body: AppleSignInRequest, auth: AuthServiceDep) -> SocialAuthResponse:
    token, user, created = auth.sign_in_with_provider(
        "apple",
        body.identity_token,
        nonce=body.nonce,
        authorization_code=body.authorization_code,
        date_of_birth=body.date_of_birth,
    )
    return _social_response(token, user, created)


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
def get_me(
    user: AuthDep,
    quota: QuotaDep,
    referrals: ReferralDep,
    users: UserStoreDep,
    settings: SettingsDep,
) -> MeResponse:
    return MeResponse(
        id=user.id,
        email=user.email,
        created_at=user.created_at,
        plan=effective_plan(user.plan),
        usage=quota.summary(user),
        referral=referrals.summary(user),
        providers=users.list_providers(user.id),
        has_password=user.has_password,
        age_confirmed=user.age_confirmed,
        consent=ConsentState(
            accepted_version=user.consent_version,
            accepted_at=user.consent_at,
            current_version=settings.CONSENT_VERSION,
        ),
    )


@router.post("/me/age")
def confirm_age(body: AgeConfirmRequest, user: AuthDep, auth: AuthServiceDep) -> dict:
    auth.confirm_age(user, body.date_of_birth)
    return {}


@router.post("/me/consent")
def accept_consent(body: ConsentRequest, user: AuthDep, auth: AuthServiceDep) -> dict:
    auth.accept_consent(user, body.version)
    return {}


@router.delete("/me/consent", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_consent(user: AuthDep, auth: AuthServiceDep) -> Response:
    auth.withdraw_consent(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/referral")
def redeem_referral(
    body: ReferralRedeemRequest, user: AuthDep, referrals: ReferralDep
) -> dict:
    referrals.redeem(user, body.code)
    return {}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: DeleteAccountRequest,
    user: AuthDep,
    auth: AuthServiceDep,
    background: BackgroundTasks,
) -> Response:
    auth.delete_account(
        user,
        body.password,
        provider=body.provider,
        token=body.token,
        nonce=body.nonce,
        background=background,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
