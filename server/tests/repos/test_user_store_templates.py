import pytest

from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.repos.user_store_templates import TemplateExistsError
from image_edit_server.schemas.template import StoredTemplate


@pytest.fixture
def db() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


def _template(id_: str = "neon-city", **overrides) -> StoredTemplate:
    fields = dict(
        id=id_,
        title="Neon City",
        tags=["night", "city", "alpha"],
        popularity=60,
        prompt="a neon city",
        preview=f"{id_}-abc123.webp",
        retired=False,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    return StoredTemplate(**{**fields, **overrides})


def test_every_field_round_trips_with_tags_in_order(db):
    original = _template()

    db.insert_template(original)

    assert db.get_template("neon-city") == original
    assert db.get_template("neon-city").tags == ["night", "city", "alpha"]


def test_get_of_an_unknown_id_is_none(db):
    assert db.get_template("nope") is None


def test_duplicate_id_raises(db):
    db.insert_template(_template())

    with pytest.raises(TemplateExistsError):
        db.insert_template(_template(title="Other"))

    assert db.get_template("neon-city").title == "Neon City"


def test_update_changes_only_the_given_columns(db):
    db.insert_template(_template())

    found = db.update_template("neon-city", {"title": "New", "popularity": 5}, "2026-02-02T00:00:00+00:00")

    row = db.get_template("neon-city")
    assert found is True
    assert (row.title, row.popularity, row.updated_at) == ("New", 5, "2026-02-02T00:00:00+00:00")
    assert (row.prompt, row.tags, row.preview) == ("a neon city", ["night", "city", "alpha"], "neon-city-abc123.webp")
    assert db.update_template("nope", {"title": "x"}, "t") is False


def test_update_refuses_unknown_columns(db):
    db.insert_template(_template())

    with pytest.raises(ValueError):
        db.update_template("neon-city", {"retired": 1}, "t")


def test_retired_flag_is_kept_and_listing_includes_retired_rows(db):
    db.insert_template(_template("a-one"))
    db.insert_template(_template("b-two"))

    assert db.set_template_retired("b-two", True, "2026-03-03T00:00:00+00:00") is True

    listed = {t.id: t.retired for t in db.list_templates()}
    assert listed == {"a-one": False, "b-two": True}
    assert db.get_template("b-two").updated_at == "2026-03-03T00:00:00+00:00"
    assert db.set_template_retired("nope", True, "t") is False


def test_seeded_marker_is_set_with_the_import_and_rows_roll_back_together(db):
    assert not db.are_templates_seeded()

    with pytest.raises(TemplateExistsError):
        db.import_seed_templates([_template("a-one"), _template("a-one")])

    assert not db.are_templates_seeded()
    assert db.list_templates() == []

    db.import_seed_templates([_template("a-one"), _template("b-two")])

    assert db.are_templates_seeded()
    assert len(db.list_templates()) == 2
