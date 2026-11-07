import pytest

from tests.helpers import ADULT_DOB, DEFAULT_PASSWORD

ADDRESS_HEADER = {"X-Forwarded-For": "6.6.6.6, 198.51.100.7"}


@pytest.fixture(autouse=True)
def real_limits(monkeypatch):
    monkeypatch.setattr("image_edit_server.core.signup_limiter.MAX_PER_HOUR", 5)
    monkeypatch.setattr("image_edit_server.core.signup_limiter.MAX_PER_DAY", 10)


def _register(client, n, headers=None):
    return client.post(
        "/auth/register",
        json={
            "email": f"user{n}@example.com",
            "password": DEFAULT_PASSWORD,
            "date_of_birth": ADULT_DOB,
        },
        headers=headers,
    )


def _google(client, token):
    return client.post(
        "/auth/oauth/google", json={"id_token": token, "date_of_birth": ADULT_DOB}
    )


def _fill_hour(client, headers=None):
    for n in range(5):
        assert _register(client, n, headers).status_code == 202


def _error(resp) -> str:
    return resp.json()["detail"]["error"]


def test_the_sixth_registration_in_an_hour_is_refused_with_retry_after(
    anon_client, sender
):
    _fill_hour(anon_client)
    sent_before = len(sender.sent)

    resp = _register(anon_client, 5)

    assert resp.status_code == 429
    assert _error(resp) == "too_many_signups"
    assert int(resp.headers["Retry-After"]) == 3600
    assert len(sender.sent) == sent_before


def test_a_refused_registration_stores_nothing(anon_client, user_store):
    _fill_hour(anon_client)

    _register(anon_client, 5)

    count = user_store._conn.execute(
        "SELECT COUNT(*) FROM pending_registrations WHERE email = ?",
        ("user5@example.com",),
    ).fetchone()[0]
    assert count == 0


def test_the_daily_limit_applies_when_fewer_than_five_fall_in_the_last_hour(
    anon_client, clock
):
    for n in range(10):
        assert _register(anon_client, n).status_code == 202
        clock.advance(hours=2)

    resp = _register(anon_client, 10)

    assert resp.status_code == 429
    assert _error(resp) == "too_many_signups"
    assert int(resp.headers["Retry-After"]) == 4 * 3600


def test_another_address_is_unaffected(anon_client, settings):
    settings.TRUSTED_PROXY_HOPS = 1
    _fill_hour(anon_client, {"X-Forwarded-For": "198.51.100.8"})
    other = {"X-Forwarded-For": "198.51.100.7"}

    assert _register(anon_client, 50, other).status_code == 202


def test_registration_is_accepted_again_after_the_wait(anon_client, clock):
    _fill_hour(anon_client)
    wait = int(_register(anon_client, 5).headers["Retry-After"])

    clock.advance(seconds=wait + 1)

    assert _register(anon_client, 5).status_code == 202


def test_a_refused_request_is_not_counted(anon_client, clock):
    _fill_hour(anon_client)
    for n in range(5, 12):
        assert _register(anon_client, n).status_code == 429

    clock.advance(hours=1, seconds=1)

    assert _register(anon_client, 5).status_code == 202


def test_a_provider_sign_up_counts_and_is_refused_at_the_limit(
    anon_client, google_verifier, user_store
):
    _fill_hour(anon_client)
    google_verifier.add("g-new", "g-1", email="gina@example.com")

    resp = _google(anon_client, "g-new")

    assert resp.status_code == 429
    assert _error(resp) == "too_many_signups"
    assert "Retry-After" in resp.headers
    assert user_store.get_by_email("gina@example.com") is None


def test_a_provider_sign_up_is_counted_toward_the_limit(anon_client, google_verifier):
    for n in range(5):
        google_verifier.add(f"g-{n}", f"sub-{n}", email=f"g{n}@example.com")
        assert _google(anon_client, f"g-{n}").status_code == 200

    assert _register(anon_client, 99).status_code == 429


def test_a_provider_sign_in_to_an_existing_account_succeeds_at_the_limit(
    anon_client, google_verifier
):
    google_verifier.add("g-old", "g-1", email="gina@example.com")
    assert _google(anon_client, "g-old").status_code == 200
    for n in range(4):
        assert _register(anon_client, n).status_code == 202

    resp = _google(anon_client, "g-old")

    assert resp.status_code == 200
    assert resp.json()["created"] is False


def test_linking_a_provider_to_an_existing_email_account_is_not_counted(
    anon_client, google_verifier, sender
):
    assert _register(anon_client, 0).status_code == 202
    code = sender.last_code("user0@example.com")
    anon_client.post(
        "/auth/register/confirm",
        json={"email": "user0@example.com", "code": code, "password": DEFAULT_PASSWORD},
    )
    for n in range(1, 5):
        assert _register(anon_client, n).status_code == 202
    google_verifier.add("g-link", "g-9", email="user0@example.com")

    link = _google(anon_client, "g-link")

    assert link.status_code == 200 and link.json()["created"] is False
    google_verifier.add("g-fresh", "g-8", email="fresh@example.com")
    assert _google(anon_client, "g-fresh").status_code == 429


def test_the_forwarded_address_is_counted_behind_one_trusted_hop(anon_client, settings):
    settings.TRUSTED_PROXY_HOPS = 1
    _fill_hour(anon_client, ADDRESS_HEADER)

    same_client = _register(anon_client, 5, {"X-Forwarded-For": "1.2.3.4, 198.51.100.7"})
    other_client = _register(anon_client, 6, {"X-Forwarded-For": "6.6.6.6, 198.51.100.8"})

    assert same_client.status_code == 429
    assert other_client.status_code == 202


def test_the_forwarded_header_is_ignored_with_no_trusted_hops(anon_client):
    _fill_hour(anon_client, {"X-Forwarded-For": "1.1.1.1"})

    resp = _register(anon_client, 5, {"X-Forwarded-For": "2.2.2.2"})

    assert resp.status_code == 429
