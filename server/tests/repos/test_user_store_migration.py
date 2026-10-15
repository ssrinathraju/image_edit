import hashlib
import sqlite3

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.referral_codes import ALPHABET
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path

OLD_SCHEMA = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _columns(path, table) -> set:
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


@pytest.fixture
def old_db(tmp_path) -> str:
    """A database written by the previous release, with users and a session."""
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    for i in range(3):
        conn.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            (f"u{i}", f"user{i}@example.com", f"hash{i}", "2026-01-01T00:00:00+00:00"),
        )
    # Valid until 2099 so it still resolves whenever the test runs.
    conn.execute(
        "INSERT INTO sessions VALUES (?, ?, ?, ?)",
        (
            hashlib.sha256(b"old-token").hexdigest(),
            "u0",
            "2026-01-01T00:00:00+00:00",
            "2099-01-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()
    return path


def test_fresh_database_has_the_new_schema(tmp_path):
    path = str(tmp_path / "fresh.db")
    store = SqliteUserStore(path)

    assert {"plan", "bonus_credits", "referral_code", "referred_by", "referral_rewards"} <= _columns(path, "users")
    assert _columns(path, "generation_usage") >= {"reservation_id", "user_id", "day", "source", "refunded"}
    user = store.create_user("ana@example.com", "hash")
    assert (user.plan, user.bonus_credits, user.referral_rewards) == ("free", 0, 0)
    assert len(user.referral_code) == 8


def test_old_database_is_upgraded_in_place(old_db):
    store = SqliteUserStore(old_db)

    users = [store.get_by_id(f"u{i}") for i in range(3)]

    assert [u.email for u in users] == [f"user{i}@example.com" for i in range(3)]
    assert all(u.plan == "free" and u.bonus_credits == 0 for u in users)
    codes = [u.referral_code for u in users]
    assert len(set(codes)) == 3
    assert all(len(c) == 8 and set(c) <= set(ALPHABET) for c in codes)
    assert store.get_password_hash("u1") == "hash1"
    assert store.get_user_by_session("old-token").id == "u0"


def test_running_the_migration_twice_changes_nothing(old_db):
    first = SqliteUserStore(old_db)
    codes = {u: first.get_by_id(u).referral_code for u in ("u0", "u1", "u2")}
    first.close()

    second = SqliteUserStore(old_db)

    assert {u: second.get_by_id(u).referral_code for u in codes} == codes


def test_a_half_migrated_file_heals(old_db):
    conn = sqlite3.connect(old_db)
    conn.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
    conn.commit()
    conn.close()

    store = SqliteUserStore(old_db)

    assert store.get_by_id("u0").referral_code


def test_auth_db_path_defaults_to_the_storage_root_and_honours_an_override(tmp_path):
    assert auth_db_path(Settings(STORAGE_ROOT=str(tmp_path))) == str(tmp_path / "app.db")
    assert auth_db_path(Settings(STORAGE_ROOT=str(tmp_path), AUTH_DB_PATH="/x/y.db")) == "/x/y.db"
