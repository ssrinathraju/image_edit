import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Optional

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from PIL import Image

TEST_TEMPLATES = [
    {"id": "sunset-beach", "title": "Sunset Beach", "tags": ["beach", "summer"],
     "popularity": 90, "prompt": "TEMPLATE PROMPT sunset beach"},
    {"id": "mountain-peak", "title": "Mountain Peak", "tags": ["snow"],
     "popularity": 50, "prompt": "TEMPLATE PROMPT mountain"},
    {"id": "city-night", "title": "City Night", "tags": ["neon"],
     "popularity": 70, "prompt": "TEMPLATE PROMPT city"},
]


def build_templates_dir(root: Path, entries: list[dict] = TEST_TEMPLATES) -> Path:
    (root / "previews").mkdir(parents=True, exist_ok=True)
    catalog = [{**e, "preview": f"{e['id']}.webp"} for e in entries]
    (root / "catalog.json").write_text(json.dumps(catalog))
    for entry in catalog:
        Image.new("RGB", (8, 8), (10, 20, 30)).save(
            root / "previews" / entry["preview"], format="WEBP"
        )
    return root


DEFAULT_PASSWORD = "correct horse battery"


def register_headers(client, email: str, password: str = DEFAULT_PASSWORD) -> dict:
    """Register an account and return headers carrying its bearer token."""
    resp = client.post("/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


class RecordingSender:
    """An EmailSender that keeps what it was asked to send."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))

    def last_code(self, to: str) -> str:
        bodies = [body for recipient, _, body in self.sent if recipient == to]
        return re.search(r"\b(\d{6})\b", bodies[-1]).group(1)

    def count_for(self, to: str) -> int:
        return sum(1 for recipient, _, _ in self.sent if recipient == to)


class FakeClock:
    """A settable clock for the code limits."""

    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def register_and_verify_through_api(
    client, sender: RecordingSender, email: str, password: str = DEFAULT_PASSWORD
) -> dict:
    """Register, then submit the emailed code, as a real client would."""
    headers = register_headers(client, email, password)
    resp = client.post(
        "/auth/verify-email", json={"code": sender.last_code(email)}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return headers


def forget_recent_sends(client) -> None:
    """Stand in for a minute passing on a real-clock app, so the next code email is not limited."""
    from image_edit_server.api.deps import get_user_store

    users = client.app.dependency_overrides[get_user_store]()
    users._conn.execute("DELETE FROM email_sends")
    users._conn.commit()


def verify_account(user_store, email: str) -> None:
    """Mark an account's email verified directly in the store."""
    user = user_store.get_by_email(email)
    user_store.mark_email_verified(user.id, 0, 0)


def register_verified_headers(
    client, user_store, email: str, password: str = DEFAULT_PASSWORD
) -> dict:
    """Register an account, verify it through the store, and return its bearer headers."""
    headers = register_headers(client, email, password)
    verify_account(user_store, email)
    return headers


def grant_bonus(user_store, user_id: str, credits: int) -> None:
    """Give an account bonus credits directly, as referral rewards would."""
    user_store._conn.execute(
        "UPDATE users SET bonus_credits = ? WHERE id = ?", (credits, user_id)
    )
    user_store._conn.commit()


GOOGLE_AUDIENCE = "google-web.apps.example"
APPLE_BUNDLE = "com.example.imageedit"
TEST_KID = "test-key-1"


def make_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwksClient:
    """Stands in for PyJWKClient: serves local public keys by kid, or fails like a dead endpoint."""

    def __init__(self, keys: dict, unreachable: bool = False) -> None:
        self._keys = keys
        self.unreachable = unreachable

    def get_signing_key_from_jwt(self, token: str):
        if self.unreachable:
            raise jwt.PyJWKClientConnectionError("fetch failed")
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self._keys:
            raise jwt.PyJWKClientError("Unable to find a signing key that matches")
        return SimpleNamespace(key=self._keys[kid].public_key())


def _base_claims(issuer: str, audience: str, subject: str, email: Optional[str]) -> dict:
    now = int(time.time())
    claims = {"iss": issuer, "aud": audience, "sub": subject, "iat": now, "exp": now + 600}
    if email is not None:
        claims["email"] = email
    return claims


def sign_token(key, claims: dict, kid: str = TEST_KID, algorithm: str = "RS256") -> str:
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})


def google_claims(
    subject: str = "g-1",
    email: Optional[str] = "ana@example.com",
    email_verified: bool = True,
    **overrides,
) -> dict:
    claims = _base_claims("https://accounts.google.com", GOOGLE_AUDIENCE, subject, email)
    claims["email_verified"] = email_verified
    claims.update(overrides)
    return claims


def apple_claims(
    subject: str = "a-1",
    email: Optional[str] = "ana@example.com",
    raw_nonce: Optional[str] = "raw-nonce",
    **overrides,
) -> dict:
    import hashlib

    claims = _base_claims("https://appleid.apple.com", APPLE_BUNDLE, subject, email)
    claims["email_verified"] = "true"
    if raw_nonce is not None:
        claims["nonce"] = hashlib.sha256(raw_nonce.encode()).hexdigest()
    claims.update(overrides)
    return claims
