import io
import pytest

VALID_PROMPT = "a family hiking in the Alps at sunset"
SMALL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _face(content_type: str = "image/png", data: bytes = SMALL_PNG):
    return ("faces", (f"face.png", io.BytesIO(data), content_type))


def test_happy_path_returns_202_with_job_id(client):
    resp = client.post(
        "/generations",
        data={"prompt": VALID_PROMPT},
        files=[_face(), _face()],
    )
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["job_id"]


def test_zero_faces_returns_400(client):
    resp = client.post("/generations", data={"prompt": VALID_PROMPT}, files=[])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_face_count"


def test_five_faces_returns_400(client):
    resp = client.post(
        "/generations",
        data={"prompt": VALID_PROMPT},
        files=[_face()] * 5,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_face_count"


def test_non_image_mime_returns_400(client):
    resp = client.post(
        "/generations",
        data={"prompt": VALID_PROMPT},
        files=[_face(content_type="text/plain")],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_image"


def test_oversized_upload_returns_400(client):
    big_data = b"x" * (10 * 1024 * 1024 + 1)
    resp = client.post(
        "/generations",
        data={"prompt": VALID_PROMPT},
        files=[_face(data=big_data)],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_image"


def test_empty_prompt_returns_400(client):
    resp = client.post("/generations", data={"prompt": "   "}, files=[_face()])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_prompt"


def test_overlong_prompt_returns_400(client):
    resp = client.post(
        "/generations",
        data={"prompt": "x" * 501},
        files=[_face()],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_prompt"


def test_template_submission_uses_the_template_prompt(client, store):
    resp = client.post(
        "/generations",
        data={"template_id": "sunset-beach"},
        files=[_face()],
    )
    assert resp.status_code == 202
    job = store.get(resp.json()["job_id"])
    assert job.prompt == "TEMPLATE PROMPT sunset beach"
    assert job.template_id == "sunset-beach"


def test_unknown_template_id_returns_400(client, store):
    resp = client.post(
        "/generations",
        data={"template_id": "does-not-exist"},
        files=[_face()],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_template"
    assert list(store.list_queued()) == []


def test_prompt_and_template_together_return_400(client, store):
    resp = client.post(
        "/generations",
        data={"prompt": VALID_PROMPT, "template_id": "sunset-beach"},
        files=[_face()],
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_template"
    assert list(store.list_queued()) == []


def test_neither_prompt_nor_template_returns_invalid_prompt(client):
    resp = client.post("/generations", files=[_face()])
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_prompt"


def test_submit_without_token_is_401_and_creates_no_job(anon_client, store):
    resp = anon_client.post(
        "/generations", data={"prompt": VALID_PROMPT}, files=[_face()]
    )

    assert resp.status_code == 401
    assert resp.json()["detail"]["error"] == "unauthorized"
    assert list(store.list_queued()) == []


def test_submitted_job_is_owned_by_the_caller(client, store, user_id):
    resp = client.post("/generations", data={"prompt": VALID_PROMPT}, files=[_face()])

    assert store.get(resp.json()["job_id"]).user_id == user_id
