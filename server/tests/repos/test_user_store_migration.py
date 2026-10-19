import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.core.passwords import hash_password
from image_edit_server.core.referral_codes import ALPHABET
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path
from image_edit_server.services.auth_service import AuthService

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


def _verified_flags(store) -> dict:
    rows = store._conn.execute("SELECT id, email_verified FROM users").fetchall()
    return dict(rows)


def test_fresh_database_has_the_email_keyed_code_schema(tmp_path):
    path = str(tmp_path / "fresh.db")
    store = SqliteUserStore(path)

    assert {"email_verified", "referral_bonus_pending"} <= _columns(path, "users")
    assert _columns(path, "email_codes") == {
        "email", "purpose", "code_hash", "expires_at", "attempts", "created_at"
    }
    assert _columns(path, "email_sends") == {"id", "email", "purpose", "sent_at"}
    assert _columns(path, "pending_registrations") == {
        "email", "password_hash", "referral_code", "created_at"
    }
    assert _user_version(path) == 5
    assert _verified_flags(SqliteUserStore(path)) == {}
    created = store.create_user("ana@example.com", "hash")
    assert _verified_flags(store) == {created.id: 1}


def test_upgrading_a_v2_database_verifies_users_and_keeps_everything_else(v2_db):
    store = SqliteUserStore(v2_db)

    a, b = store.get_by_id("u0"), store.get_by_id("u1")

    assert _verified_flags(store) == {"u0": 1, "u1": 1}
    assert (a.bonus_credits, a.referral_rewards, b.bonus_credits) == (5, 1, 5)
    assert store.get_user_by_session("v2-token").id == "u0"
    assert _user_version(v2_db) == 5


def test_running_the_migration_twice_changes_nothing_for_new_accounts(v2_db):
    first = SqliteUserStore(v2_db)
    created = first.create_user("new@example.com", "hash")
    first.close()

    second = SqliteUserStore(v2_db)

    assert _verified_flags(second) == {"u0": 1, "u1": 1, created.id: 1}


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
    """A schema-version-3 file: verified users, a session, a paid referral, and an
    unverified account holding a verification code."""
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
        "INSERT INTO users (id, email, password_hash, created_at, referral_code,"
        " email_verified) VALUES ('u2', 'c@example.com', ?, '2026-01-01T00:00:00+00:00',"
        " 'CCCCCCCC', 0)",
        (hash_password("correct horse battery"),),
    )
    conn.execute(
        "INSERT INTO email_codes VALUES ('u2', 'verify_email', 'x',"
        " '2099-01-01T00:00:00+00:00', 0, '2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO email_sends (user_id, purpose, sent_at) VALUES"
        " ('u2', 'verify_email', '2026-01-01T00:00:00+00:00')"
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
    assert _user_version(path) == 5


def test_upgrading_a_v3_database_keeps_everything_and_adds_no_identities(v3_db):
    store = SqliteUserStore(v3_db)

    a, b = store.get_by_id("u0"), store.get_by_id("u1")

    assert (a.bonus_credits, a.referral_rewards, b.bonus_credits) == (5, 1, 5)
    assert store.get_password_hash("u0") == "h0"
    assert store.get_user_by_session("v3-token").id == "u0"
    assert store._conn.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0
    vias = store._conn.execute("SELECT DISTINCT created_via FROM users").fetchall()
    assert vias == [("password",)]
    assert (a.has_password, b.has_password) == (True, True)
    assert store.list_providers("u0") == []
    assert _user_version(v3_db) == 5


def test_upgrading_a_v3_database_verifies_an_unverified_account_and_it_can_log_in(v3_db):
    store = SqliteUserStore(v3_db)
    throttle = LoginThrottle(5, timedelta(minutes=15))
    auth = AuthService(store, throttle, Settings(), lambda _: None, object())

    token, user = auth.login("c@example.com", "correct horse battery")

    assert _verified_flags(store)["u2"] == 1
    assert store.get_user_by_session(token).id == user.id == "u2"


def test_upgrading_a_v3_database_recreates_the_code_tables_by_email(v3_db):
    store = SqliteUserStore(v3_db)

    assert _columns(v3_db, "email_codes") == {
        "email", "purpose", "code_hash", "expires_at", "attempts", "created_at"
    }
    assert _columns(v3_db, "email_sends") == {"id", "email", "purpose", "sent_at"}
    assert store._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0] == 0
    assert store._conn.execute("SELECT COUNT(*) FROM email_sends").fetchone()[0] == 0
    assert store._conn.execute(
        "SELECT COUNT(*) FROM pending_registrations"
    ).fetchone()[0] == 0


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


