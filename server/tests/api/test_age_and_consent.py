import logging
from datetime import timedelta

import pytest

from tests.helpers import register_headers

# The fake clock reads 2026-01-01.
SECRET_DOB = "1987-03-14"
EXACTLY_18 = "2008-01-01"
ONE_DAY_SHORT = "2008-01-02"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def unconfirmed_headers(user_store) -> dict:
    """An account from before the upgrade: no confirmed age and no consent."""
    user = user_store.create_user("old@example.com", "hash")
    return _bearer(user_store.create_session(user.id, timedelta(days=1)))


def _me(client, headers=None) -> dict:
    return client.get("/me", headers=headers).json()


# ── Check a date of birth ───────────────────────────────────────────────


def test_exactly_18_today_is_accepted(anon_client, unconfirmed_headers):
    resp = anon_client.post(
        "/me/age", json={"date_of_birth": EXACTLY_18}, headers=unconfirmed_headers
    )

    assert resp.status_code == 200


@pytest.mark.parametrize("text", ["2008-13-01", "08/05/2001", "2026-01-02", "1987-03-14T00:00", "1987-03-14 "])
def test_malformed_or_future_dates_are_400(anon_client, unconfirmed_headers, text):
    resp = anon_client.post(
        "/me/age", json={"date_of_birth": text}, headers=unconfirmed_headers
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_date_of_birth"


NOT_A_DATE_STRING = [
    pytest.param(19900101, "19900101", id="number"),
    pytest.param(True, "true", id="boolean"),
    pytest.param({}, "{}", id="object"),
    pytest.param([], "[]", id="list"),
    pytest.param("x" * 200, "x" * 200, id="200-character-string"),
    pytest.param(None, "null", id="null"),
]


def _assert_invalid_date_of_birth(resp, sent_text: str) -> None:
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_date_of_birth"
    if sent_text not in ("null", "{}", "[]", "true"):
        assert sent_text not in resp.text


@pytest.mark.parametrize("value,sent_text", NOT_A_DATE_STRING)
def test_a_non_string_date_of_birth_is_400_on_age_confirmation(
    anon_client, unconfirmed_headers, value, sent_text
):
    resp = anon_client.post(
        "/me/age", json={"date_of_birth": value}, headers=unconfirmed_headers
    )

    _assert_invalid_date_of_birth(resp, sent_text)


@pytest.mark.parametrize("value,sent_text", NOT_A_DATE_STRING)
def test_a_non_string_date_of_birth_is_400_on_register(
    anon_client, sender, value, sent_text
):
    resp = anon_client.post(
        "/auth/register",
        json={"email": "ana@example.com", "password": "correct horse battery",
              "date_of_birth": value},
    )

    _assert_invalid_date_of_birth(resp, sent_text)
    assert sender.count_for("ana@example.com") == 0


@pytest.mark.parametrize(
    "value,sent_text", [case for case in NOT_A_DATE_STRING if case.values[0] is not None]
)
def test_a_non_string_date_of_birth_is_400_on_google_sign_in(
    anon_client, google_verifier, user_store, value, sent_text
):
    google_verifier.add("g-tok", "g-1")

    resp = anon_client.post(
        "/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": value}
    )

    _assert_invalid_date_of_birth(resp, sent_text)
    assert user_store._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_an_explicit_null_on_provider_sign_in_still_asks_for_a_date(
    anon_client, google_verifier
):
    google_verifier.add("g-tok", "g-1")

    resp = anon_client.post(
        "/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": None}
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "age_required"


# ── Confirm the age of an existing account ──────────────────────────────


def test_existing_account_confirms_its_age(anon_client, unconfirmed_headers):
    assert _me(anon_client, unconfirmed_headers)["age_confirmed"] is False

    resp = anon_client.post(
        "/me/age", json={"date_of_birth": SECRET_DOB}, headers=unconfirmed_headers
    )

    assert resp.status_code == 200
    assert _me(anon_client, unconfirmed_headers)["age_confirmed"] is True


def test_an_under_18_date_is_403_and_leaves_the_account_unconfirmed(
    anon_client, unconfirmed_headers
):
    resp = anon_client.post(
        "/me/age", json={"date_of_birth": ONE_DAY_SHORT}, headers=unconfirmed_headers
    )

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "under_age"
    assert _me(anon_client, unconfirmed_headers)["age_confirmed"] is False


