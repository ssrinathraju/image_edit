import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
