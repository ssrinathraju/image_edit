import asyncio
import logging
from io import BytesIO

import pytest
from fastapi import HTTPException
from PIL import Image

from image_edit_server.services import template_admin_service as admin_service
from image_edit_server.services.template_admin_service import (
    RawTemplateFields,
    TemplateAdminService,
)
from image_edit_server.services.template_seed import load_template_catalog
from tests.helpers import image_bytes

ADMIN = "admin-1"
SECRET_PROMPT = "SECRET PROMPT TEXT zebra"
SECRET_TITLE = "Secret Title Quokka"
SECRET_TAG = "secrettag"


@pytest.fixture
def previews_dir(tmp_path):
    return tmp_path / "storage" / "template-previews"


@pytest.fixture
def holder(user_store, templates_dir, previews_dir):
    return load_template_catalog(user_store, templates_dir, previews_dir)


@pytest.fixture
def service(user_store, holder, safety_service, previews_dir) -> TemplateAdminService:
    return TemplateAdminService(user_store, holder, safety_service, previews_dir)


def _fields(**overrides) -> RawTemplateFields:
    values = dict(
        id="neon-city", title="Neon City", tags="night, City", popularity="60",
        prompt="a neon city at night",
    )
    return RawTemplateFields(**{**values, **overrides})


async def _refused(coro) -> dict:
    with pytest.raises(HTTPException) as caught:
        await coro
    return caught.value.detail | {"status": caught.value.status_code}


def _files(previews_dir) -> set:
    return {p.name for p in previews_dir.iterdir()}


# ── validation ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"id": "Bad Id"}, "id"),
        ({"id": "a" * 65}, "id"),
        ({"id": "double--hyphen"}, "id"),
        ({"title": "   "}, "title"),
        ({"title": "x" * 61}, "title"),
        ({"tags": ",".join(f"t{i}" for i in range(11))}, "tags"),
        ({"tags": "x" * 31}, "tags"),
        ({"popularity": "150"}, "popularity"),
        ({"popularity": "-1"}, "popularity"),
        ({"popularity": "ten"}, "popularity"),
        ({"popularity": "1.5"}, "popularity"),
        ({"popularity": "9" * 5000}, "popularity"),
        ({"prompt": " "}, "prompt"),
        ({"prompt": "p" * 501}, "prompt"),
        ({"title": None}, "title"),
    ],
)
async def test_each_field_limit_is_enforced_and_names_the_field(service, user_store, previews_dir, overrides, field):
    before = len(user_store.list_templates())

    body = await _refused(service.create(ADMIN, _fields(**overrides), image_bytes()))

    assert (body["status"], body["error"], body["field"]) == (400, "invalid_template_field", field)
    assert len(user_store.list_templates()) == before
    assert not any("neon" in name for name in _files(previews_dir))


async def test_limits_accept_the_boundaries(service):
    row = await service.create(
        ADMIN,
        _fields(id="a" * 64, title="t" * 60, popularity="0", prompt="p" * 500,
                tags=",".join(f"{i:02d}" + "x" * 28 for i in range(10))),
        image_bytes(),
    )

    assert (len(row.id), len(row.title), len(row.tags), row.popularity) == (64, 60, 10, 0)


async def test_text_is_trimmed_and_tags_are_lowered_and_deduplicated_in_order(service):
    row = await service.create(
        ADMIN,
        _fields(title="  Neon City ", tags=" Night, city ,NIGHT,, Alpha", prompt="  go  "),
        image_bytes(),
    )

    assert (row.title, row.prompt, row.tags) == ("Neon City", "go", ["night", "city", "alpha"])


async def test_edit_with_eleven_tags_is_refused_and_leaves_the_template(service, user_store):
    await service.create(ADMIN, _fields(), image_bytes())

    body = await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(tags=",".join(f"t{i}" for i in range(11))), None))

    assert body["field"] == "tags"
    assert user_store.get_template("neon-city").tags == ["night", "city"]


