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
        SMTP_FROM="noreply@example.com", SUPPORT_EMAIL="help@example.com",
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
            json={
                "email": "ana@example.com",
                "password": "correct horse battery",
                "date_of_birth": "1990-01-01",
            },
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


def test_importing_main_creates_nothing_under_the_default_storage(tmp_path):
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", "import image_edit_server.main as m; assert not hasattr(m, 'app')"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []


def test_startup_prunes_email_rows_and_survives_a_failure(tmp_path, templates_dir, monkeypatch):
    from fastapi.testclient import TestClient

    from image_edit_server.repos.user_store import SqliteUserStore

    calls = []

    def broken_prune(self, now):
        calls.append(now)
        raise RuntimeError("db locked")

    monkeypatch.setattr(SqliteUserStore, "prune_email_rows", broken_prune)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings)) as client:
        assert client.get("/templates").status_code == 200

    assert len(calls) == 1


@pytest.mark.parametrize(
    "flag,upload_flags,output_flags",
    [("none", False, False), ("outputs", False, True), ("all", True, True)],
)
def test_stub_flag_builds_the_matching_pair_of_stub_classifiers(flag, upload_flags, output_flags):
    from image_edit_server.main import _make_classifiers

    upload, output = _make_classifiers(Settings(SAFETY_STUB_FLAG=flag))

    assert (upload.score(b"x") == 1.0) is upload_flags
    assert (output.score(b"x") == 1.0) is output_flags


