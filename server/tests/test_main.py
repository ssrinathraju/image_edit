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

    from tests.helpers import register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))

    with TestClient(create_app(settings)) as first:
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
    from tests.helpers import register_headers

    settings = Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s"))
    with TestClient(create_app(settings)) as first:
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
