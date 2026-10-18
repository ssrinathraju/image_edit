from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

MAX_REFERRAL_CODE_CHARS = 32

MAX_EMAIL_CHARS = 254
MAX_PASSWORD_CHARS = 128
# Looser transport cap so the service answers 400 invalid_credentials_format for a too-long new password.
MAX_NEW_PASSWORD_TRANSPORT_CHARS = 1024
MAX_CODE_CHARS = 16
MAX_PROVIDER_TOKEN_CHARS = 8192
MAX_NONCE_CHARS = 256


@dataclass(frozen=True)
class User:
    id: str
    email: str
    created_at: str
    plan: str = "free"
    bonus_credits: int = 0
    referral_code: str = ""
    referral_rewards: int = 0
    has_password: bool = True


@dataclass(frozen=True)
class UsageSnapshot:
    """Raw usage figures for one account at one moment."""

    daily_limit: int
    used_today: int
    bonus_credits: int
    remaining: int
    resets_at: datetime


class Credentials(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_CHARS)
    password: str = Field(max_length=MAX_PASSWORD_CHARS)
    referral_code: Optional[str] = Field(default=None, max_length=MAX_REFERRAL_CODE_CHARS)


class AuthResponse(BaseModel):
    token: str
    id: str
    email: str


class SocialAuthResponse(AuthResponse):
    created: bool


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(max_length=MAX_PROVIDER_TOKEN_CHARS)


class AppleSignInRequest(BaseModel):
    identity_token: str = Field(max_length=MAX_PROVIDER_TOKEN_CHARS)
    nonce: str = Field(max_length=MAX_NONCE_CHARS)
    authorization_code: str = Field(max_length=MAX_PROVIDER_TOKEN_CHARS)


class ReferralRedeemRequest(BaseModel):
    code: str = Field(max_length=MAX_REFERRAL_CODE_CHARS)


class RegistrationConfirm(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_CHARS)
    code: str = Field(max_length=MAX_CODE_CHARS)


class ResetRequest(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_CHARS)


class ResetConfirm(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_CHARS)
    code: str = Field(max_length=MAX_CODE_CHARS)
    new_password: str = Field(max_length=MAX_NEW_PASSWORD_TRANSPORT_CHARS)


class UsageResponse(BaseModel):
    daily_limit: int
    used_today: int
    bonus_credits: int
    remaining: int
    resets_at: str
    plan_limits: dict[str, int]


class ReferralResponse(BaseModel):
    code: str
    rewards: int
    max_rewards: int
    bonus_per_referral: int


class MeResponse(BaseModel):
    id: str
    email: str
    created_at: str
    plan: str
    usage: UsageResponse
    referral: ReferralResponse
    providers: list[str]
    has_password: bool


class DeleteAccountRequest(BaseModel):
    """Confirms deletion with either the password or a fresh provider sign-in token."""

    password: Optional[str] = Field(default=None, max_length=MAX_PASSWORD_CHARS)
    provider: Optional[Literal["google", "apple"]] = None
    token: Optional[str] = Field(default=None, max_length=MAX_PROVIDER_TOKEN_CHARS)
    nonce: Optional[str] = Field(default=None, max_length=MAX_NONCE_CHARS)

    @model_validator(mode="after")
    def _require_exactly_one_form(self) -> "DeleteAccountRequest":
        provider_form = self.provider is not None or self.token is not None
        if self.password is not None and provider_form:
            raise ValueError("send either password or provider with token, not both")
        if self.password is None and not (self.provider and self.token):
            raise ValueError("send either password, or provider together with token")
        return self