def test_running_the_migration_twice_keeps_codes_written_after_the_first_run(v3_db):
    first = SqliteUserStore(v3_db)
    first._conn.execute(
        "INSERT INTO email_codes VALUES ('c@example.com', 'registration', 'x',"
        " '2099-01-01T00:00:00+00:00', 0, '2026-01-01T00:00:00+00:00')"
    )
    first._conn.commit()
    first.close()

    second = SqliteUserStore(v3_db)

    assert second._conn.execute("SELECT COUNT(*) FROM email_codes").fetchone()[0] == 1
    assert _verified_flags(second) == {"u0": 1, "u1": 1, "u2": 1}


AGE_AND_CONSENT_COLUMNS = {"age_confirmed_at", "consent_version", "consent_at"}


@pytest.fixture
def v4_db(v3_db) -> str:
    """A schema-version-4 file: the v3 accounts, migrated, then stripped of the v5 columns."""
    SqliteUserStore(v3_db).close()
    conn = sqlite3.connect(v3_db)
    for column in AGE_AND_CONSENT_COLUMNS:
        conn.execute(f"ALTER TABLE users DROP COLUMN {column}")
    conn.execute("PRAGMA user_version = 4")
    conn.commit()
    conn.close()
    return v3_db


def test_fresh_database_has_the_age_and_consent_columns(tmp_path):
    path = str(tmp_path / "fresh.db")
    SqliteUserStore(path)

    assert AGE_AND_CONSENT_COLUMNS <= _columns(path, "users")


def test_upgrading_a_v4_database_leaves_age_and_consent_empty_and_keeps_the_rest(v4_db):
    assert not AGE_AND_CONSENT_COLUMNS & _columns(v4_db, "users")

    store = SqliteUserStore(v4_db)

    a, b = store.get_by_id("u0"), store.get_by_id("u1")
    assert AGE_AND_CONSENT_COLUMNS <= _columns(v4_db, "users")
    for user in (a, b):
        assert user.age_confirmed is False
        assert (user.age_confirmed_at, user.consent_version, user.consent_at) == (
            None, None, None
        )
    assert (a.bonus_credits, a.referral_rewards, b.bonus_credits) == (5, 1, 5)
    assert store.get_password_hash("u0") == "h0"
    assert store.get_user_by_session("v3-token").id == "u0"
    assert _user_version(v4_db) == 5


def test_running_the_v5_migration_twice_changes_nothing(v4_db):
    first = SqliteUserStore(v4_db)
    before = first._conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    first.close()

    second = SqliteUserStore(v4_db)

    assert second._conn.execute("SELECT * FROM users ORDER BY id").fetchall() == before


def test_upgrading_a_v4_database_discards_registrations_started_before_the_age_check(v4_db):
    conn = sqlite3.connect(v4_db)
    conn.execute(
        "INSERT INTO pending_registrations (email, password_hash, created_at)"
        " VALUES ('kid@example.com', 'h', ?)",
        (datetime.now(timezone.utc).isoformat(),),
    )
    conn.commit()
    conn.close()

    store = SqliteUserStore(v4_db)

    assert store._conn.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[0] == 0
