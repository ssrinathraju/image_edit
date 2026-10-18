SECRET = "do-not-echo-this-secret"


def test_a_missing_field_is_reported_by_location_without_echoing_other_fields(anon_client):
    resp = anon_client.post(
        "/auth/oauth/apple",
        json={"identity_token": SECRET, "authorization_code": SECRET},
    )

    assert resp.status_code == 422
    errors = resp.json()["detail"]
    assert [error["loc"] for error in errors] == [["body", "nonce"]]
    assert all({"input", "ctx"}.isdisjoint(error) for error in errors)
    assert SECRET not in resp.text


def test_a_rejected_delete_body_does_not_echo_the_token_or_the_password(client):
    resp = client.request(
        "DELETE", "/me", json={"password": SECRET, "provider": "google", "token": SECRET}
    )

    assert resp.status_code == 422
    assert SECRET not in resp.text
    assert all({"input", "ctx"}.isdisjoint(error) for error in resp.json()["detail"])


def test_the_response_still_says_what_is_wrong(client):
    resp = client.request("DELETE", "/me", json={})

    assert resp.status_code == 422
    assert resp.json()["detail"][0]["msg"]
