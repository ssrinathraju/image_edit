import io

import pytest

from tests.helpers import corrupt_plan, grant_bonus

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _submit(client, **data):
    data = data or {"prompt": "a family at sunset"}
    return client.post(
        "/generations",
        data=data,
        files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))],
    )


def _remaining(client) -> int:
    return client.get("/me").json()["usage"]["remaining"]


def test_fourth_generation_is_refused_and_creates_no_job(client, store):
    for _ in range(3):
        assert _submit(client).status_code == 202
    jobs_before = len(list(store.list_queued()))

    resp = _submit(client)

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "quota_exceeded"
    assert len(list(store.list_queued())) == jobs_before


def test_validation_failures_do_not_consume_a_generation(client):
    empty_prompt = client.post("/generations", data={"prompt": "  "}, files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))])
    no_photo = client.post("/generations", data={"prompt": "x"})
    bad_template = _submit(client, template_id="nope")
    bad_type = client.post(
        "/generations",
        data={"prompt": "x"},
        files=[("faces", ("f.txt", io.BytesIO(b"x"), "text/plain"))],
    )

    assert [r.status_code for r in (empty_prompt, no_photo, bad_template, bad_type)] == [400] * 4
    assert _remaining(client) == 3


def test_a_bonus_credit_covers_the_fourth(client, user_store, user_id):
    grant_bonus(user_store, user_id, 5)
    for _ in range(3):
        assert _submit(client).status_code == 202

    assert _submit(client).status_code == 202

    usage = client.get("/me").json()["usage"]
    assert (usage["used_today"], usage["bonus_credits"]) == (3, 4)


def test_premium_allows_a_fourth(client, user_store):
    user_store.set_plan("ana@example.com", "premium")

    for _ in range(4):
        assert _submit(client).status_code == 202


def test_an_unknown_stored_plan_submits_with_the_free_limit(client, user_store, user_id, caplog):
    corrupt_plan(user_store, user_id, "gold")

    codes = [_submit(client).status_code for _ in range(4)]

    assert codes == [202, 202, 202, 429]
    assert user_id in caplog.text
    assert "gold" not in caplog.text


def test_plan_change_applies_without_a_restart(client, user_store):
    for _ in range(3):
        _submit(client)
    assert _submit(client).status_code == 429

    user_store.set_plan("ana@example.com", "premium")

    assert _submit(client).status_code == 202


def test_an_upload_failure_releases_the_reservation(client, monkeypatch):
    def broken_save(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(
        "image_edit_server.services.generation_service.file_storage.save_upload",
        broken_save,
    )
    # The server error is raised to the test client, which re-raises by default.
    with pytest.raises(OSError):
        _submit(client)

    assert _remaining(client) == 3


def test_a_status_request_does_not_consume_a_generation(client, store):
    job_id = _submit(client).json()["job_id"]
    before = _remaining(client)

    client.get(f"/generations/{job_id}")

    assert _remaining(client) == before == 2


def test_anonymous_submission_consumes_nothing(anon_client, client):
    resp = anon_client.post("/generations", data={"prompt": "x"})

    assert resp.status_code == 401
    assert _remaining(client) == 3
