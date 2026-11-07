from datetime import datetime, timezone

import pytest

from image_edit_server.core.identity_verifier import ProviderIdentity
from image_edit_server.repos.user_store import SqliteUserStore
from tests.helpers import make_token_cipher

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
SECRET = "refresh-secret"


def _raw_apple_token(users, user_id):
    return users._conn.execute(
        "SELECT apple_refresh_token FROM identities WHERE user_id = ? AND provider = 'apple'",
        (user_id,),
    ).fetchone()[0]


def _set_raw_apple_token(users, user_id, value):
    users._conn.execute(
        "UPDATE identities SET apple_refresh_token = ? WHERE user_id = ? AND provider = 'apple'",
        (value, user_id),
    )
    users._conn.commit()


def _linked_apple_user(users, email="ana@example.com", subject="a-1"):
    user = users.create_user(email, "hash")
    users.link_identity(user.id, ProviderIdentity("apple", subject, email, True, T0), T0)
    return user


@pytest.fixture
def sealed_users():
    return SqliteUserStore(":memory:", token_cipher=make_token_cipher())


def test_the_stored_apple_token_is_encrypted_and_reads_back(sealed_users):
    user = _linked_apple_user(sealed_users)

    sealed_users.set_apple_refresh_token(user.id, SECRET)

    raw = _raw_apple_token(sealed_users, user.id)
    assert raw.startswith("v1:") and SECRET not in raw
    assert sealed_users.get_apple_refresh_token(user.id) == SECRET


def test_a_value_copied_onto_another_account_is_unreadable_and_warned(sealed_users, caplog):
    ana = _linked_apple_user(sealed_users)
    bob = _linked_apple_user(sealed_users, "bob@example.com", "a-2")
    sealed_users.set_apple_refresh_token(ana.id, SECRET)
    _set_raw_apple_token(sealed_users, bob.id, _raw_apple_token(sealed_users, ana.id))

    with caplog.at_level("WARNING"):
        assert sealed_users.get_apple_refresh_token(bob.id) is None

    assert f"apple_token_unreadable user={bob.id}" in caplog.text
    assert SECRET not in caplog.text


def test_reading_under_a_different_key_returns_none(tmp_path, caplog):
    path = str(tmp_path / "app.db")
    first = SqliteUserStore(path, token_cipher=make_token_cipher(1))
    user = _linked_apple_user(first)
    first.set_apple_refresh_token(user.id, SECRET)
    first.close()

    second = SqliteUserStore(path, token_cipher=make_token_cipher(2))
    with caplog.at_level("WARNING"):
        assert second.get_apple_refresh_token(user.id) is None
    assert f"apple_token_unreadable user={user.id}" in caplog.text


def test_unlink_returns_the_decrypted_token(sealed_users):
    user = _linked_apple_user(sealed_users)
    sealed_users.set_apple_refresh_token(user.id, SECRET)

    assert sealed_users.unlink_identity(user.id, "apple") == SECRET


def test_unlink_of_a_damaged_value_completes_with_none_and_a_warning(sealed_users, caplog):
    user = _linked_apple_user(sealed_users)
    sealed_users.set_apple_refresh_token(user.id, SECRET)
    damaged = _raw_apple_token(sealed_users, user.id)[:-4] + "AAAA"
    _set_raw_apple_token(sealed_users, user.id, damaged)

    with caplog.at_level("WARNING"):
        assert sealed_users.unlink_identity(user.id, "apple") is None

    assert sealed_users.list_providers(user.id) == []
    assert f"apple_token_unreadable user={user.id}" in caplog.text


def test_storing_an_apple_token_without_a_cipher_is_refused():
    users = SqliteUserStore(":memory:")
    user = _linked_apple_user(users)

    with pytest.raises(RuntimeError, match="TOKEN_ENCRYPTION_KEY"):
        users.set_apple_refresh_token(user.id, SECRET)

    assert _raw_apple_token(users, user.id) is None


def _database_with_plain_and_sealed_tokens(path):
    seed = SqliteUserStore(path, token_cipher=make_token_cipher())
    plain = _linked_apple_user(seed, "plain@example.com", "a-1")
    sealed = _linked_apple_user(seed, "sealed@example.com", "a-2")
    seed.set_apple_refresh_token(sealed.id, "kept-secret")
    _set_raw_apple_token(seed, plain.id, "plain-text-secret")
    kept = _raw_apple_token(seed, sealed.id)
    seed.close()
    return plain, sealed, kept


@pytest.mark.parametrize("with_key", [True, False])
def test_startup_discards_plain_text_tokens_and_keeps_encrypted_ones(tmp_path, caplog, with_key):
    path = str(tmp_path / "app.db")
    plain, sealed, kept = _database_with_plain_and_sealed_tokens(path)

    with caplog.at_level("INFO"):
        reopened = SqliteUserStore(path, token_cipher=make_token_cipher() if with_key else None)

    assert _raw_apple_token(reopened, plain.id) is None
    assert reopened.list_providers(plain.id) == ["apple"]
    assert _raw_apple_token(reopened, sealed.id) == kept
    assert "apple_tokens_discarded count=1" in caplog.text
    assert "plain-text-secret" not in caplog.text and kept not in caplog.text


def test_startup_logs_nothing_when_no_plain_text_token_exists(tmp_path, caplog):
    path = str(tmp_path / "app.db")
    SqliteUserStore(path, token_cipher=make_token_cipher()).close()

    with caplog.at_level("INFO"):
        SqliteUserStore(path, token_cipher=make_token_cipher())

    assert "apple_tokens_discarded" not in caplog.text
