import asyncio
import io
import threading
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from image_edit_server.api.deps import get_user_store
from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app
from tests.helpers import RecordingSender, image_bytes, register_headers

SMALL_PNG = image_bytes("PNG", (8, 8))
OLD_PROMPT = "OLD PROMPT hat"
NEW_PROMPT = "NEW PROMPT scarf"


class GatedPipeline:
    """Records each prompt it runs and holds jobs open while its gate is closed."""

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.started = threading.Event()
        self.gate = threading.Event()
        self.gate.set()

    async def run(self, faces, prompt, output_path):
        self.prompts.append(prompt)
        self.started.set()
        while not self.gate.is_set():
            await asyncio.sleep(0.01)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16)).save(output_path, format="PNG")
        return output_path


@pytest.fixture
def pipeline(monkeypatch) -> GatedPipeline:
    gated = GatedPipeline()
    monkeypatch.setattr("image_edit_server.main._make_pipeline", lambda cfg: gated)
    return gated


@pytest.fixture
def storage_settings(tmp_path, templates_dir) -> Settings:
    return Settings(
        STORAGE_ROOT=str(tmp_path / "storage"),
        TEMPLATES_DIR=str(templates_dir),
        FREE_DAILY_LIMIT=50,
    )


@pytest.fixture
def http(storage_settings, pipeline):
    with TestClient(create_app(storage_settings, sender=RecordingSender())) as client:
        yield client


@pytest.fixture
def admin(http) -> dict:
    headers = register_headers(http, "ana@example.com", consent=True)
    http.app.dependency_overrides[get_user_store]().set_role("ana@example.com", "admin")
    return headers


@pytest.fixture
def user(http) -> dict:
    return register_headers(http, "ben@example.com", consent=True)


def _new_template_data(**overrides) -> dict:
    data = {
        "id": "neon-city", "title": "Neon City", "tags": "night, city",
        "popularity": "60", "prompt": OLD_PROMPT,
    }
    return {**data, **overrides}


def _preview(data: bytes = None, fmt: str = "PNG"):
    return {"preview": ("preview.png", data or image_bytes(fmt, (900, 600)), "image/png")}


def _create(http, admin, files=None, **overrides):
    return http.post(
        "/admin/templates", data=_new_template_data(**overrides),
        files=files if files is not None else _preview(), headers=admin,
    )


def _generate(http, headers, template_id):
    return http.post(
        "/generations", data={"template_id": template_id}, headers=headers,
        files=[("faces", ("face.png", io.BytesIO(SMALL_PNG), "image/png"))],
    )


def _wait_for(http, headers, job_id, status="succeeded"):
    for _ in range(200):
        body = http.get(f"/generations/{job_id}", headers=headers).json()
        if body["status"] == status:
            return body
        time.sleep(0.02)
    raise AssertionError(f"job never reached {status}: {body}")


def _error(resp) -> str:
    return resp.json()["detail"]["error"]


# ── access ──────────────────────────────────────────────────────────────────

def test_every_endpoint_refuses_signed_out_requests(http):
    calls = [
        http.get("/admin/templates"),
        http.post("/admin/templates", data=_new_template_data(), files=_preview()),
        http.patch("/admin/templates/sunset-beach", data={"title": "x"}),
        http.post("/admin/templates/sunset-beach/retire"),
        http.post("/admin/templates/sunset-beach/restore"),
    ]

    assert [c.status_code for c in calls] == [401] * 5


def test_every_endpoint_refuses_a_non_admin_and_changes_nothing(http, user, admin):
    calls = [
        http.get("/admin/templates", headers=user),
        http.post("/admin/templates", data=_new_template_data(), files=_preview(), headers=user),
        http.patch("/admin/templates/sunset-beach", data={"title": "x"}, headers=user),
        http.post("/admin/templates/sunset-beach/retire", headers=user),
        http.post("/admin/templates/sunset-beach/restore", headers=user),
    ]

    assert [c.status_code for c in calls] == [403] * 5
    assert {_error(c) for c in calls} == {"admin_required"}
    listing = http.get("/admin/templates", headers=admin).json()
    assert [t["id"] for t in listing] == ["sunset-beach", "city-night", "mountain-peak"]
    assert listing[0]["title"] == "Sunset Beach" and not listing[0]["retired"]


# ── listing ─────────────────────────────────────────────────────────────────

def test_admin_listing_has_prompts_and_puts_retired_templates_last(http, admin):
    http.post("/admin/templates/sunset-beach/retire", headers=admin)

    resp = http.get("/admin/templates", headers=admin)

    assert resp.status_code == 200
    items = resp.json()
    assert [t["id"] for t in items] == ["city-night", "mountain-peak", "sunset-beach"]
    assert items[-1]["retired"] is True
    assert all(set(t) == {"id", "title", "tags", "popularity", "prompt", "preview_url", "retired", "updated_at"} for t in items)
    assert items[0]["prompt"] == "TEMPLATE PROMPT city"


