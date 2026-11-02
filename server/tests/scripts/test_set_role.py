import importlib.util
import sys
from pathlib import Path

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.repos.user_store import SqliteUserStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "set_role.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("set_role", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(STORAGE_ROOT=str(tmp_path))


@pytest.fixture
def running_store(settings) -> SqliteUserStore:
    """The server's own connection, opened before the script runs."""
    store = SqliteUserStore(str(Path(settings.STORAGE_ROOT) / "app.db"))
    store.create_user("ana@example.com", "hash")
    return store


def test_granting_and_removing_the_role_is_seen_by_a_running_store(script, settings, running_store):
    assert running_store.get_by_email("ana@example.com").role == "user"

    assert script.set_role("Ana@Example.com", "admin", settings) == 0
    assert running_store.get_by_email("ana@example.com").role == "admin"

    assert script.set_role("ana@example.com", "user", settings) == 0
    assert running_store.get_by_email("ana@example.com").role == "user"


def test_unknown_email_is_an_error_and_changes_nothing(script, settings, running_store, capsys):
    code = script.set_role("nobody@example.com", "admin", settings)

    assert code == 1
    assert "no account" in capsys.readouterr().err
    assert running_store.get_by_email("ana@example.com").role == "user"


def test_a_missing_database_is_refused_and_not_created(script, tmp_path, capsys):
    settings = Settings(STORAGE_ROOT=str(tmp_path / "elsewhere"))

    code = script.set_role("ana@example.com", "admin", settings)

    assert code == 3
    assert "no database at" in capsys.readouterr().err
    assert not (tmp_path / "elsewhere").exists()


def test_an_invalid_role_is_refused(script, settings, running_store, capsys):
    code = script.set_role("ana@example.com", "root", settings)

    assert code == 2
    assert "unknown role" in capsys.readouterr().err
    assert running_store.get_by_email("ana@example.com").role == "user"


def test_output_never_contains_the_email(script, settings, running_store, capsys):
    script.set_role("ana@example.com", "admin", settings)
    script.set_role("nobody@example.com", "admin", settings)
    script.set_role("ana@example.com", "root", settings)

    captured = capsys.readouterr()
    assert "ana@example.com" not in captured.out + captured.err
    assert "nobody@example.com" not in captured.out + captured.err


def test_main_parses_arguments(script, settings, running_store, monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_STORAGE_ROOT", settings.STORAGE_ROOT)

    assert script.main(["--email", "ana@example.com", "--role", "admin"]) == 0
    assert running_store.get_by_email("ana@example.com").role == "admin"
