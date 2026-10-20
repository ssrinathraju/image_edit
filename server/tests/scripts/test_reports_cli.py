import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.repos import file_storage
from image_edit_server.repos.user_store import SqliteUserStore

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reports.py"
NOW = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("reports_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(STORAGE_ROOT=str(tmp_path / "storage"))


@pytest.fixture
def store(settings) -> SqliteUserStore:
    path = Path(settings.STORAGE_ROOT) / "app.db"
    path.parent.mkdir(parents=True)
    return SqliteUserStore(str(path))


@pytest.fixture
def seeded(store, settings):
    user = store.create_user("ana@example.com", "hash")
    file_storage.save_report_image("old.png", b"OLD-IMAGE", settings.STORAGE_ROOT)
    store.add_report("old", user.id, "job-old", "violence", "bad\nnote", "server", "old.png", NOW - timedelta(hours=2), 20)
    store.add_report("new", user.id, "job-new", "hate", "", "none", None, NOW, 20)
    return user


def test_list_shows_open_reports_newest_first(script, settings, seeded, capsys):
    assert script.list_reports(settings) == 0

    lines = capsys.readouterr().out.strip().splitlines()
    assert [line.split()[0] for line in lines] == ["new", "old"]
    assert "violence" in lines[1] and "job=job-old" in lines[1]
    assert "bad note" in lines[1]


def test_list_with_no_reports_says_so(script, settings, store, capsys):
    assert script.list_reports(settings) == 0
    assert "no open reports" in capsys.readouterr().out


def test_show_writes_the_image_to_the_chosen_file(script, settings, seeded, tmp_path, capsys):
    out = tmp_path / "saved.png"

    assert script.show_report("old", str(out), settings) == 0

    assert out.read_bytes() == b"OLD-IMAGE"
    assert "category=violence" in capsys.readouterr().out


def test_show_refuses_to_overwrite_an_existing_file(script, settings, seeded, tmp_path):
    out = tmp_path / "saved.png"
    out.write_bytes(b"mine")

    assert script.show_report("old", str(out), settings) == script.EXIT_BAD_ARGUMENT
    assert out.read_bytes() == b"mine"


def test_show_for_a_report_without_an_image_fails_cleanly(script, settings, seeded, tmp_path):
    assert script.show_report("new", str(tmp_path / "x.png"), settings) == script.EXIT_NO_IMAGE


def test_show_for_an_unknown_id_fails(script, settings, seeded, tmp_path, capsys):
    assert script.show_report("nope", str(tmp_path / "x.png"), settings) == script.EXIT_NOT_FOUND
    assert "no report" in capsys.readouterr().err


def test_resolve_closes_the_report_and_records_the_outcome(script, settings, store, seeded, capsys):
    assert script.resolve_report("old", "removed", settings) == 0

    assert [r.id for r in store.list_open_reports()] == ["new"]
    report = store.get_report("old")
    assert report.outcome == "removed" and report.resolved_at is not None


def test_resolve_twice_or_unknown_fails(script, settings, seeded):
    script.resolve_report("old", "removed", settings)

    assert script.resolve_report("old", "again", settings) == script.EXIT_NOT_FOUND
    assert script.resolve_report("nope", "x", settings) == script.EXIT_NOT_FOUND


def test_resolve_needs_an_outcome(script, settings, seeded):
    assert script.resolve_report("old", "  ", settings) == script.EXIT_BAD_ARGUMENT


def test_a_missing_database_is_reported_without_creating_one(script, tmp_path, capsys):
    empty = Settings(STORAGE_ROOT=str(tmp_path / "nowhere"))

    assert script.list_reports(empty) == script.EXIT_NO_DATABASE
    assert not (tmp_path / "nowhere").exists()
    assert "no database" in capsys.readouterr().err


def test_main_dispatches_the_subcommands(script, settings, seeded, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("IMAGE_EDIT_STORAGE_ROOT", settings.STORAGE_ROOT)
    out = tmp_path / "m.png"

    assert script.main(["list"]) == 0
    assert script.main(["show", "old", "--out", str(out)]) == 0
    assert script.main(["resolve", "old", "--outcome", "kept"]) == 0
    assert out.exists()
