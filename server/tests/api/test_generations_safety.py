import io
import logging
from datetime import datetime, timedelta, timezone

import pytest

from tests.api.test_generations_quota import PNG

HOUR = timedelta(hours=1)


def _submit(client, **data):
    data = data or {"prompt": "a family at sunset"}
    return client.post(
        "/generations",
        data=data,
        files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))],
    )


def _remaining(client) -> int:
    return client.get("/me").json()["usage"]["remaining"]


def _strike_n_hours_ago(user_store, user_id, *ages, window=timedelta(hours=24)):
    now = datetime.now(timezone.utc)
    for age in ages:
        user_store.record_strike(user_id, now - age * HOUR, window)


def test_a_blocked_prompt_is_refused_without_echo_job_or_cost(client, store):
    before = _remaining(client)

    resp = _submit(client, prompt="a blockedword portrait")

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "prompt_blocked"
    assert "blockedword" not in resp.text
    assert "portrait" not in resp.text
    assert list(store.list_queued()) == []
    assert _remaining(client) == before


def test_a_disguised_term_is_refused(client):
    resp = _submit(client, prompt="N-U-D-3 beach")

    assert resp.json()["detail"]["error"] == "prompt_blocked"


def test_a_harmless_word_containing_a_term_is_allowed(client):
    assert _submit(client, prompt="a classic grassy blockedwords-free field").status_code == 202


def test_template_prompts_are_not_screened(client, catalog, safety_service):
    safety_service._matcher = type("M", (), {"matches": lambda self, text: True})()

    resp = _submit(client, template_id="sunset-beach")

    assert resp.status_code == 202


def test_a_flagged_photo_is_refused_with_nothing_stored_or_counted(
    client, store, settings, tmp_path, upload_classifier
):
    upload_classifier.next_score = 0.9
    before = _remaining(client)

    resp = _submit(client)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "photo_blocked"
    assert list(store.list_queued()) == []
    assert _remaining(client) == before
    assert not (tmp_path / "storage" / "inputs").exists() or not list(
        (tmp_path / "storage" / "inputs").iterdir()
    )


def test_a_score_just_under_the_threshold_continues(client, upload_classifier):
    upload_classifier.next_score = 0.69

    assert _submit(client).status_code == 202


def test_a_score_at_the_threshold_is_flagged(client, upload_classifier):
    upload_classifier.next_score = 0.7

    assert _submit(client).status_code == 400


def test_every_photo_is_checked(client, upload_classifier):
    resp = client.post(
        "/generations",
        data={"prompt": "two people"},
        files=[("faces", ("a.png", io.BytesIO(PNG), "image/png")),
               ("faces", ("b.png", io.BytesIO(PNG), "image/png"))],
    )

    assert resp.status_code == 202
    assert len(upload_classifier.seen) == 2


def test_an_upload_classifier_error_is_503_and_counts_nothing(client, store, upload_classifier):
    upload_classifier.error = RuntimeError("model crashed")
    before = _remaining(client)

    resp = _submit(client)

    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "safety_unavailable"
    assert list(store.list_queued()) == []
    assert _remaining(client) == before


def test_safe_input_still_gets_202(client):
    assert _submit(client).status_code == 202


def test_three_strikes_pause_generating_with_the_end_time(client, user_store, user_id, upload_classifier):
    _strike_n_hours_ago(user_store, user_id, 10, 5, 1)

    resp = _submit(client)

    assert resp.status_code == 403
    detail = resp.json()["detail"]
    assert detail["error"] == "generation_suspended"
    expected = datetime.now(timezone.utc) + 14 * HOUR
    assert abs(datetime.fromisoformat(detail["suspended_until"]) - expected) < timedelta(minutes=1)


def test_the_pause_is_raised_before_any_upload_is_read(client, user_store, user_id, upload_classifier):
    _strike_n_hours_ago(user_store, user_id, 3, 2, 1)

    resp = client.post("/generations", data={"prompt": "x"})

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "generation_suspended"
    assert upload_classifier.seen == []


def test_other_endpoints_still_work_while_paused(client, user_store, user_id):
    job_id = _submit(client).json()["job_id"]
    _strike_n_hours_ago(user_store, user_id, 3, 2, 1)

    assert client.get("/me").status_code == 200
    assert client.get(f"/generations/{job_id}").status_code == 200


def test_the_pause_ends_by_itself(client, user_store, user_id):
    _strike_n_hours_ago(user_store, user_id, 25, 5, 1)

    assert _submit(client).status_code == 202


def test_two_strikes_do_not_pause(client, user_store, user_id):
    _strike_n_hours_ago(user_store, user_id, 5, 1)

    assert _submit(client).status_code == 202


def test_a_blocked_prompt_is_logged_with_the_account_but_not_the_prompt(client, user_id, caplog):
    with caplog.at_level(logging.INFO):
        _submit(client, prompt="a blockedword portrait")

    assert "prompt_blocked" in caplog.text
    assert user_id in caplog.text
    assert "blockedword" not in caplog.text
    assert "portrait" not in caplog.text
