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


V2_SCHEMA = OLD_SCHEMA + """
ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free';
ALTER TABLE users ADD COLUMN bonus_credits INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN referral_code TEXT;
ALTER TABLE users ADD COLUMN referred_by TEXT;
ALTER TABLE users ADD COLUMN referral_rewards INTEGER NOT NULL DEFAULT 0;
"""


@pytest.fixture
def v2_db(tmp_path) -> str:
    """A schema-version-2 file: users, a session, and one paid referral."""
    path = str(tmp_path / "v2.db")
    conn = sqlite3.connect(path)
    conn.executescript(V2_SCHEMA)
    conn.execute("PRAGMA user_version = 2")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
        " referral_code, referral_rewards) VALUES ('u0', 'a@example.com', 'h0',"
        " '2026-01-01T00:00:00+00:00', 5, 'AAAAAAAA', 1)"
    )
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
        " referral_code, referred_by) VALUES ('u1', 'b@example.com', 'h1',"
        " '2026-01-01T00:00:00+00:00', 5, 'BBBBBBBB', 'u0')"
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?, 'u0', '2026-01-01T00:00:00+00:00',"
        " '2099-01-01T00:00:00+00:00')",
        (hashlib.sha256(b"v2-token").hexdigest(),),
    )
    conn.commit()
    conn.close()
    return path


def _user_version(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_fresh_database_has_the_verification_schema(tmp_path):
    path = str(tmp_path / "fresh.db")
    store = SqliteUserStore(path)

    assert {"email_verified", "referral_bonus_pending"} <= _columns(path, "users")
    assert _columns(path, "email_codes") >= {
        "user_id", "purpose", "code_hash", "expires_at", "attempts", "created_at"
    }
    assert _columns(path, "email_sends") >= {"id", "user_id", "purpose", "sent_at"}
    assert _user_version(path) == 4
    assert store.create_user("ana@example.com", "hash").email_verified is False


def test_upgrading_a_v2_database_verifies_users_and_keeps_everything_else(v2_db):
    store = SqliteUserStore(v2_db)

    a, b = store.get_by_id("u0"), store.get_by_id("u1")

    assert (a.email_verified, b.email_verified) == (True, True)
    assert (a.bonus_credits, a.referral_rewards, b.bonus_credits) == (5, 1, 5)
    assert store.get_user_by_session("v2-token").id == "u0"
    pending = store._conn.execute(
        "SELECT SUM(referral_bonus_pending) FROM users"
    ).fetchone()[0]
    assert pending == 0
    assert _user_version(v2_db) == 4


def test_upgraded_users_are_not_paid_again_when_marked_verified(v2_db):
    store = SqliteUserStore(v2_db)

    assert store.mark_email_verified("u1", 5, 10) is False

    assert store.get_by_id("u1").bonus_credits == 5
    assert store.get_by_id("u0").bonus_credits == 5


def test_running_the_verification_migration_twice_changes_nothing(v2_db):
    first = SqliteUserStore(v2_db)
    first.create_user("new@example.com", "hash")
    first.close()

    second = SqliteUserStore(v2_db)

    assert second.get_by_email("new@example.com").email_verified is False
    assert second.get_by_id("u0").email_verified is True


V3_SCHEMA = V2_SCHEMA + """
ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN referral_bonus_pending INTEGER NOT NULL DEFAULT 0;
CREATE TABLE email_codes (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, purpose)
);
CREATE TABLE email_sends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,
    sent_at TEXT NOT NULL
);
"""


@pytest.fixture
def v3_db(tmp_path) -> str:
    """A schema-version-3 file: verified users, a session, an email code and a paid referral."""
    path = str(tmp_path / "v3.db")
    conn = sqlite3.connect(path)
    conn.executescript(V3_SCHEMA)
    conn.execute("PRAGMA user_version = 3")
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
        " referral_code, referral_rewards, email_verified) VALUES ('u0', 'a@example.com',"
        " 'h0', '2026-01-01T00:00:00+00:00', 5, 'AAAAAAAA', 1, 1)"
    )
    conn.execute(
        "INSERT INTO users (id, email, password_hash, created_at, bonus_credits,"
        " referral_code, referred_by, email_verified) VALUES ('u1', 'b@example.com',"
        " 'h1', '2026-01-01T00:00:00+00:00', 5, 'BBBBBBBB', 'u0', 1)"
    )
    conn.execute(
        "INSERT INTO sessions VALUES (?, 'u0', '2026-01-01T00:00:00+00:00',"
        " '2099-01-01T00:00:00+00:00')",
        (hashlib.sha256(b"v3-token").hexdigest(),),
    )
    conn.execute(
        "INSERT INTO email_codes VALUES ('u1', 'verify_email', 'x',"
        " '2099-01-01T00:00:00+00:00', 0, '2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()
    return path


def test_fresh_database_has_the_identity_schema(tmp_path):
    path = str(tmp_path / "fresh.db")
    SqliteUserStore(path)

    assert {"created_via", "referral_redeemed"} <= _columns(path, "users")
    assert _columns(path, "identities") >= {
        "provider", "subject", "user_id", "email", "apple_refresh_token", "created_at"
    }
    assert _user_version(path) == 4


def test_upgrading_a_v3_database_keeps_everything_and_adds_no_identities(v3_db):
    store = SqliteUserStore(v3_db)

    a, b = store.get_by_id("u0"), store.get_by_id("u1")

    assert (a.email_verified, b.email_verified) == (True, True)
    assert (a.bonus_credits, a.referral_rewards, b.bonus_credits) == (5, 1, 5)
    assert store.get_password_hash("u0") == "h0"
    assert store.get_user_by_session("v3-token").id == "u0"
    assert store._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0] == 1
    assert store._conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0
    vias = store._conn.execute("SELECT DISTINCT created_via FROM users").fetchall()
    assert vias == [("password",)]
    assert (a.has_password, b.has_password) == (True, True)
    assert store.list_providers("u0") == []
    assert _user_version(v3_db) == 4


def test_running_the_identity_migration_twice_changes_nothing(v3_db):
    first = SqliteUserStore(v3_db)
    before = first._conn.execute(
        "SELECT id, created_via, referral_redeemed, bonus_credits FROM users ORDER BY id"
    ).fetchall()
    first.close()

    second = SqliteUserStore(v3_db)

    after = second._conn.execute(
        "SELECT id, created_via, referral_redeemed, bonus_credits FROM users ORDER BY id"
    ).fetchall()
    assert after == before
    assert second.get_by_id("u1").bonus_credits == 5
