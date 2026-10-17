from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

MAX_REFERRAL_CODE_CHARS = 32

MAX_EMAIL_CHARS = 254
MAX_PASSWORD_CHARS = 128


@dataclass(frozen=True)
class User:
    id: str
    email: str
    created_at: str
    plan: str = "free"
    bonus_credits: int = 0
    referral_code: str = ""
    referral_rewards: int = 0
    email_verified: bool = False


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


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD_CHARS)
