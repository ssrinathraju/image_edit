"""End-to-end: submit → poll until succeeded → download image."""
import io
import time

import pytest
from fastapi.testclient import TestClient

from image_edit_server.configs.settings import Settings
from image_edit_server.main import create_app

SMALL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def app_client(tmp_path):
    settings = Settings(STORAGE_ROOT=str(tmp_path))
    app = create_app(settings=settings)
    with TestClient(app) as client:
        yield client


def test_full_generation_flow(app_client):
    # Submit
    resp = app_client.post(
        "/generations",
        data={"prompt": "a family at sunset"},
        files=[("faces", ("face.png", io.BytesIO(SMALL_PNG), "image/png"))],
    )
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # Poll until terminal (StubPipeline is fast)
    for _ in range(40):
        status_resp = app_client.get(f"/generations/{job_id}")
        assert status_resp.status_code == 200
        body = status_resp.json()
        if body["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.1)

    assert body["status"] == "succeeded"
    assert "result_url" in body

    # Download the image
    img_resp = app_client.get(body["result_url"])
    assert img_resp.status_code == 200
    assert img_resp.headers["content-type"].startswith("image/png")
    assert len(img_resp.content) > 0


def test_static_files_serve_png(app_client, tmp_path):
    from pathlib import Path
    from PIL import Image

    # Place a PNG in the outputs dir
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (10, 10), color=(255, 0, 0))
    img.save(out_dir / "foo.png", format="PNG")

    resp = app_client.get("/images/foo.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
