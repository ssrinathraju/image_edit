import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_template_previews.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("generate_template_previews", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def templates_dir(tmp_path):
    entries = [
        {"id": id_, "title": title, "tags": [], "popularity": 10,
         "preview": f"{id_}.webp", "prompt": "p"}
        for id_, title in [("one", "Number One"), ("two", "Number Two")]
    ]
    (tmp_path / "catalog.json").write_text(json.dumps(entries))
    return tmp_path


def test_placeholder_writes_one_webp_per_entry(script, templates_dir):
    written = script.generate_placeholders(templates_dir)
    assert sorted(written) == ["one", "two"]
    for name in ("one", "two"):
        with Image.open(templates_dir / "previews" / f"{name}.webp") as img:
            assert img.format == "WEBP"
            assert img.size == (512, 512)


def test_existing_previews_are_skipped_without_force(script, templates_dir):
    script.generate_placeholders(templates_dir)
    target = templates_dir / "previews" / "one.webp"
    target.write_bytes(b"sentinel")

    assert script.generate_placeholders(templates_dir) == []
    assert target.read_bytes() == b"sentinel"

    assert "one" in script.generate_placeholders(templates_dir, force=True)
    assert target.read_bytes() != b"sentinel"


def test_only_regenerates_a_single_template(script, templates_dir):
    assert script.generate_placeholders(templates_dir, only="two") == ["two"]
    assert not (templates_dir / "previews" / "one.webp").exists()


def test_unknown_only_id_exits(script, templates_dir):
    with pytest.raises(SystemExit):
        script.generate_placeholders(templates_dir, only="nope")
