import pytest
from fastapi.testclient import TestClient

from image_edit_server.api.deps import AdminDep


@pytest.fixture
def admin_probe(app):
    @app.get("/_admin-probe")
    def probe(admin: AdminDep) -> dict:
        return {"id": admin.id}

    return app


def test_no_token_gives_401(admin_probe):
    assert TestClient(admin_probe).get("/_admin-probe").status_code == 401


def test_a_user_token_gives_403_admin_required(admin_probe, client):
    resp = client.get("/_admin-probe")

    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "admin_required"


def test_an_admin_token_passes(admin_probe, client, user_store):
    user_store.set_role("ana@example.com", "admin")

    assert client.get("/_admin-probe").status_code == 200


def test_a_role_removed_between_requests_is_refused_on_the_second(admin_probe, client, user_store):
    user_store.set_role("ana@example.com", "admin")
    assert client.get("/_admin-probe").status_code == 200

    user_store.set_role("ana@example.com", "user")

    resp = client.get("/_admin-probe")
    assert resp.status_code == 403
    assert resp.json()["detail"]["error"] == "admin_required"