async def test_edit_with_no_fields_is_refused(service):
    await service.create(ADMIN, _fields(), image_bytes())

    body = await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(), None))

    assert (body["status"], body["error"]) == (400, "invalid_template_field")


async def test_edit_of_an_unknown_id_is_404(service):
    body = await _refused(service.edit(ADMIN, "nope", RawTemplateFields(title="x"), None))

    assert (body["status"], body["error"]) == (404, "template_not_found")


# ── screening ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"title": "A blockedword place"}, "title"),
        ({"tags": "fine, blockedword"}, "tags"),
        ({"prompt": "make it BLOCKEDWORD now"}, "prompt"),
    ],
)
async def test_blocked_terms_are_refused_with_the_field_and_nothing_is_written(
    service, user_store, previews_dir, overrides, field
):
    body = await _refused(service.create(ADMIN, _fields(**overrides), image_bytes()))

    assert (body["status"], body["error"], body["field"]) == (400, "template_text_blocked", field)
    assert user_store.get_template("neon-city") is None
    assert not any("neon" in name for name in _files(previews_dir))


async def test_a_blocked_term_on_edit_changes_nothing(service, user_store):
    await service.create(ADMIN, _fields(), image_bytes())

    body = await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(tags="blockedword"), None))

    assert body["error"] == "template_text_blocked"
    assert user_store.get_template("neon-city").tags == ["night", "city"]


# ── preview ─────────────────────────────────────────────────────────────────

async def test_a_jpeg_preview_is_stored_as_a_square_512_webp(service, previews_dir):
    row = await service.create(ADMIN, _fields(), image_bytes("JPEG", (1200, 800)))

    with Image.open(previews_dir / row.preview) as stored:
        assert (stored.format, stored.size) == ("WEBP", (512, 512))
    assert row.preview.startswith("neon-city-") and row.preview.endswith(".webp")


async def test_the_crop_is_centred(service, previews_dir):
    wide = Image.new("RGB", (300, 100), (255, 0, 0))
    wide.paste((0, 0, 255), (100, 0, 200, 100))
    out = BytesIO()
    wide.save(out, format="PNG")

    row = await service.create(ADMIN, _fields(), out.getvalue())

    with Image.open(previews_dir / row.preview) as stored:
        assert stored.getpixel((256, 256))[2] > 200
        assert stored.getpixel((5, 256))[2] > 200


async def test_a_missing_preview_on_create_is_refused(service):
    body = await _refused(service.create(ADMIN, _fields(), None))

    assert (body["status"], body["error"]) == (400, "invalid_preview")


@pytest.mark.parametrize(
    "data",
    [
        b"x" * (3 * 1024 * 1024),
        b"this is just text, named preview.png",
        image_bytes("GIF"),
        image_bytes("BMP"),
    ],
    ids=["3mb", "text", "gif", "bmp"],
)
async def test_bad_previews_are_refused_and_nothing_changes(service, user_store, previews_dir, data):
    before = _files(previews_dir)

    body = await _refused(service.create(ADMIN, _fields(), data))

    assert (body["status"], body["error"], body["field"]) == (400, "invalid_preview", "preview")
    assert user_store.get_template("neon-city") is None
    assert _files(previews_dir) == before


async def test_a_decompression_bomb_is_refused(service, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)

    body = await _refused(service.create(ADMIN, _fields(), image_bytes("PNG", (200, 200))))

    assert body["error"] == "invalid_preview"


async def test_an_oversized_preview_on_edit_keeps_the_current_one(service, user_store):
    created = await service.create(ADMIN, _fields(), image_bytes())

    body = await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(), b"x" * (3 * 1024 * 1024)))

    assert body["error"] == "invalid_preview"
    assert user_store.get_template("neon-city").preview == created.preview