def test_public_listing_never_includes_a_prompt(http, admin):
    _create(http, admin)

    resp = http.get("/templates")

    assert "prompt" not in resp.text.lower().replace("preview", "")
    assert OLD_PROMPT not in resp.text


# ── create ──────────────────────────────────────────────────────────────────

def test_create_returns_201_lists_the_template_and_accepts_a_generation(http, admin, user, pipeline):
    resp = _create(http, admin)

    assert resp.status_code == 201
    body = resp.json()
    assert (body["id"], body["retired"], body["tags"], body["prompt"]) == ("neon-city", False, ["night", "city"], OLD_PROMPT)
    public = http.get("/templates").json()
    assert [t["id"] for t in public] == ["sunset-beach", "city-night", "neon-city", "mountain-peak"]
    assert public[2]["tags"] == ["night", "city"]

    job = _generate(http, user, "neon-city")
    assert job.status_code == 202
    _wait_for(http, user, job.json()["job_id"])
    assert pipeline.prompts == [OLD_PROMPT]


def test_created_preview_is_served_as_a_512_webp(http, admin):
    body = _create(http, admin, files=_preview(image_bytes("JPEG", (1200, 800)))).json()

    resp = http.get(body["preview_url"])

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(resp.content)).size == (512, 512)


def test_create_errors(http, admin):
    assert _error(_create(http, admin, popularity="150")) == "invalid_template_field"
    assert _create(http, admin, popularity="150").json()["detail"]["field"] == "popularity"
    assert _error(_create(http, admin, prompt="a nude figure")) == "template_text_blocked"
    assert _error(_create(http, admin, files={})) == "invalid_preview"
    assert _error(_create(http, admin, files=_preview(b"not an image"))) == "invalid_preview"
    assert _error(_create(http, admin, files=_preview(b"x" * (3 * 1024 * 1024)))) == "invalid_preview"
    missing = http.post("/admin/templates", data={"id": "x-y"}, files=_preview(), headers=admin)
    assert (missing.status_code, _error(missing)) == (400, "invalid_template_field")
    assert "neon-city" not in {t["id"] for t in http.get("/admin/templates", headers=admin).json()}


def test_a_very_long_popularity_is_refused_over_http(http, admin):
    resp = _create(http, admin, popularity="9" * 5000)

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_template_field"
    assert resp.json()["detail"]["field"] == "popularity"


def test_duplicate_id_is_409_and_leaves_the_original(http, admin):
    _create(http, admin)

    resp = _create(http, admin, title="Another", files=_preview(image_bytes("PNG", (50, 50), (1, 2, 3))))

    assert (resp.status_code, _error(resp)) == (409, "template_exists")
    listing = {t["id"]: t for t in http.get("/admin/templates", headers=admin).json()}
    assert listing["neon-city"]["title"] == "Neon City"


# ── edit ────────────────────────────────────────────────────────────────────

def test_editing_the_title_only_keeps_everything_else(http, admin):
    created = _create(http, admin).json()

    resp = http.patch("/admin/templates/neon-city", data={"title": "Neon Town"}, headers=admin)

    assert resp.status_code == 200
    public = {t["id"]: t for t in http.get("/templates").json()}["neon-city"]
    assert public["title"] == "Neon Town"
    assert (public["tags"], public["preview_url"]) == (created["tags"], created["preview_url"])
    assert resp.json()["popularity"] == 60 and resp.json()["prompt"] == OLD_PROMPT


def test_edit_errors(http, admin):
    _create(http, admin)

    assert http.patch("/admin/templates/nope", data={"title": "x"}, headers=admin).status_code == 404
    assert _error(http.patch("/admin/templates/nope", data={"title": "x"}, headers=admin)) == "template_not_found"
    no_fields = http.patch("/admin/templates/neon-city", headers=admin)
    assert (no_fields.status_code, _error(no_fields)) == (400, "invalid_template_field")
    too_many = http.patch("/admin/templates/neon-city", data={"tags": ",".join(f"t{i}" for i in range(11))}, headers=admin)
    assert too_many.json()["detail"]["field"] == "tags"
    blocked = http.patch("/admin/templates/neon-city", data={"tags": "nude"}, headers=admin)
    assert (blocked.status_code, _error(blocked)) == (400, "template_text_blocked")
    bad_preview = http.patch("/admin/templates/neon-city", files=_preview(b"junk"), headers=admin)
    assert (bad_preview.status_code, _error(bad_preview)) == (400, "invalid_preview")
    unchanged = {t["id"]: t for t in http.get("/admin/templates", headers=admin).json()}["neon-city"]
    assert (unchanged["tags"], unchanged["prompt"]) == (["night", "city"], OLD_PROMPT)


