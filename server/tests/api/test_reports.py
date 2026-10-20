import io
import logging
from datetime import timedelta

import pytest

from image_edit_server.repos import file_storage
from image_edit_server.schemas.job import Job, JobStatus
from tests.api.test_generations_quota import PNG

SERVER_IMAGE = b"server-side-image"
DEVICE_IMAGE = PNG


@pytest.fixture
def my_job(store, settings, user_id) -> str:
    """A succeeded job of the signed-in account whose image is still on the server."""
    job_id = store.create(Job(id="", prompt="p", user_id=user_id))
    store.update(job_id, status=JobStatus.succeeded)
    path = file_storage.output_path(job_id, settings.STORAGE_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(SERVER_IMAGE)
    return job_id


def _report(client, job_id, category="violence", note=None, image=None, content_type="image/png", headers=None):
    data = {"job_id": job_id, "category": category}
    if note is not None:
        data["note"] = note
    files = [("image", ("r.png", io.BytesIO(image), content_type))] if image is not None else None
    return client.post("/reports", data=data, files=files, headers=headers)


def _rows(user_store):
    return user_store.list_open_reports()


def _report_files(settings):
    return file_storage.list_report_image_files(settings.STORAGE_ROOT)


def test_a_recent_result_is_reported_with_the_servers_copy(client, user_store, settings, my_job):
    resp = _report(client, my_job, image=DEVICE_IMAGE)

    assert resp.status_code == 201
    (report,) = _rows(user_store)
    assert (report.job_id, report.category, report.image_source) == (my_job, "violence", "server")
    stored = file_storage.report_image_path(report.image_name, settings.STORAGE_ROOT)
    assert stored.read_bytes() == SERVER_IMAGE
    assert resp.json()["report_id"] == report.id


def test_an_old_creation_is_reported_with_the_devices_copy(client, user_store, settings):
    resp = _report(client, "expired-job", image=DEVICE_IMAGE)

    assert resp.status_code == 201
    (report,) = _rows(user_store)
    assert report.image_source == "device"
    stored = file_storage.report_image_path(report.image_name, settings.STORAGE_ROOT)
    assert stored.read_bytes() == DEVICE_IMAGE


def test_a_report_without_any_image_is_recorded_with_source_none(client, user_store, settings):
    resp = _report(client, "expired-job")

    assert resp.status_code == 201
    (report,) = _rows(user_store)
    assert (report.image_source, report.image_name) == ("none", None)
    assert _report_files(settings) == []


def test_the_note_is_stored(client, user_store, my_job):
    _report(client, my_job, note="looks wrong")

    assert _rows(user_store)[0].note == "looks wrong"


def test_another_accounts_job_is_404_and_stores_nothing(client, store, user_store, settings):
    other = store.create(Job(id="", prompt="p", user_id="someone-else"))
    store.update(other, status=JobStatus.succeeded)

    resp = _report(client, other, image=DEVICE_IMAGE)

    assert resp.status_code == 404
    assert _rows(user_store) == []
    assert _report_files(settings) == []


@pytest.mark.parametrize("category", ["spam", "", "SEXUAL"])
def test_an_unknown_category_is_refused(client, user_store, settings, category):
    resp = _report(client, "job", category=category, image=DEVICE_IMAGE)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_report"
    assert _rows(user_store) == []
    assert _report_files(settings) == []


def test_a_note_over_500_characters_is_refused_and_500_is_accepted(client, user_store):
    too_long = _report(client, "job", note="x" * 501)
    exactly = _report(client, "job", note="x" * 500)

    assert too_long.status_code == 400
    assert too_long.json()["detail"]["error"] == "invalid_report"
    assert exactly.status_code == 201
    assert len(_rows(user_store)) == 1


def test_an_invalid_uploaded_image_is_refused_and_stores_nothing(client, user_store, settings):
    wrong_type = _report(client, "job", image=b"x", content_type="text/plain")

    assert wrong_type.status_code == 400
    assert wrong_type.json()["detail"]["error"] == "invalid_image"
    assert _rows(user_store) == []
    assert _report_files(settings) == []


def test_an_oversized_uploaded_image_is_refused(client, user_store, settings, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10)

    resp = _report(client, "job", image=b"x" * 11)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_image"
    assert _rows(user_store) == []


def test_an_invalid_upload_is_ignored_when_the_servers_copy_is_used(client, user_store, my_job):
    resp = _report(client, my_job, image=b"x", content_type="text/plain")

    assert resp.status_code == 201
    assert _rows(user_store)[0].image_source == "server"


def test_a_job_whose_image_vanished_falls_back_to_the_devices_copy(client, store, user_store, user_id):
    job_id = store.create(Job(id="", prompt="p", user_id=user_id))
    store.update(job_id, status=JobStatus.succeeded)

    resp = _report(client, job_id, image=DEVICE_IMAGE)

    assert resp.status_code == 201
    assert _rows(user_store)[0].image_source == "device"


def test_a_failed_job_has_no_server_copy(client, store, settings, user_store, user_id):
    job_id = store.create(Job(id="", prompt="p", user_id=user_id))
    store.update(job_id, status=JobStatus.failed)
    path = file_storage.output_path(job_id, settings.STORAGE_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"should not be copied")

    _report(client, job_id)

    assert _rows(user_store)[0].image_source == "none"


def test_reports_need_a_session(anon_client):
    assert _report(anon_client, "job").status_code == 401


def test_the_twenty_first_report_in_a_day_is_refused_and_stores_nothing(client, user_store, settings):
    for _ in range(20):
        assert _report(client, "job", image=DEVICE_IMAGE).status_code == 201

    resp = _report(client, "job", image=DEVICE_IMAGE)

    assert resp.status_code == 429
    assert resp.json()["detail"]["error"] == "too_many_reports"
    assert len(_rows(user_store)) == 20
    assert len(_report_files(settings)) == 20


def test_the_cap_resets_after_a_day(client, clock, settings):
    for _ in range(20):
        _report(client, "job")
    clock.advance(hours=25)

    assert _report(client, "job").status_code == 201


def test_report_created_is_logged_without_the_note(client, user_id, caplog):
    with caplog.at_level(logging.INFO):
        _report(client, "job", note="secret detail")

    assert "report_created" in caplog.text
    assert user_id in caplog.text
    assert "secret detail" not in caplog.text


def test_a_report_missing_its_fields_is_invalid_report_not_a_422(client, user_store):
    resp = client.post("/reports", data={})

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_report"
