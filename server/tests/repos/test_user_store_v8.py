import sqlite3

from image_edit_server.repos.user_store import SqliteUserStore


def _user_version(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def _tables(path) -> set:
    conn = sqlite3.connect(path)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def _user_rows(path) -> list:
    conn = sqlite3.connect(path)
    try:
        return conn.execute(
            "SELECT id, email, password_hash, created_at, plan, referral_code"
            " FROM users ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _make_v7_file(tmp_path) -> str:
    """A file as the previous release left it: no role column, no templates or meta table."""
    path = str(tmp_path / "v7.db")
    store = SqliteUserStore(path)
    store.create_user("ana@example.com", "hash-ana")
    store.create_user("ben@example.com", "hash-ben")
    store.close()
    conn = sqlite3.connect(path)
    conn.executescript(
        "DROP TABLE templates; DROP TABLE meta; ALTER TABLE users DROP COLUMN role;"
    )
    conn.execute("PRAGMA user_version = 7")
    conn.commit()
    conn.close()
    return path


def test_fresh_database_is_at_v8_and_new_users_are_not_admins(tmp_path):
    path = str(tmp_path / "fresh8.db")
    store = SqliteUserStore(path)

    assert _user_version(path) == 8
    assert {"templates", "meta"} <= _tables(path)
    assert store.create_user("ana@example.com", "hash").role == "user"


def test_v7_file_upgrades_with_every_account_a_user_and_nothing_else_changed(tmp_path):
    path = _make_v7_file(tmp_path)
    before = _user_rows(path)

    store = SqliteUserStore(path)

    assert _user_version(path) == 8
    roles = [store.get_by_email(e).role for e in ("ana@example.com", "ben@example.com")]
    assert roles == ["user", "user"]
    assert _user_rows(path) == before
    assert not store.are_templates_seeded()
    assert store.list_templates() == []


def test_rerunning_the_v8_migration_is_a_no_op(tmp_path):
    path = _make_v7_file(tmp_path)
    SqliteUserStore(path).close()
    snapshot = _user_rows(path)

    SqliteUserStore(path).close()

    assert _user_rows(path) == snapshot
    assert _user_version(path) == 8


def test_a_file_with_the_role_column_but_no_templates_table_heals(tmp_path):
    path = _make_v7_file(tmp_path)
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    conn.commit()
    conn.close()

    store = SqliteUserStore(path)

    assert {"templates", "meta"} <= _tables(path)
    assert store.get_by_email("ana@example.com").role == "user"


def test_set_role_changes_the_role_and_rejects_unknown_roles(tmp_path):
    store = SqliteUserStore(str(tmp_path / "r.db"))
    store.create_user("ana@example.com", "hash")

    assert store.set_role("ana@example.com", "admin") is True
    assert store.get_by_email("ana@example.com").role == "admin"
    assert store.set_role("nobody@example.com", "admin") is False
    try:
        store.set_role("ana@example.com", "root")
    except ValueError:
        pass
    else:
        raise AssertionError("an unknown role must be refused")