async def test_a_replaced_preview_gets_a_new_name_and_the_old_file_is_deleted(service, holder, previews_dir):
    created = await service.create(ADMIN, _fields(), image_bytes("PNG", color=(1, 2, 3)))
    assert (previews_dir / created.preview).is_file()

    edited = await service.edit(ADMIN, "neon-city", RawTemplateFields(), image_bytes("PNG", color=(9, 9, 9)))

    assert edited.preview != created.preview
    assert not (previews_dir / created.preview).exists()
    assert (previews_dir / edited.preview).is_file()
    assert holder.current.get("neon-city").preview == edited.preview


async def test_replacing_a_preview_with_identical_content_keeps_the_file(service, previews_dir):
    data = image_bytes("PNG", color=(1, 2, 3))
    created = await service.create(ADMIN, _fields(), data)

    edited = await service.edit(ADMIN, "neon-city", RawTemplateFields(), data)

    assert edited.preview == created.preview
    assert (previews_dir / edited.preview).is_file()


# ── write order and failure ─────────────────────────────────────────────────

async def test_a_failed_commit_on_create_leaves_no_file_and_no_row(service, user_store, holder, previews_dir, monkeypatch):
    before_files = _files(previews_dir)

    def explode(_template):
        raise RuntimeError("disk full")

    monkeypatch.setattr(user_store, "insert_template", explode)

    body = await _refused(service.create(ADMIN, _fields(), image_bytes()))

    assert (body["status"], body["error"]) == (500, "template_store_failed")
    assert _files(previews_dir) == before_files
    assert user_store.get_template("neon-city") is None
    assert holder.current.get("neon-city") is None


async def test_a_failed_commit_on_edit_keeps_the_old_preview_and_row(service, user_store, previews_dir, monkeypatch):
    created = await service.create(ADMIN, _fields(), image_bytes("PNG", color=(1, 2, 3)))
    before_files = _files(previews_dir)

    def explode(*args):
        raise RuntimeError("disk full")

    monkeypatch.setattr(user_store, "update_template", explode)

    body = await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(title="New"), image_bytes("PNG", color=(7, 7, 7))))

    assert body["status"] == 500
    assert _files(previews_dir) == before_files
    assert user_store.get_template("neon-city").title == "Neon City"
    assert user_store.get_template("neon-city").preview == created.preview


async def test_a_duplicate_id_is_409_and_the_existing_template_is_unchanged(service, user_store):
    created = await service.create(ADMIN, _fields(), image_bytes())

    body = await _refused(service.create(ADMIN, _fields(title="Other"), image_bytes("PNG", color=(5, 5, 5))))

    assert (body["status"], body["error"]) == (409, "template_exists")
    assert user_store.get_template("neon-city") == created


async def test_a_retired_id_still_counts_as_a_duplicate(service):
    await service.create(ADMIN, _fields(), image_bytes())
    await service.retire(ADMIN, "neon-city")

    body = await _refused(service.create(ADMIN, _fields(), image_bytes()))

    assert body["error"] == "template_exists"


# ── retire, restore, listing ────────────────────────────────────────────────

async def test_retire_and_restore_are_idempotent_and_swap_the_catalog(service, holder):
    await service.create(ADMIN, _fields(), image_bytes())

    first = await service.retire(ADMIN, "neon-city")
    second = await service.retire(ADMIN, "neon-city")

    assert first.retired and second.retired
    assert holder.current.get("neon-city") is None

    back = await service.restore(ADMIN, "neon-city")
    again = await service.restore(ADMIN, "neon-city")

    assert not back.retired and not again.retired
    assert holder.current.get("neon-city") is not None
    assert (back.title, back.prompt, back.tags, back.preview) == (first.title, first.prompt, first.tags, first.preview)


async def test_retire_of_an_unknown_id_is_404(service):
    assert (await _refused(service.retire(ADMIN, "nope")))["error"] == "template_not_found"
    assert (await _refused(service.restore(ADMIN, "nope")))["status"] == 404