def test_an_already_confirmed_account_gets_409(client):
    resp = client.post("/me/age", json={"date_of_birth": SECRET_DOB})

    assert resp.status_code == 409
    assert resp.json()["detail"]["error"] == "age_already_confirmed"


def test_confirming_age_needs_a_session(anon_client):
    resp = anon_client.post("/me/age", json={"date_of_birth": SECRET_DOB})

    assert resp.status_code == 401


# ── Existing accounts after the upgrade ─────────────────────────────────


def test_an_existing_account_reports_no_age_and_no_consent(anon_client, unconfirmed_headers):
    me = _me(anon_client, unconfirmed_headers)

    assert me["age_confirmed"] is False
    assert me["consent"]["accepted_version"] is None
    assert me["consent"]["accepted_at"] is None


# ── Record and withdraw consent ─────────────────────────────────────────


def test_the_current_version_is_accepted_and_reported(client, unconsented_client):
    resp = unconsented_client.post("/me/consent", json={"version": "1"})

    assert resp.status_code == 200
    consent = _me(unconsented_client)["consent"]
    assert consent["accepted_version"] == "1"
    assert consent["accepted_at"]
    assert consent["current_version"] == "1"


def test_an_outdated_version_is_refused_and_nothing_is_recorded(
    unconsented_client, settings
):
    settings.CONSENT_VERSION = "2"

    resp = unconsented_client.post("/me/consent", json={"version": "1"})

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "consent_version_mismatch"
    assert _me(unconsented_client)["consent"]["accepted_version"] is None


def test_withdrawal_removes_consent(client):
    resp = client.delete("/me/consent")

    assert resp.status_code == 204
    consent = _me(client)["consent"]
    assert consent["accepted_version"] is None and consent["accepted_at"] is None


def test_withdrawing_without_consent_is_still_204(unconsented_client):
    assert unconsented_client.delete("/me/consent").status_code == 204


def test_consent_endpoints_need_a_session(anon_client):
    assert anon_client.post("/me/consent", json={"version": "1"}).status_code == 401
    assert anon_client.delete("/me/consent").status_code == 401


# ── Report age and consent ──────────────────────────────────────────────


def test_a_new_account_without_consent_reports_age_confirmed_and_no_version(unconsented_client):
    me = _me(unconsented_client)

    assert me["age_confirmed"] is True
    assert me["consent"] == {
        "accepted_version": None,
        "accepted_at": None,
        "current_version": "1",
    }


# ── Never store the date of birth ───────────────────────────────────────


def _every_stored_value(user_store) -> str:
    tables = [row[0] for row in user_store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )]
    dump = []
    for table in tables:
        dump.extend(map(str, user_store._conn.execute(f"SELECT * FROM {table}").fetchall()))
    return "\n".join(dump)


def test_no_date_of_birth_is_stored_logged_or_returned(
    anon_client, sender, user_store, google_verifier, caplog
):
    google_verifier.add("g-tok", "g-1", email="gina@example.com")
    with caplog.at_level(logging.DEBUG):
        anon_client.post(
            "/auth/register",
            json={"email": "ana@example.com", "password": "correct horse battery",
                  "date_of_birth": SECRET_DOB},
        )
        confirmed = anon_client.post(
            "/auth/register/confirm",
            json={"email": "ana@example.com", "code": sender.last_code("ana@example.com"),
                  "password": "correct horse battery"},
        )
        anon_client.post(
            "/auth/oauth/google", json={"id_token": "g-tok", "date_of_birth": SECRET_DOB}
        )
        old = user_store.create_user("old@example.com", "hash")
        headers = _bearer(user_store.create_session(old.id, timedelta(days=1)))
        anon_client.post("/me/age", json={"date_of_birth": SECRET_DOB}, headers=headers)
        anon_client.post("/me/age", json={"date_of_birth": ONE_DAY_SHORT}, headers=headers)
        me = anon_client.get("/me", headers=_bearer(confirmed.json()["token"]))

    assert me.json()["age_confirmed"] is True
    assert SECRET_DOB not in me.text
    assert SECRET_DOB not in caplog.text
    assert ONE_DAY_SHORT not in caplog.text
    assert SECRET_DOB not in _every_stored_value(user_store)
    assert "date_of_birth" not in {
        row[1] for row in user_store._conn.execute("PRAGMA table_info(users)")
    }
    assert "date_of_birth" not in {
        row[1] for row in user_store._conn.execute("PRAGMA table_info(pending_registrations)")
    }
