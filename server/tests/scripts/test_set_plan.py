import importlib.util
import sys
from pathlib import Path

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.repos.user_store import SqliteUserStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "set_plan.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("set_plan", SCRIPT)
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


def test_success_changes_the_plan_and_a_running_store_sees_it(script, settings, running_store):
    assert running_store.get_by_email("ana@example.com").plan == "free"

    code = script.set_plan("Ana@Example.com", "premium", settings)

    assert code == 0
    assert running_store.get_by_email("ana@example.com").plan == "premium"


def test_unknown_email_is_an_error_and_changes_nothing(script, settings, running_store, capsys):
    code = script.set_plan("nobody@example.com", "premium", settings)

    assert code == 1
    assert "no account" in capsys.readouterr().err
    assert running_store.get_by_email("ana@example.com").plan == "free"


def test_unknown_plan_is_an_error(script, settings, running_store, capsys):
    code = script.set_plan("ana@example.com", "gold", settings)

    assert code == 2
    assert "unknown plan" in capsys.readouterr().err
    assert running_store.get_by_email("ana@example.com").plan == "free"


def test_main_parses_arguments(script, settings, running_store, monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_STORAGE_ROOT", settings.STORAGE_ROOT)

    code = script.main(["--email", "ana@example.com", "--plan", "premium"])

    assert code == 0
    assert running_store.get_by_email("ana@example.com").plan == "premium"
