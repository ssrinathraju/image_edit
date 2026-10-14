from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

MAX_EMAIL_CHARS = 254
MAX_PASSWORD_CHARS = 128


@dataclass(frozen=True)
class User:
    id: str
    email: str
    created_at: str


class Credentials(BaseModel):
    email: str = Field(max_length=MAX_EMAIL_CHARS)
    password: str = Field(max_length=MAX_PASSWORD_CHARS)


class AuthResponse(BaseModel):
    token: str
    id: str
    email: str


class MeResponse(BaseModel):
    id: str
    email: str
    created_at: str


class DeleteAccountRequest(BaseModel):
    password: str = Field(max_length=MAX_PASSWORD_CHARS)
