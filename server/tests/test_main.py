import pytest

from tests.helpers import TEST_TEMPLATES, build_templates_dir
from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from image_edit_server.repos.template_catalog import CatalogError


def test_create_app_fails_on_duplicate_template_id(tmp_path):
    entries = [TEST_TEMPLATES[0], {**TEST_TEMPLATES[1], "id": TEST_TEMPLATES[0]["id"]}]
    templates_dir = build_templates_dir(tmp_path / "t", entries)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with pytest.raises(CatalogError, match=TEST_TEMPLATES[0]["id"]):
        create_app(settings)


def test_session_survives_an_app_restart_on_the_same_storage_root(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings, sender=RecordingSender())) as first:
        headers = register_headers(first, "ana@example.com")
    assert (tmp_path / "s" / "app.db").exists()

    with TestClient(create_app(settings)) as second:
        resp = second.get("/me", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["email"] == "ana@example.com"


def test_auth_db_path_setting_overrides_the_default_location(tmp_path, templates_dir):
    db_path = tmp_path / "elsewhere" / "users.db"
    settings = Settings(
        TEMPLATES_DIR=str(templates_dir),
        STORAGE_ROOT=str(tmp_path / "s"),
        AUTH_DB_PATH=str(db_path),
    )

    create_app(settings)

    assert db_path.exists()
    assert not (tmp_path / "s" / "app.db").exists()


def test_generations_lost_to_a_restart_are_refunded_at_startup(tmp_path, templates_dir):
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient

    from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path
    from tests.helpers import RecordingSender, register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    with TestClient(create_app(settings, sender=RecordingSender())) as first:
        headers = register_headers(first, "ana@example.com")
        user_id = first.get("/me", headers=headers).json()["id"]

    # Two jobs that were accepted and then died with the process.
    ledger = SqliteUserStore(auth_db_path(settings))
    for _ in range(2):
        ledger.reserve_generation(user_id, 3, datetime.now(timezone.utc))
    ledger.close()

    with TestClient(create_app(settings)) as second:
        usage = second.get("/me", headers=headers).json()["usage"]

    assert usage["used_today"] == 0
    assert usage["remaining"] == 3


def _age(path, hours):
    import os
    import time

    stamp = time.time() - hours * 3600
    os.utime(path, (stamp, stamp))


def test_startup_sweep_runs_before_the_first_request(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    root = tmp_path / "s"
    (root / "outputs").mkdir(parents=True)
    (root / "inputs" / "lost-job").mkdir(parents=True)
    (root / "inputs" / "lost-job" / "face_0.jpg").write_bytes(b"face")
    old, fresh = root / "outputs" / "old.png", root / "outputs" / "fresh.png"
    old.write_bytes(b"x")
    fresh.write_bytes(b"x")
    _age(old, 48)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(root))

    with TestClient(create_app(settings)):
        # Entering the context ran startup; no request has been made yet.
        assert not old.exists()
        assert fresh.exists()
        assert not (root / "inputs" / "lost-job").exists()


def test_a_failing_startup_sweep_does_not_stop_the_app(tmp_path, templates_dir, monkeypatch):
    from fastapi.testclient import TestClient

    async def broken_sweep(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr("image_edit_server.main.sweep", broken_sweep)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings)) as client:
        assert client.get("/templates").status_code == 200


def test_the_retention_task_is_cancelled_on_shutdown(tmp_path, templates_dir, monkeypatch):
    import asyncio

    from fastapi.testclient import TestClient

    events = []

    async def fake_retention(store, cfg):
        events.append("started")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            events.append("cancelled")
            raise

    monkeypatch.setattr("image_edit_server.main.run_retention", fake_retention)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings)):
        pass

    assert events == ["started", "cancelled"]


def test_invalid_retention_settings_stop_the_server_from_starting():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="OUTPUT_RETENTION_HOURS"):
        Settings(OUTPUT_RETENTION_HOURS=0)


def test_log_sender_is_chosen_without_smtp_host_and_warns(tmp_path, templates_dir, caplog):
    from image_edit_server.services.email.log_sender import LogSender

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    from image_edit_server.main import _make_email_sender

    with caplog.at_level("WARNING"):
        sender = _make_email_sender(settings)

    assert isinstance(sender, LogSender)
    assert "NOT delivered" in caplog.text


def test_smtp_sender_is_chosen_with_smtp_host_and_does_not_warn(tmp_path, templates_dir, caplog):
    from image_edit_server.main import _make_email_sender
    from image_edit_server.services.email.smtp_sender import SmtpSender

    settings = Settings(
        TEMPLATES_DIR=str(templates_dir),
        STORAGE_ROOT=str(tmp_path / "s"),
        SMTP_HOST="smtp.example.com",
        SMTP_FROM="noreply@example.com",
    )

    with caplog.at_level("WARNING"):
        sender = _make_email_sender(settings)

    assert isinstance(sender, SmtpSender)
    assert "NOT delivered" not in caplog.text


def test_an_injected_sender_receives_the_registration_email(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    sender = RecordingSender()
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings, sender=sender)) as client:
        register_headers(client, "ana@example.com")

    assert sender.count_for("ana@example.com") == 1


def test_without_smtp_the_registration_code_is_in_the_server_log(
    tmp_path, templates_dir, caplog
):
    from fastapi.testclient import TestClient

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with caplog.at_level("INFO"), TestClient(create_app(settings)) as client:
        resp = client.post(
            "/auth/register",
            json={"email": "ana@example.com", "password": "correct horse battery"},
        )

    assert resp.status_code == 202
    assert "ana@example.com" in caplog.text
    assert "registration code is" in caplog.text


def test_a_validation_error_never_echoes_the_secrets_that_were_sent(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    secrets = ["identity-token-secret", "auth-code-secret", "password-secret", "provider-token-secret"]

    with TestClient(create_app(settings, sender=RecordingSender())) as client:
        headers = register_headers(client, "ana@example.com")
        apple = client.post(
            "/auth/oauth/apple",
            json={"identity_token": secrets[0], "authorization_code": secrets[1]},
        )
        delete = client.request(
            "DELETE",
            "/me",
            json={"password": secrets[2], "provider": "google", "token": secrets[3]},
            headers=headers,
        )

    assert (apple.status_code, delete.status_code) == (422, 422)
    assert apple.json()["detail"][0]["loc"] == ["body", "nonce"]
    for resp in (apple, delete):
        for secret in secrets:
            assert secret not in resp.text
