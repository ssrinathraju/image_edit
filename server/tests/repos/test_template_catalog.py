import json
from pathlib import Path

import pytest

from image_edit_server.repos.template_catalog import CatalogError, load_catalog


def _entry(id_: str, title: str, popularity: int, tags=None) -> dict:
    return {
        "id": id_,
        "title": title,
        "tags": tags or [],
        "popularity": popularity,
        "preview": f"{id_}.webp",
        "prompt": f"prompt for {title}",
    }


def _write_catalog(root: Path, entries: list[dict], with_previews: bool = True) -> Path:
    (root / "previews").mkdir(parents=True, exist_ok=True)
    (root / "catalog.json").write_text(json.dumps(entries))
    if with_previews:
        for e in entries:
            (root / "previews" / e["preview"]).write_bytes(b"x")
    return root


@pytest.fixture
def catalog(tmp_path):
    entries = [
        _entry("alpha", "Alpha", 50, ["beach"]),
        _entry("bravo", "Bravo", 90, ["city", "Night"]),
        _entry("charlie", "Charlie", 70, ["mountain"]),
        _entry("able", "Able", 50),
    ]
    return load_catalog(_write_catalog(tmp_path, entries))


def test_orders_by_popularity_desc_then_title(catalog):
    assert [t.id for t in catalog.all()] == ["bravo", "charlie", "able", "alpha"]


def test_search_matches_title_case_insensitively(catalog):
    assert [t.id for t in catalog.search("CHARL")] == ["charlie"]


def test_search_matches_tag_case_insensitively(catalog):
    assert [t.id for t in catalog.search("night")] == ["bravo"]
    assert [t.id for t in catalog.search("BEACH")] == ["alpha"]


def test_blank_query_returns_everything(catalog):
    assert len(catalog.search("")) == 4
    assert len(catalog.search("   ")) == 4
    assert len(catalog.search(None)) == 4


def test_search_with_no_matches_is_empty(catalog):
    assert catalog.search("zzzz") == []


def test_get_returns_template_or_none(catalog):
    assert catalog.get("bravo").title == "Bravo"
    assert catalog.get("missing") is None


def test_duplicate_id_names_the_id(tmp_path):
    entries = [_entry("dup", "One", 1), _entry("dup", "Two", 2)]
    root = _write_catalog(tmp_path, entries)
    with pytest.raises(CatalogError, match="dup"):
        load_catalog(root)


def test_missing_preview_names_template_and_file(tmp_path):
    root = _write_catalog(tmp_path, [_entry("alpha", "Alpha", 1)], with_previews=False)
    with pytest.raises(CatalogError, match="alpha.*alpha.webp"):
        load_catalog(root)


def test_malformed_json_is_reported(tmp_path):
    (tmp_path / "catalog.json").write_text("{not json")
    with pytest.raises(CatalogError, match="not valid JSON"):
        load_catalog(tmp_path)


def test_non_array_catalog_is_reported(tmp_path):
    (tmp_path / "catalog.json").write_text("{}")
    with pytest.raises(CatalogError, match="array"):
        load_catalog(tmp_path)


def test_invalid_entry_names_the_id(tmp_path):
    bad = _entry("Bad Id", "Bad", 1)
    root = _write_catalog(tmp_path, [bad], with_previews=False)
    with pytest.raises(CatalogError, match="Bad Id"):
        load_catalog(root)


def test_missing_catalog_file_is_reported(tmp_path):
    with pytest.raises(CatalogError, match="not found"):
        load_catalog(tmp_path)


# ── catalog built from stored rows ──────────────────────────────────────────

from image_edit_server.repos.template_catalog import (  # noqa: E402
    CatalogHolder,
    catalog_from_stored,
    check_stored_previews,
)
from image_edit_server.schemas.template import StoredTemplate  # noqa: E402


def _stored(id_: str, popularity: int, retired: bool = False) -> StoredTemplate:
    return StoredTemplate(
        id=id_, title=id_.title(), tags=["x"], popularity=popularity,
        preview=f"{id_}-aaa.webp", prompt="p", retired=retired, updated_at="t",
    )


def test_stored_catalog_leaves_out_retired_templates_and_keeps_the_order():
    rows = [_stored("low", 10), _stored("gone", 99, retired=True), _stored("high", 80)]

    catalog = catalog_from_stored(rows)

    assert [t.id for t in catalog.all()] == ["high", "low"]
    assert catalog.get("gone") is None
    assert catalog.search("gone") == []


def test_holder_swaps_the_whole_catalog():
    holder = CatalogHolder(catalog_from_stored([_stored("one", 1)]))
    old = holder.current

    holder.replace(catalog_from_stored([_stored("two", 2)]))

    assert [t.id for t in old.all()] == ["one"]
    assert [t.id for t in holder.current.all()] == ["two"]


def test_a_stored_row_with_a_missing_preview_names_the_id(tmp_path):
    (tmp_path / "ok-aaa.webp").write_bytes(b"x")

    with pytest.raises(CatalogError, match="'lost'"):
        check_stored_previews([_stored("ok", 1), _stored("lost", 2)], tmp_path)
