from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class User:
    id: str
    email: str
    created_at: str


class Credentials(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    id: str
    email: str


class MeResponse(BaseModel):
    id: str
    email: str
    created_at: str


class DeleteAccountRequest(BaseModel):
    password: str