async def test_list_all_puts_retired_templates_last_in_public_order(service):
    await service.retire(ADMIN, "sunset-beach")

    ids = [t.id for t in service.list_all()]

    assert ids == ["city-night", "mountain-peak", "sunset-beach"]


async def test_two_concurrent_preview_edits_serialise_and_leave_one_consistent_file(service, user_store, previews_dir):
    await service.create(ADMIN, _fields(), image_bytes("PNG", color=(1, 1, 1)))

    await asyncio.gather(
        service.edit(ADMIN, "neon-city", RawTemplateFields(title="A"), image_bytes("PNG", color=(10, 10, 10))),
        service.edit(ADMIN, "neon-city", RawTemplateFields(title="B"), image_bytes("PNG", color=(20, 20, 20))),
    )

    row = user_store.get_template("neon-city")
    neon_files = {n for n in _files(previews_dir) if n.startswith("neon-city-")}
    assert neon_files == {row.preview}
    assert row.title in {"A", "B"}


# ── audit log ───────────────────────────────────────────────────────────────

async def test_log_lines_carry_action_id_and_admin_only(service, caplog):
    caplog.set_level(logging.INFO)
    fields = _fields(title=SECRET_TITLE, tags=SECRET_TAG, prompt=SECRET_PROMPT)

    await service.create(ADMIN, fields, image_bytes())
    await service.edit(ADMIN, "neon-city", RawTemplateFields(prompt=SECRET_PROMPT + " v2", title=SECRET_TITLE + "2"), None)
    await service.retire(ADMIN, "neon-city")
    await service.restore(ADMIN, "neon-city")
    await _refused(service.edit(ADMIN, "neon-city", RawTemplateFields(prompt="blockedword " + SECRET_PROMPT), None))

    lines = [r.getMessage() for r in caplog.records if r.name.endswith("template_admin_service")]
    assert [l.split()[0] + " " + l.split()[1] for l in lines] == [
        "template_admin action=create",
        "template_admin action=edit",
        "template_admin action=retire",
        "template_admin action=restore",
        "template_admin_refused action=edit",
    ]
    assert all("template='neon-city'" in l or "template=neon-city" in l for l in lines)
    assert all(f"admin={ADMIN}" in l for l in lines)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    for secret in ("SECRET", "Quokka", "zebra", SECRET_TAG, "blockedword", "neon city"):
        assert secret not in joined
    assert "fields=title,prompt" in lines[1]


async def test_a_very_long_popularity_is_refused_without_converting_it(service, monkeypatch):
    # Python 3.11+ makes int() raise ValueError on a string of over 4300 digits.
    def limited_int(value):
        if isinstance(value, str) and len(value) > 4300:
            raise ValueError("Exceeds the limit for integer string conversion")
        return int(value)

    monkeypatch.setattr(admin_service, "int", limited_int, raising=False)

    body = await _refused(service.create(ADMIN, _fields(popularity="9" * 5000), image_bytes()))

    assert (body["status"], body["field"]) == (400, "popularity")


async def test_a_failed_catalog_swap_still_returns_the_saved_template(
    service, user_store, holder, monkeypatch, caplog
):
    def broken_replace(catalog):
        raise RuntimeError("swap failed")

    monkeypatch.setattr(holder, "replace", broken_replace)

    row = await service.create(ADMIN, _fields(), image_bytes())

    assert user_store.get_template("neon-city") is not None
    assert row.id == "neon-city"
    assert "catalog refresh failed" in caplog.text


async def test_success_and_refusal_lines_quote_the_id_the_same_way(service, caplog):
    caplog.set_level(logging.INFO)
    await service.create(ADMIN, _fields(), image_bytes())
    await _refused(service.retire(ADMIN, "missing"))

    lines = [r.getMessage() for r in caplog.records if r.name.endswith("template_admin_service")]
    assert "template='neon-city'" in lines[0]
    assert "template='missing'" in lines[1]
