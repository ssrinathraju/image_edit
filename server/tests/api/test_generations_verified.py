from tests.api.test_generations_submit import SMALL_PNG, VALID_PROMPT, _face


def _submit(client):
    return client.post(
        "/generations", data={"prompt": VALID_PROMPT}, files=[_face()]
    )


def test_unverified_valid_request_is_403_with_no_job_and_no_quota_used(unverified_client, store):
    before = unverified_client.get("/me").json()["usage"]["remaining"]

    resp = _submit(unverified_client)

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "email_not_verified"
    assert store.list_for_user(unverified_client.get("/me").json()["id"]) == []
    assert unverified_client.get("/me").json()["usage"]["remaining"] == before


def test_unverified_empty_request_is_403_not_400(unverified_client):
    resp = unverified_client.post("/generations")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "email_not_verified"


def test_submit_succeeds_after_verifying(unverified_client, user_store):
    assert _submit(unverified_client).status_code == 403

    user_store.mark_email_verified(unverified_client.get("/me").json()["id"], 0, 0)

    resp = _submit(unverified_client)
    assert resp.status_code == 202
    assert resp.json()["job_id"]


def test_unverified_account_can_still_read_a_job_made_while_verified(client, user_store, user_id):
    job_id = _submit(client).json()["job_id"]
    user_store._conn.execute("UPDATE users SET email_verified = 0 WHERE id = ?", (user_id,))
    user_store._conn.commit()

    resp = client.get(f"/generations/{job_id}")

    assert resp.status_code == 200
    assert resp.json()["job_id"] == job_id
