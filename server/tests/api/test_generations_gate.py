from datetime import timedelta
from pathlib import Path

import pytest

from tests.api.test_generations_submit import VALID_PROMPT, _face


def _upload_count(settings) -> int:
    inputs = Path(settings.STORAGE_ROOT) / "inputs"
    return len(list(inputs.iterdir())) if inputs.exists() else 0


def _remaining(client, headers=None) -> int:
    return client.get("/me", headers=headers).json()["usage"]["remaining"]


@pytest.fixture
def unconfirmed_headers(user_store) -> dict:
    user = user_store.create_user("old@example.com", "hash")
    token = user_store.create_session(user.id, timedelta(days=1))
    return {"Authorization": f"Bearer {token}"}


def test_an_unconfirmed_age_is_refused_first_and_nothing_is_counted(
    anon_client, unconfirmed_headers, store, settings
):
    before = _remaining(anon_client, unconfirmed_headers)

    resp = anon_client.post(
        "/generations",
        data={"prompt": VALID_PROMPT},
        files=[_face()],
        headers=unconfirmed_headers,
    )

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "age_not_confirmed"
    assert store.list_for_user(
        anon_client.get("/me", headers=unconfirmed_headers).json()["id"]
    ) == []
    assert _remaining(anon_client, unconfirmed_headers) == before
    assert _upload_count(settings) == 0


def test_missing_consent_is_refused_and_no_face_is_stored(unconsented_client, settings):
    before = _remaining(unconsented_client)

    resp = unconsented_client.post(
        "/generations", data={"prompt": VALID_PROMPT}, files=[_face()]
    )

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "consent_required"
    assert _upload_count(settings) == 0
    assert _remaining(unconsented_client) == before


def test_outdated_consent_is_refused(client, settings):
    settings.CONSENT_VERSION = "2"

    resp = client.post("/generations", data={"prompt": VALID_PROMPT}, files=[_face()])

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "consent_required"


def test_the_gate_comes_before_input_validation(unconsented_client):
    resp = unconsented_client.post("/generations", data={}, files=[])

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "consent_required"


def test_withdrawn_consent_blocks_the_next_submission(client):
    client.delete("/me/consent")

    resp = client.post("/generations", data={"prompt": VALID_PROMPT}, files=[_face()])

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "consent_required"


def test_a_confirmed_and_consenting_account_can_generate(client):
    resp = client.post("/generations", data={"prompt": VALID_PROMPT}, files=[_face()])

    assert resp.status_code == 202
    assert resp.json()["job_id"]
