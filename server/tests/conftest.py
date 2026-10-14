from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from image_edit_server.api.auth import router as auth_router
from image_edit_server.api.deps import get_auth_service, get_user_store
from image_edit_server.api.generations import get_store, router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.template_catalog import TemplateCatalog, load_catalog
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services.auth_service import AuthService
from tests.helpers import build_templates_dir, register_headers


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch):
    """Keep registration cheap in tests; verify still honours stored iterations."""
    monkeypatch.setattr("image_edit_server.core.passwords.PBKDF2_ITERATIONS", 1_000)


@pytest.fixture
def templates_dir(tmp_path) -> Path:
    return build_templates_dir(tmp_path / "templates")


@pytest.fixture
def catalog(templates_dir) -> TemplateCatalog:
    return load_catalog(templates_dir)


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()


@pytest.fixture
def user_store() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def app(store, catalog, user_store) -> FastAPI:
    settings = Settings()
    throttle = LoginThrottle(
        settings.LOGIN_MAX_FAILURES, timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    )
    auth_service = AuthService(
        user_store,
        throttle,
        settings,
        lambda user_id: [store.delete(j.id) for j in store.list_for_user(user_id)],
    )
    app = FastAPI()
    app.include_router(router)
    app.include_router(templates_router)
    app.include_router(auth_router)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    return app


@pytest.fixture
def anon_client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def client(app) -> TestClient:
    """A client already signed in as ana@example.com."""
    test_client = TestClient(app)
    test_client.headers.update(register_headers(test_client, "ana@example.com"))
    return test_client


@pytest.fixture
def user_id(client) -> str:
    return client.get("/me").json()["id"]


@pytest.fixture
def second_user_headers(anon_client) -> dict:
    return register_headers(anon_client, "ben@example.com")
