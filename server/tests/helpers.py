import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from PIL import Image

from image_edit_server.core.identity_verifier import (
    InvalidProviderToken,
    ProviderIdentity,
)

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
ADULT_DOB = "1990-01-01"


def register_headers(
    client, email: str, password: str = DEFAULT_PASSWORD, consent: bool = False
) -> dict:
    """Register and confirm through the API with the emailed code; returns bearer headers."""
    from image_edit_server.api.deps import get_auth_service

    sender = client.app.dependency_overrides[get_auth_service]()._sender
    resp = client.post("/auth/register", json={"email": email, "password": password, "date_of_birth": ADULT_DOB},
    )
    assert resp.status_code == 202, resp.text
    resp = client.post(
        "/auth/register/confirm",
        json={"email": email, "code": sender.last_code(email), "password": password},
    )
    assert resp.status_code == 201, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['token']}"}
    if consent:
        grant_consent(client, headers)
    return headers


def grant_consent(client, headers=None, version: str = "1") -> None:
    """Accept face-photo consent through the API for the account behind `headers`."""
    resp = client.post("/me/consent", json={"version": version}, headers=headers)
    assert resp.status_code == 200, resp.text


def confirm_in_store(users, email, code, at, max_attempts, bonus, max_rewards, password_ok=True):
    """Both confirm steps against a store; returns (result, user) with user None unless ok."""
    from image_edit_server.core.email_codes import ConsumeResult

    result, pending = users.check_registration_code(email, code, at, max_attempts)
    if result is not ConsumeResult.OK:
        return result, None
    user = users.complete_registration(email, pending, password_ok, at, bonus, max_rewards)
    return result, user


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


def forget_recent_sends(client) -> None:
    """Stand in for a minute passing on a real-clock app, so the next code email is not limited."""
    from image_edit_server.api.deps import get_user_store

    users = client.app.dependency_overrides[get_user_store]()
    users._conn.execute("DELETE FROM email_sends")
    users._conn.commit()


def grant_bonus(user_store, user_id: str, credits: int) -> None:
    """Give an account bonus credits directly, as referral rewards would."""
    user_store._conn.execute(
        "UPDATE users SET bonus_credits = ? WHERE id = ?", (credits, user_id)
    )
    user_store._conn.commit()


def corrupt_plan(user_store, user_id: str, plan: str) -> None:
    """Store a plan value that set_plan would refuse, as a damaged database could hold."""
    user_store._conn.execute("UPDATE users SET plan = ? WHERE id = ?", (plan, user_id))
    user_store._conn.commit()


GOOGLE_AUDIENCE = "google-web.apps.example"
APPLE_BUNDLE = "com.example.imageedit"
TEST_KID = "test-key-1"


def make_rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwksClient:
    """Stands in for PyJWKClient: serves local public keys by kid, or fails like a dead endpoint."""

    def __init__(
        self, keys: dict, unreachable: bool = False, error: Optional[Exception] = None
    ) -> None:
        self._keys = keys
        self.unreachable = unreachable
        self.error = error

    def get_signing_key_from_jwt(self, token: str):
        if self.unreachable:
            raise jwt.PyJWKClientConnectionError("fetch failed")
        if self.error:
            raise self.error
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


MISSING = object()


def apple_claims(
    subject: str = "a-1",
    email: Optional[str] = "ana@example.com",
    raw_nonce: Optional[str] = "raw-nonce",
    email_verified: object = "true",
    **overrides,
) -> dict:
    """Apple sends email_verified as a string; pass MISSING to leave the claim out."""
    import hashlib

    claims = _base_claims("https://appleid.apple.com", APPLE_BUNDLE, subject, email)
    if email_verified is not MISSING:
        claims["email_verified"] = email_verified
    if raw_nonce is not None:
        claims["nonce"] = hashlib.sha256(raw_nonce.encode()).hexdigest()
    claims.update(overrides)
    return claims


class FakeVerifier:
    """An IdentityVerifier whose tokens are registered up front; unknown tokens are rejected."""

    def __init__(self, provider: str, clock: Callable[[], datetime]) -> None:
        self.provider = provider
        self._clock = clock
        self._outcomes: dict[str, object] = {}
        self.calls: list[tuple[str, Optional[str]]] = []

    def add(
        self,
        token: str,
        subject: str,
        email: Optional[str] = "ana@example.com",
        verified: bool = True,
        issued_at: Optional[datetime] = None,
    ) -> str:
        identity = ProviderIdentity(
            self.provider, subject, email, verified, issued_at or self._clock()
        )
        self._outcomes[token] = identity
        return token

    def fail_with(self, token: str, error: Exception) -> str:
        self._outcomes[token] = error
        return token

    def verify(self, token: str, *, nonce: Optional[str] = None) -> ProviderIdentity:
        self.calls.append((token, nonce))
        outcome = self._outcomes.get(token)
        if outcome is None:
            raise InvalidProviderToken("unknown token")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeAppleClient:
    """Stands in for AppleRevocationClient, recording what would be sent to Apple."""

    def __init__(self) -> None:
        self.refresh_token: Optional[str] = "apple-refresh-1"
        self.revoke_error: Optional[Exception] = None
        self.exchanged: list[str] = []
        self.revoked: list[str] = []

    def exchange_code(self, code: str) -> Optional[str]:
        self.exchanged.append(code)
        return self.refresh_token

    def revoke(self, token: str) -> None:
        self.revoked.append(token)
        if self.revoke_error:
            raise self.revoke_error


def write_apple_key_file(path: Path) -> Path:
    """Write a fresh P-256 private key in the PKCS8 PEM form Apple's .p8 files use."""
    key = ec.generate_private_key(ec.SECP256R1())
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return path


class FakeClassifier:
    """An image classifier whose score, failure and delay a test controls."""

    def __init__(self, score: float = 0.0, delay: float = 0.0) -> None:
        self.next_score = score
        self.error: Optional[Exception] = None
        self.delay = delay
        self.seen: list[bytes] = []

    def score(self, image_bytes: bytes) -> float:
        self.seen.append(image_bytes)
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.next_score
