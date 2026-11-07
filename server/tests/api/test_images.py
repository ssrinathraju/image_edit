from datetime import timedelta

import pytest
from PIL import Image
from ulid import ULID

from image_edit_server.core import url_signing
from image_edit_server.repos import file_storage

NOT_FOUND_BODY = {"detail": "Not Found"}


@pytest.fixture
def job_id(settings) -> str:
    """A job id with a real image in outputs/."""
    new_id = str(ULID())
    path = file_storage.output_path(new_id, settings.STORAGE_ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=(255, 0, 0)).save(path, format="PNG")
    return new_id


@pytest.fixture
def link(job_id, clock, result_url_secret):
    def build(for_job=None, exp=None, secret=None):
        target = for_job or job_id
        expires_at = exp if exp is not None else int((clock() + url_signing.RESULT_URL_TTL).timestamp())
        signature = url_signing.sign(target, expires_at, secret or result_url_secret)
        return f"/images/{job_id}.png?exp={expires_at}&sig={signature}"

    return build


def _assert_refused(resp):
    assert resp.status_code == 404
    assert resp.json() == NOT_FOUND_BODY


def test_a_valid_link_returns_the_image(anon_client, link):
    resp = anon_client.get(link())

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["cache-control"] == "private, no-store"
    assert resp.content.startswith(b"\x89PNG")


def test_a_link_without_parameters_is_refused(anon_client, job_id):
    _assert_refused(anon_client.get(f"/images/{job_id}.png"))


def test_a_link_with_only_one_parameter_is_refused(anon_client, job_id, link):
    full = link()
    exp_only = full.split("&sig=")[0]
    sig_only = full.replace(full.split("?")[1].split("&")[0] + "&", "")

    _assert_refused(anon_client.get(exp_only))
    _assert_refused(anon_client.get(sig_only))


def test_an_expired_link_is_refused_though_the_image_remains(anon_client, link, clock):
    url = link()
    clock.advance(minutes=16)

    _assert_refused(anon_client.get(url))


def test_a_link_works_until_just_before_it_expires(anon_client, link, clock):
    url = link()
    clock.advance(minutes=14, seconds=59)

    assert anon_client.get(url).status_code == 200


def test_a_tampered_expiry_is_refused(anon_client, link, clock):
    url = link()
    exp = int(url.split("exp=")[1].split("&")[0])

    _assert_refused(anon_client.get(url.replace(f"exp={exp}", f"exp={exp + 3600}")))


def test_another_jobs_signature_is_refused(anon_client, link):
    _assert_refused(anon_client.get(link(for_job=str(ULID()))))


def test_a_signature_made_with_another_secret_is_refused(anon_client, link):
    _assert_refused(anon_client.get(link(secret=b"x" * 40)))


@pytest.mark.parametrize("exp", ["abc", "-5", "1.5", "", "1" * 13, "１２３"])
def test_a_non_numeric_or_overlong_expiry_is_refused(anon_client, job_id, exp):
    _assert_refused(anon_client.get(f"/images/{job_id}.png", params={"exp": exp, "sig": "x"}))


@pytest.mark.parametrize(
    "bad_id",
    ["..%2F..%2Fapp", "..", "foo", "01hzzzzzzzzzzzzzzzzzzzzzza", "01HZZZZZZZZZZZZZZZZZZZZZZ!", "A" * 27],
)
def test_a_malformed_job_id_is_refused(anon_client, clock, result_url_secret, bad_id):
    exp = int((clock() + timedelta(minutes=5)).timestamp())
    sig = url_signing.sign(bad_id, exp, result_url_secret)

    _assert_refused(anon_client.get(f"/images/{bad_id}.png?exp={exp}&sig={sig}"))


def test_a_valid_link_to_a_swept_image_is_refused(anon_client, link, job_id, settings):
    url = link()
    file_storage.delete_output(job_id, settings.STORAGE_ROOT)

    _assert_refused(anon_client.get(url))


def test_a_valid_link_for_a_job_that_never_had_a_file_is_refused(
    anon_client, clock, result_url_secret
):
    """A content-blocked job is never promoted to outputs/."""
    blocked = str(ULID())
    exp = int((clock() + timedelta(minutes=5)).timestamp())
    sig = url_signing.sign(blocked, exp, result_url_secret)

    _assert_refused(anon_client.get(f"/images/{blocked}.png?exp={exp}&sig={sig}"))


def test_every_refusal_has_the_body_of_an_unknown_route(anon_client):
    assert anon_client.get("/no/such/route").json() == NOT_FOUND_BODY