def test_stub_backend_starts_without_loading_a_classifier_model(tmp_path, templates_dir, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("the stub backend must not load a classifier model")

    monkeypatch.setattr("image_edit_server.main.LocalImageClassifier", explode)
    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    create_app(settings)


def test_real_backend_refuses_to_start_when_the_classifier_cannot_load(tmp_path, templates_dir, monkeypatch):
    def cannot_load(*args, **kwargs):
        raise ImportError("no module named transformers")

    monkeypatch.setattr("image_edit_server.main.LocalImageClassifier", cannot_load)
    settings = Settings(
        TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"), MODEL_BACKEND="sana"
    )

    with pytest.raises(RuntimeError, match="image classifier could not be loaded"):
        create_app(settings)


def test_real_backend_shares_one_classifier_between_uploads_and_outputs(monkeypatch):
    from image_edit_server.main import _make_classifiers

    built = []
    monkeypatch.setattr(
        "image_edit_server.main.LocalImageClassifier",
        lambda model_id, device: built.append((model_id, device)) or object(),
    )

    upload, output = _make_classifiers(Settings(MODEL_BACKEND="sana", SAFETY_DEVICE="cpu"))

    assert upload is output
    assert built == [("Falconsai/nsfw_image_detection", "cpu")]


# ── stored templates: seed import and startup checks ────────────────────────

import json  # noqa: E402
import shutil  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

REAL_SEED = Path(__file__).resolve().parents[1] / "seed" / "templates"
SEED_TEMPLATE_COUNT = 12


@pytest.fixture
def seed_copy(tmp_path) -> Path:
    """A temporary copy of the real seed folder; tests may edit it freely."""
    return Path(shutil.copytree(REAL_SEED, tmp_path / "seed-copy"))


def _app_for(tmp_path, seed_dir) -> TestClient:
    settings = Settings(TEMPLATES_DIR=str(seed_dir), STORAGE_ROOT=str(tmp_path / "s"))
    return TestClient(create_app(settings))


def _stored_store(tmp_path):
    from image_edit_server.repos.user_store import SqliteUserStore

    return SqliteUserStore(str(tmp_path / "s" / "app.db"))


def test_first_start_imports_all_seed_templates_with_hashed_previews(tmp_path, seed_copy):
    http = _app_for(tmp_path, seed_copy)

    listing = http.get("/templates").json()

    assert len(listing) == SEED_TEMPLATE_COUNT
    assert len({t["preview_url"] for t in listing}) == SEED_TEMPLATE_COUNT
    for item in listing:
        assert item["preview_url"].startswith("/template-previews/")
        assert item["preview_url"] != f"/template-previews/{item['id']}.webp"
        resp = http.get(item["preview_url"])
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/webp"


def test_second_start_with_an_edited_seed_ignores_it(tmp_path, seed_copy):
    first = _app_for(tmp_path, seed_copy)
    before = first.get("/templates").json()
    entries = json.loads((seed_copy / "catalog.json").read_text())
    (seed_copy / "catalog.json").write_text(json.dumps(entries[:2]))

    second = _app_for(tmp_path, seed_copy)

    assert second.get("/templates").json() == before


def test_start_after_every_template_is_retired_does_not_reimport(tmp_path, seed_copy):
    _app_for(tmp_path, seed_copy)
    store = _stored_store(tmp_path)
    for row in store.list_templates():
        store.set_template_retired(row.id, True, "t")
    store.close()

    second = _app_for(tmp_path, seed_copy)

    assert second.get("/templates").json() == []


def test_invalid_seed_with_a_missing_preview_fails_startup_and_names_the_entry(tmp_path, seed_copy):
    entries = json.loads((seed_copy / "catalog.json").read_text())
    (seed_copy / "previews" / entries[3]["preview"]).unlink()

    with pytest.raises(CatalogError, match=entries[3]["id"]):
        _app_for(tmp_path, seed_copy)

    assert not (tmp_path / "s" / "template-previews").exists() or not any(
        (tmp_path / "s" / "template-previews").iterdir()
    )


def test_stored_row_with_a_deleted_preview_fails_startup_and_names_the_id(tmp_path, seed_copy):
    _app_for(tmp_path, seed_copy)
    store = _stored_store(tmp_path)
    victim = store.list_templates()[0]
    store.close()
    (tmp_path / "s" / "template-previews" / victim.preview).unlink()

    with pytest.raises(CatalogError, match=victim.id):
        _app_for(tmp_path, seed_copy)


def test_unreferenced_preview_files_are_removed_at_startup(tmp_path, seed_copy):
    _app_for(tmp_path, seed_copy)
    stray = tmp_path / "s" / "template-previews" / "stray-123456.webp"
    stray.write_bytes(b"x")

    _app_for(tmp_path, seed_copy)

    assert not stray.exists()
    assert len(list((tmp_path / "s" / "template-previews").iterdir())) == SEED_TEMPLATE_COUNT


def test_create_app_makes_the_package_info_lines_visible(tmp_path, templates_dir):
    import logging

    package_logger = logging.getLogger("image_edit_server")
    saved = (package_logger.level, list(package_logger.handlers))
    package_logger.setLevel(logging.NOTSET)
    package_logger.handlers.clear()
    try:
        create_app(Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s")))

        assert package_logger.isEnabledFor(logging.INFO)
        assert package_logger.handlers
    finally:
        package_logger.setLevel(saved[0])
        package_logger.handlers[:] = saved[1]


def _signed_status_link(client, headers, storage_root):
    """Submit a job on a real app and return its status-call result_url once it succeeds."""
    import io
    import time

    from tests.api.test_generations_quota import PNG

    resp = client.post(
        "/generations",
        data={"prompt": "a calm lake"},
        files=[("faces", ("f.png", io.BytesIO(PNG), "image/png"))],
        headers=headers,
    )
    job_id = resp.json()["job_id"]
    for _ in range(100):
        body = client.get(f"/generations/{job_id}", headers=headers).json()
        if body["status"] == "succeeded":
            return job_id, body["result_url"]
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_an_empty_secret_gives_a_working_app_with_verifiable_links(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    with TestClient(create_app(settings, sender=RecordingSender())) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        _job_id, url = _signed_status_link(client, headers, tmp_path)

        assert client.get(url).status_code == 200


def test_a_short_secret_fails_startup_with_a_clear_message(tmp_path, templates_dir):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="RESULT_URL_SECRET must be at least 32 characters"):
        create_app(
            Settings(
                TEMPLATES_DIR=str(templates_dir),
                STORAGE_ROOT=str(tmp_path / "s"),
                RESULT_URL_SECRET="short",
            )
        )


def test_a_configured_secret_makes_links_work_across_instances(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    def build():
        return create_app(
            Settings(
                TEMPLATES_DIR=str(templates_dir),
                STORAGE_ROOT=str(tmp_path / "s"),
                RESULT_URL_SECRET="s" * 40,
            ),
            sender=RecordingSender(),
        )

    with TestClient(build()) as first:
        headers = register_headers(first, "ana@example.com", consent=True)
        _job_id, url = _signed_status_link(first, headers, tmp_path)
    with TestClient(build()) as second:
        assert second.get(url).status_code == 200


def test_links_from_a_random_secret_do_not_survive_a_restart(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    def build():
        return create_app(
            Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s")),
            sender=RecordingSender(),
        )

    with TestClient(build()) as first:
        headers = register_headers(first, "ana@example.com", consent=True)
        _job_id, url = _signed_status_link(first, headers, tmp_path)
    with TestClient(build()) as second:
        assert second.get(url).status_code == 404


def test_the_secret_and_signatures_never_reach_the_logs(tmp_path, templates_dir, caplog):
    import logging

    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    secret = "very-secret-value-" + "x" * 20
    caplog.set_level(logging.DEBUG)
    settings = Settings(
        TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"), RESULT_URL_SECRET=secret
    )
    with TestClient(create_app(settings, sender=RecordingSender())) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        _job_id, url = _signed_status_link(client, headers, tmp_path)
        client.get(url)

    signature = url.split("sig=")[1]
    # The test client's own httpx lines echo the URL it requested; only the server's logs count.
    server_log = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(("image_edit_server", "uvicorn"))
    )
    assert "random secret" not in server_log  # a configured secret logs no notice at all
    assert secret not in server_log
    assert signature not in server_log


def test_an_empty_secret_logs_the_notice_and_a_set_secret_does_not(tmp_path, templates_dir, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="image_edit_server")
    create_app(Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "a")))
    assert any(
        r.levelno == logging.INFO and "RESULT_URL_SECRET is not set" in r.getMessage()
        for r in caplog.records
    )

    caplog.clear()
    create_app(
        Settings(
            TEMPLATES_DIR=str(templates_dir),
            STORAGE_ROOT=str(tmp_path / "b"),
            RESULT_URL_SECRET="s" * 40,
        )
    )
    assert not any("RESULT_URL_SECRET" in r.getMessage() for r in caplog.records)


def test_the_real_app_refuses_an_unsigned_link_to_an_existing_image(tmp_path, templates_dir):
    from fastapi.testclient import TestClient

    from tests.helpers import RecordingSender, register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    with TestClient(create_app(settings, sender=RecordingSender())) as client:
        headers = register_headers(client, "ana@example.com", consent=True)
        job_id, url = _signed_status_link(client, headers, tmp_path)
        unsigned = url.split("?")[0]

        assert client.get(url).status_code == 200
        resp = client.get(unsigned)
        assert resp.status_code == 404
        assert resp.json() == {"detail": "Not Found"}


def test_create_app_builds_the_cipher_and_discards_plain_text_tokens(tmp_path, templates_dir):
    from datetime import datetime, timezone

    from image_edit_server.core.identity_verifier import ProviderIdentity
    from image_edit_server.repos.user_store import SqliteUserStore
    from tests.helpers import encoded_test_key, write_apple_key_file

    root = tmp_path / "s"
    root.mkdir()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    seed = SqliteUserStore(str(root / "app.db"))
    user = seed.create_user("ana@example.com", "hash")
    seed.link_identity(user.id, ProviderIdentity("apple", "a-1", "ana@example.com", True, now), now)
    seed._conn.execute("UPDATE identities SET apple_refresh_token = 'legacy-plain'")
    seed._conn.commit()
    seed.close()
    settings = Settings(
        TEMPLATES_DIR=str(templates_dir),
        STORAGE_ROOT=str(root),
        APPLE_BUNDLE_ID="com.example.app",
        APPLE_TEAM_ID="TEAM",
        APPLE_KEY_ID="KEY",
        APPLE_PRIVATE_KEY_PATH=str(write_apple_key_file(tmp_path / "AuthKey.p8")),
        TOKEN_ENCRYPTION_KEY=encoded_test_key(),
    )

    app = create_app(settings)

    assert app is not None
    reopened = SqliteUserStore(str(root / "app.db"))
    assert reopened.list_providers(user.id) == ["apple"]
    assert reopened._conn.execute("SELECT apple_refresh_token FROM identities").fetchone()[0] is None
