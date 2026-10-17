"""The generations endpoint must use the app's settings, not the environment default."""
import io
from pathlib import Path

from image_edit_server.api.deps import get_settings
from image_edit_server.configs.settings import Settings

PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _face(data: bytes = PNG):
    return ("faces", ("f.png", io.BytesIO(data), "image/png"))


def _default_inputs() -> set:
    """What the CWD-relative default (the bug's destination) currently holds."""
    folder = Path(Settings().STORAGE_ROOT) / "inputs"
    return {p.name for p in folder.iterdir()} if folder.is_dir() else set()


def test_uploads_follow_the_configured_storage_root(client, settings):
    before = _default_inputs()

    resp = client.post("/generations", data={"prompt": "a family"}, files=[_face()])

    job_id = resp.json()["job_id"]
    assert resp.status_code == 202
    assert (Path(settings.STORAGE_ROOT) / "inputs" / job_id / "face_0.jpg").is_file()
    assert _default_inputs() == before


def test_the_face_limit_comes_from_the_apps_settings(app, client, settings):
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"MAX_FACES": 1}
    )

    resp = client.post(
        "/generations", data={"prompt": "a family"}, files=[_face(), _face()]
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_face_count"


def test_the_prompt_limit_comes_from_the_apps_settings(app, client, settings):
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"MAX_PROMPT_CHARS": 5}
    )

    resp = client.post(
        "/generations", data={"prompt": "much longer than five"}, files=[_face()]
    )

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_prompt"


def test_the_upload_size_limit_comes_from_the_apps_settings(app, client, settings):
    app.dependency_overrides[get_settings] = lambda: settings.model_copy(
        update={"MAX_UPLOAD_BYTES": 10}
    )

    resp = client.post("/generations", data={"prompt": "a family"}, files=[_face()])

    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_image"
