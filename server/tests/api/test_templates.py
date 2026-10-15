def test_lists_templates_in_popularity_order(client):
    resp = client.get("/templates")
    assert resp.status_code == 200
    assert [t["id"] for t in resp.json()] == ["sunset-beach", "city-night", "mountain-peak"]


def test_items_have_required_fields(client):
    item = client.get("/templates").json()[0]
    assert set(item) == {"id", "title", "tags", "preview_url"}
    assert item["preview_url"] == "/template-previews/sunset-beach.webp"


def test_q_filters_by_tag_case_insensitively(client):
    resp = client.get("/templates", params={"q": "BEACH"})
    assert [t["id"] for t in resp.json()] == ["sunset-beach"]


def test_blank_q_returns_everything(client):
    assert len(client.get("/templates", params={"q": "  "}).json()) == 3


def test_no_matches_returns_empty_list(client):
    resp = client.get("/templates", params={"q": "zzzz"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_responses_never_contain_prompts(client):
    resp = client.get("/templates")
    assert "TEMPLATE PROMPT" not in resp.text
    assert all("prompt" not in item for item in resp.json())


def test_preview_url_serves_the_image(templates_dir, tmp_path):
    from fastapi.testclient import TestClient

    from image_edit_server.configs.settings import Settings
    from image_edit_server.main import create_app

    app = create_app(Settings(TEMPLATES_DIR=str(templates_dir), STORAGE_ROOT=str(tmp_path / "s")))
    http = TestClient(app)
    preview_url = http.get("/templates").json()[0]["preview_url"]

    resp = http.get(preview_url)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/webp"


def test_templates_stay_public(anon_client):
    assert anon_client.get("/templates").status_code == 200