def test_replacing_a_preview_changes_its_url_and_serves_the_new_image(http, admin):
    created = _create(http, admin, files=_preview(image_bytes("PNG", (600, 600), (255, 0, 0)))).json()

    edited = http.patch(
        "/admin/templates/neon-city", files=_preview(image_bytes("PNG", (600, 600), (0, 0, 255))), headers=admin
    ).json()

    assert edited["preview_url"] != created["preview_url"]
    assert http.get("/templates").json()[2]["preview_url"] == edited["preview_url"]
    new_image = Image.open(io.BytesIO(http.get(edited["preview_url"]).content)).convert("RGB")
    assert new_image.getpixel((256, 256))[2] > 200
    assert http.get(created["preview_url"]).status_code == 404


def test_an_edited_prompt_applies_to_new_jobs_only(http, admin, user, pipeline):
    _create(http, admin)
    pipeline.gate.clear()
    running = _generate(http, user, "neon-city").json()["job_id"]
    assert pipeline.started.wait(5)
    queued = _generate(http, user, "neon-city").json()["job_id"]

    http.patch("/admin/templates/neon-city", data={"prompt": NEW_PROMPT}, headers=admin)
    pipeline.gate.set()
    later = _generate(http, user, "neon-city").json()["job_id"]

    for job_id in (running, queued, later):
        _wait_for(http, user, job_id)
    assert pipeline.prompts == [OLD_PROMPT, OLD_PROMPT, NEW_PROMPT]


# ── retire and restore ──────────────────────────────────────────────────────

def test_a_retired_template_is_hidden_and_new_generations_are_refused(http, admin, user):
    assert http.post("/admin/templates/sunset-beach/retire", headers=admin).status_code == 200

    assert "sunset-beach" not in {t["id"] for t in http.get("/templates").json()}
    assert http.get("/templates", params={"q": "beach"}).json() == []
    resp = _generate(http, user, "sunset-beach")
    assert (resp.status_code, _error(resp)) == (400, "invalid_template")


def test_a_job_running_when_its_template_is_retired_still_succeeds(http, admin, user, pipeline):
    pipeline.gate.clear()
    job_id = _generate(http, user, "sunset-beach").json()["job_id"]
    assert pipeline.started.wait(5)

    http.post("/admin/templates/sunset-beach/retire", headers=admin)
    pipeline.gate.set()

    body = _wait_for(http, user, job_id)
    assert body["status"] == "succeeded"
    assert http.get(body["result_url"]).status_code == 200


def test_retire_then_restore_brings_it_back_unchanged(http, admin):
    before = {t["id"]: t for t in http.get("/admin/templates", headers=admin).json()}["sunset-beach"]
    public_before = http.get("/templates").json()

    retire = http.post("/admin/templates/sunset-beach/retire", headers=admin)
    again = http.post("/admin/templates/sunset-beach/retire", headers=admin)
    restore = http.post("/admin/templates/sunset-beach/restore", headers=admin)
    restore_again = http.post("/admin/templates/sunset-beach/restore", headers=admin)

    assert [retire.json()["retired"], again.json()["retired"]] == [True, True]
    assert [restore.status_code, restore_again.status_code] == [200, 200]
    assert http.get("/templates").json() == public_before
    after = {t["id"]: t for t in http.get("/admin/templates", headers=admin).json()}["sunset-beach"]
    assert {k: v for k, v in after.items() if k != "updated_at"} == {k: v for k, v in before.items() if k != "updated_at"}


def test_retire_and_restore_of_an_unknown_id_are_404(http, admin):
    for action in ("retire", "restore"):
        resp = http.post(f"/admin/templates/nope/{action}", headers=admin)
        assert (resp.status_code, _error(resp)) == (404, "template_not_found")


# ── persistence ─────────────────────────────────────────────────────────────

def test_added_and_retired_templates_survive_a_restart_and_the_seed_stays_ignored(
    storage_settings, pipeline, templates_dir
):
    with TestClient(create_app(storage_settings, sender=RecordingSender())) as first:
        headers = register_headers(first, "ana@example.com")
        first.app.dependency_overrides[get_user_store]().set_role("ana@example.com", "admin")
        assert _create(first, headers).status_code == 201
        first.post("/admin/templates/sunset-beach/retire", headers=headers)
    (templates_dir / "catalog.json").write_text("[]")

    with TestClient(create_app(storage_settings, sender=RecordingSender())) as second:
        ids = [t["id"] for t in second.get("/templates").json()]

    assert ids == ["city-night", "neon-city", "mountain-peak"]
