from tests.helpers import DEFAULT_PASSWORD

ANA = "ana@example.com"
PASSWORD_REAUTH = {"reauth": {"password": DEFAULT_PASSWORD}}


def _link_google(client, token, headers=None, reauth=None):
    body = {"id_token": token, "reauth": reauth or PASSWORD_REAUTH["reauth"]}
    return client.post("/me/providers/google", json=body, headers=headers)


def _link_apple(client, token, headers=None, code="auth-code", reauth=None):
    body = {
        "identity_token": token,
        "nonce": "n",
        "authorization_code": code,
        "reauth": reauth or PASSWORD_REAUTH["reauth"],
    }
    return client.post("/me/providers/apple", json=body, headers=headers)


def _unlink(client, provider, body=None, headers=None):
    return client.request(
        "DELETE", f"/me/providers/{provider}", json=body or PASSWORD_REAUTH, headers=headers
    )


def _providers(client, headers=None):
    return client.get("/me", headers=headers).json()["providers"]


def _error(resp):
    return resp.json()["detail"]["error"]


def _sign_in_google(client, token):
    return client.post("/auth/oauth/google", json={"id_token": token, "date_of_birth": "1990-01-01"})


def _provider_only_account(client, verifier, path, subject, email, body):
    verifier.add(f"signin-{subject}", subject, email=email)
    resp = client.post(path, json={**body, "date_of_birth": "1990-01-01"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['token']}"}


def _google_only(client, google_verifier, subject="g-1", email="gina@example.com"):
    return _provider_only_account(
        client, google_verifier, "/auth/oauth/google", subject, email, {"id_token": f"signin-{subject}"}
    )


def _apple_only(client, apple_verifier, subject="a-1", email="ann@example.com"):
    body = {"identity_token": f"signin-{subject}", "nonce": "n", "authorization_code": "c"}
    return _provider_only_account(client, apple_verifier, "/auth/oauth/apple", subject, email, body)


# ── link ──


def test_linking_google_lists_it_and_leaves_the_email_alone(client, google_verifier):
    google_verifier.add("tok", "g-1", email="other@gmail.com")

    resp = _link_google(client, "tok")

    assert resp.status_code == 200
    assert _providers(client) == ["google"]
    assert client.get("/me").json()["email"] == ANA


def test_signing_in_with_the_linked_identity_reaches_the_account(
    client, anon_client, google_verifier
):
    google_verifier.add("tok", "g-1", email="other@gmail.com")
    _link_google(client, "tok")
    my_id = client.get("/me").json()["id"]

    resp = _sign_in_google(anon_client, "tok")

    assert resp.status_code == 200
    assert resp.json()["id"] == my_id and resp.json()["created"] is False


def test_an_identity_on_another_account_is_409_provider_in_use(
    client, anon_client, google_verifier
):
    _google_only(anon_client, google_verifier)
    google_verifier.add("tok", "g-1", email="gina@example.com")

    resp = _link_google(client, "tok")

    assert resp.status_code == 409 and _error(resp) == "provider_in_use"
    assert _providers(client) == []


def test_a_second_identity_of_one_provider_is_409_provider_already_linked(client, google_verifier):
    google_verifier.add("first", "g-1", email="one@gmail.com")
    google_verifier.add("second", "g-2", email="two@gmail.com")
    _link_google(client, "first")

    resp = _link_google(client, "second")

    assert resp.status_code == 409 and _error(resp) == "provider_already_linked"


def test_linking_the_same_identity_again_is_409_provider_already_linked(client, google_verifier):
    google_verifier.add("tok", "g-1", email="one@gmail.com")
    _link_google(client, "tok")

    assert _error(_link_google(client, "tok")) == "provider_already_linked"


def test_a_rejected_token_is_401(client):
    resp = _link_google(client, "never-registered")

    assert resp.status_code == 401 and _error(resp) == "invalid_provider_token"


def test_an_unconfigured_provider_is_503(client, verifiers, google_verifier):
    del verifiers["google"]

    assert _link_google(client, "tok").status_code == 503


def test_linking_apple_checks_the_nonce_and_stores_the_refresh_token(
    client, apple_verifier, apple_client
):
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")

    resp = _link_apple(client, "tok")

    assert resp.status_code == 200
    assert _providers(client) == ["apple"]
    assert apple_verifier.calls[-1] == ("tok", "n")
    assert apple_client.exchanged == ["auth-code"]


def test_linking_without_the_password_is_403_and_links_nothing(client, google_verifier):
    google_verifier.add("tok", "g-1", email="other@gmail.com")

    wrong = _link_google(client, "tok", reauth={"password": "wrong password"})

    assert wrong.status_code == 403 and _error(wrong) == "reauth_failed"
    assert _providers(client) == []
    body = {"id_token": "tok"}
    missing = client.post("/me/providers/google", json=body)
    assert missing.status_code == 422 and _providers(client) == []


def test_a_provider_only_account_links_apple_with_its_google(
    anon_client, google_verifier, apple_verifier, clock
):
    headers = _google_only(anon_client, google_verifier)
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")
    google_verifier.add("fresh", "g-1", issued_at=clock.now)

    resp = _link_apple(
        anon_client, "tok", headers, reauth={"provider": "google", "token": "fresh"}
    )

    assert resp.status_code == 200
    assert _providers(anon_client, headers) == ["apple", "google"]


def test_the_new_identity_cannot_vouch_for_itself(anon_client, google_verifier, apple_verifier, clock):
    headers = _google_only(anon_client, google_verifier)
    apple_verifier.add("tok", "a-1", issued_at=clock.now)

    resp = _link_apple(
        anon_client,
        "tok",
        headers,
        reauth={"provider": "apple", "token": "tok", "nonce": "n"},
    )

    assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert _providers(anon_client, headers) == ["google"]


def test_a_stolen_session_cannot_link_the_attackers_google_to_take_over(
    client, google_verifier, clock
):
    google_verifier.add("attacker", "g-evil", email="evil@gmail.com", issued_at=clock.now)
    stolen = {"provider": "google", "token": "attacker"}

    link = _link_google(client, "attacker", reauth=stolen)
    password = client.post(
        "/me/password", json={"new_password": "attacker chosen pass", "reauth": stolen}
    )
    email = client.post(
        "/me/email", json={"new_email": "evil@example.com", "reauth": stolen}
    )

    assert link.status_code == 403 and _error(link) == "reauth_failed"
    assert password.status_code == 403 and email.status_code == 403
    assert _providers(client) == []


def test_provider_form_refusals_on_a_password_account_record_no_lockout_failure(
    client, google_verifier, clock, settings
):
    google_verifier.add("attacker", "g-evil", email="evil@gmail.com", issued_at=clock.now)
    stolen = {"provider": "google", "token": "attacker"}

    for _ in range(settings.LOGIN_MAX_FAILURES + 1):
        assert _link_google(client, "attacker", reauth=stolen).status_code == 403

    login = client.post(
        "/auth/login", json={"email": "ana@example.com", "password": DEFAULT_PASSWORD}
    )
    assert login.status_code == 200


def test_a_password_account_cannot_reauthenticate_with_its_linked_google(
    client, google_verifier, clock
):
    google_verifier.add("tok", "g-1", email="other@gmail.com", issued_at=clock.now)
    assert _link_google(client, "tok").status_code == 200
    fresh = {"provider": "google", "token": "tok"}

    password = client.post(
        "/me/password", json={"new_password": "attacker chosen pass", "reauth": fresh}
    )
    email = client.post("/me/email", json={"new_email": "evil@example.com", "reauth": fresh})
    unlink = _unlink(client, "google", {"reauth": fresh})
    link_apple = _link_apple(client, "x", reauth=fresh)

    for resp in (password, email, unlink, link_apple):
        assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert _providers(client) == ["google"]
    assert client.post("/auth/login", json={"email": ANA, "password": DEFAULT_PASSWORD}).status_code == 200


def test_linking_needs_a_session(anon_client, google_verifier):
    google_verifier.add("tok", "g-1")

    assert _link_google(anon_client, "tok").status_code == 401


# ── unlink ──


def test_unlinking_with_a_password_present(client, anon_client, google_verifier):
    google_verifier.add("tok", "g-1", email="other@gmail.com")
    _link_google(client, "tok")
    my_id = client.get("/me").json()["id"]

    resp = _unlink(client, "google")

    assert resp.status_code == 204
    assert _providers(client) == []
    again = _sign_in_google(anon_client, "tok")
    assert again.json()["created"] is True and again.json()["id"] != my_id


def test_unlinking_with_a_wrong_password_is_403_and_keeps_the_link(client, google_verifier):
    google_verifier.add("tok", "g-1", email="other@gmail.com")
    _link_google(client, "tok")

    resp = _unlink(client, "google", {"reauth": {"password": "wrong password"}})

    assert resp.status_code == 403 and _error(resp) == "reauth_failed"
    assert _providers(client) == ["google"]


def test_unlinking_a_provider_that_is_not_linked_is_404(client):
    resp = _unlink(client, "google")

    assert resp.status_code == 404 and _error(resp) == "not_found"


def test_the_last_sign_in_method_is_kept(anon_client, apple_verifier, clock):
    headers = _apple_only(anon_client, apple_verifier)
    apple_verifier.add("fresh", "a-1", issued_at=clock.now)

    resp = _unlink(
        anon_client,
        "apple",
        {"reauth": {"provider": "apple", "token": "fresh", "nonce": "n"}},
        headers,
    )

    assert resp.status_code == 409 and _error(resp) == "last_sign_in_method"
    assert _providers(anon_client, headers) == ["apple"]


def test_a_provider_only_account_can_unlink_one_when_another_remains(
    anon_client, google_verifier, apple_verifier, clock
):
    headers = _google_only(anon_client, google_verifier)
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")
    google_verifier.add("fresh", "g-1", issued_at=clock.now)
    reauth = {"provider": "google", "token": "fresh"}
    assert _link_apple(anon_client, "tok", headers, reauth=reauth).status_code == 200
    google_verifier.add("fresh", "g-1", issued_at=clock.now)

    resp = _unlink(
        anon_client, "google", {"reauth": {"provider": "google", "token": "fresh"}}, headers
    )

    assert resp.status_code == 204
    assert _providers(anon_client, headers) == ["apple"]


def test_setting_a_password_makes_the_last_provider_removable(
    anon_client, google_verifier, clock
):
    headers = _google_only(anon_client, google_verifier)
    google_verifier.add("fresh", "g-1", issued_at=clock.now)
    reauth = {"provider": "google", "token": "fresh"}
    anon_client.post(
        "/me/password", json={"new_password": "a brand new passphrase", "reauth": reauth}, headers=headers
    )

    resp = _unlink(
        anon_client, "google", {"reauth": {"password": "a brand new passphrase"}}, headers
    )

    assert resp.status_code == 204


def test_unlinking_apple_revokes_its_stored_token(client, apple_verifier, apple_client):
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")
    _link_apple(client, "tok")

    resp = _unlink(client, "apple")

    assert resp.status_code == 204
    assert apple_client.revoked == ["apple-refresh-1"]


def test_a_failing_revocation_does_not_block_the_unlink_and_is_logged(
    client, apple_verifier, apple_client, caplog
):
    apple_verifier.add("tok", "a-1", email="relay@privaterelay.appleid.com")
    _link_apple(client, "tok")
    apple_client.revoke_error = RuntimeError("apple is down")

    with caplog.at_level("WARNING"):
        resp = _unlink(client, "apple")

    assert resp.status_code == 204
    assert _providers(client) == []
    assert "Apple revocation failed" in caplog.text
    assert "apple-refresh-1" not in caplog.text


def test_unlinking_google_revokes_nothing(client, google_verifier, apple_client):
    google_verifier.add("tok", "g-1", email="other@gmail.com")
    _link_google(client, "tok")

    _unlink(client, "google")

    assert apple_client.revoked == []


def test_an_unknown_provider_in_the_path_is_422(client):
    assert _unlink(client, "twitter").status_code == 422
