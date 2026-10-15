import json
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


def grant_bonus(user_store, user_id: str, credits: int) -> None:
    """Give an account bonus credits directly, as referral rewards would."""
    user_store._conn.execute(
        "UPDATE users SET bonus_credits = ? WHERE id = ?", (credits, user_id)
    )
    user_store._conn.commit()
