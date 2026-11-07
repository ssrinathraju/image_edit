from tests.helpers import DEFAULT_PASSWORD, make_token_cipher

SECRET = "apple-refresh-1"


def _sign_in_with_apple(client, apple_verifier, code="c", subject="a-1"):
    apple_verifier.add(f"signin-{subject}", subject, email=f"{subject}@example.com")
    resp = client.post(
        "/auth/oauth/apple",
        json={
            "identity_token": f"signin-{subject}",
            "nonce": "n",
            "authorization_code": code,
            "date_of_birth": "1990-01-01",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"], {"Authorization": f"Bearer {resp.json()['token']}"}


def _delete_apple_account(client, apple_verifier, clock, headers, subject="a-1"):
    apple_verifier.add("fresh", subject, email=f"{subject}@example.com", issued_at=clock.now)
    body = {"provider": "apple", "token": "fresh", "nonce": "n"}
    return client.request("DELETE", "/me", json=body, headers=headers)


def _raw_token(user_store, user_id):
    return user_store._conn.execute(
        "SELECT apple_refresh_token FROM identities WHERE user_id = ?", (user_id,)
    ).fetchone()[0]


def _set_raw_token(user_store, user_id, value):
    user_store._conn.execute(
        "UPDATE identities SET apple_refresh_token = ? WHERE user_id = ?", (value, user_id)
    )
    user_store._conn.commit()


def test_sign_in_stores_an_encrypted_token_that_deletion_revokes(
    anon_client, apple_verifier, apple_client, user_store, clock
):
    user_id, headers = _sign_in_with_apple(anon_client, apple_verifier)

    raw = _raw_token(user_store, user_id)
    assert raw.startswith("v1:") and SECRET not in raw
    resp = _delete_apple_account(anon_client, apple_verifier, clock, headers)

    assert resp.status_code == 204
    assert apple_client.revoked == [SECRET]


def test_deletion_after_a_key_change_completes_without_revoking_and_warns(
    anon_client, apple_verifier, apple_client, user_store, clock, caplog
):
    user_id, headers = _sign_in_with_apple(anon_client, apple_verifier)
    user_store._token_cipher = make_token_cipher(99)

    with caplog.at_level("WARNING"):
        resp = _delete_apple_account(anon_client, apple_verifier, clock, headers)

    assert resp.status_code == 204
    assert apple_client.revoked == []
    assert f"apple_token_unreadable user={user_id}" in caplog.text
    assert SECRET not in caplog.text


def test_unlinking_apple_with_a_damaged_value_completes_without_revoking(
    client, apple_verifier, apple_client, user_store, caplog
):
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")
    client.post(
        "/me/providers/apple",
        json={
            "identity_token": "tok",
            "nonce": "n",
            "authorization_code": "c",
            "reauth": {"password": DEFAULT_PASSWORD},
        },
    )
    user_id = client.get("/me").json()["id"]
    _set_raw_token(user_store, user_id, _raw_token(user_store, user_id)[:-4] + "AAAA")

    with caplog.at_level("WARNING"):
        resp = client.request(
            "DELETE", "/me/providers/apple", json={"reauth": {"password": DEFAULT_PASSWORD}}
        )

    assert resp.status_code == 204
    assert client.get("/me").json()["providers"] == []
    assert apple_client.revoked == []
    assert f"apple_token_unreadable user={user_id}" in caplog.text


def test_a_value_copied_onto_another_account_is_not_revoked_on_deletion(
    anon_client, apple_verifier, apple_client, user_store, clock
):
    ana_id, _ = _sign_in_with_apple(anon_client, apple_verifier, subject="a-1")
    bob_id, bob_headers = _sign_in_with_apple(anon_client, apple_verifier, subject="a-2")
    _set_raw_token(user_store, bob_id, _raw_token(user_store, ana_id))

    resp = _delete_apple_account(anon_client, apple_verifier, clock, bob_headers, subject="a-2")

    assert resp.status_code == 204
    assert apple_client.revoked == []


def test_deleting_an_account_whose_plain_text_token_was_discarded_revokes_nothing(
    anon_client, apple_verifier, apple_client, user_store, clock, caplog
):
    user_id, headers = _sign_in_with_apple(anon_client, apple_verifier)
    _set_raw_token(user_store, user_id, "legacy-plain-text-token")

    user_store._discard_unencrypted_apple_tokens()
    with caplog.at_level("WARNING"):
        resp = _delete_apple_account(anon_client, apple_verifier, clock, headers)

    assert resp.status_code == 204
    assert apple_client.revoked == []
    assert "apple_token_unreadable" not in caplog.text


def test_a_discarded_plain_text_token_is_replaced_by_the_next_sign_in_with_a_code(
    anon_client, apple_verifier, apple_client, user_store, clock
):
    user_id, headers = _sign_in_with_apple(anon_client, apple_verifier)
    _set_raw_token(user_store, user_id, "legacy-plain-text-token")

    user_store._discard_unencrypted_apple_tokens()

    assert _raw_token_gone(user_store, user_id)
    assert user_store.list_providers(user_id) == ["apple"]
    again_id, headers = _sign_in_with_apple(anon_client, apple_verifier, code="after-upgrade")
    assert again_id == user_id
    assert _raw_token(user_store, user_id).startswith("v1:")
    resp = _delete_apple_account(anon_client, apple_verifier, clock, headers)
    assert resp.status_code == 204
    assert apple_client.revoked == [SECRET]


def _raw_token_gone(user_store, user_id) -> bool:
    row = user_store._conn.execute(
        "SELECT apple_refresh_token FROM identities WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row is None or row[0] is None


def test_the_next_sign_in_with_a_code_after_a_key_change_stores_a_fresh_token(
    anon_client, apple_verifier, apple_client, user_store, clock
):
    user_id, headers = _sign_in_with_apple(anon_client, apple_verifier)
    user_store._token_cipher = make_token_cipher(99)
    apple_client.refresh_token = "apple-refresh-2"

    _sign_in_with_apple(anon_client, apple_verifier, code="second-code")
    resp = _delete_apple_account(anon_client, apple_verifier, clock, headers)

    assert apple_client.exchanged == ["c", "second-code"]
    assert resp.status_code == 204
    assert apple_client.revoked == ["apple-refresh-2"]
