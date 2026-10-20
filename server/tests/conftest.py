from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from image_edit_server.api.auth import router as auth_router
from image_edit_server.api.deps import (
    get_auth_service,
    get_quota_service,
    get_referral_service,
    get_safety_service,
    get_settings,
    get_user_store,
)
from image_edit_server.api.errors import install_validation_error_handler
from image_edit_server.api.generations import get_store, router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.configs.settings import Settings
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.core.safety import TermMatcher
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.template_catalog import TemplateCatalog, load_catalog
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services.auth_service import AuthService
from image_edit_server.services.quota_service import QuotaService
from image_edit_server.services.referral_service import ReferralService
from image_edit_server.services.safety.safety_service import SafetyService
from tests.helpers import (
    FakeAppleClient,
    FakeClassifier,
    FakeClock,
    FakeVerifier,
    RecordingSender,
    build_templates_dir,
    register_headers,
)


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
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def google_verifier(clock) -> FakeVerifier:
    return FakeVerifier("google", clock)


@pytest.fixture
def apple_verifier(clock) -> FakeVerifier:
    return FakeVerifier("apple", clock)


@pytest.fixture
def apple_client() -> FakeAppleClient:
    return FakeAppleClient()


@pytest.fixture
def verifiers(google_verifier, apple_verifier) -> dict:
    """The configured providers; a test removes an entry to make it unconfigured."""
    return {"google": google_verifier, "apple": apple_verifier}


@pytest.fixture
def user_store() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def settings(tmp_path, templates_dir) -> Settings:
    """The app's configuration, rooted in the test's temp dir so nothing lands in ./storage."""
    return Settings(
        STORAGE_ROOT=str(tmp_path / "storage"), TEMPLATES_DIR=str(templates_dir)
    )


@pytest.fixture
def upload_classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def output_classifier() -> FakeClassifier:
    return FakeClassifier()


@pytest.fixture
def safety_service(settings, user_store, upload_classifier, output_classifier) -> SafetyService:
    return SafetyService(
        settings,
        user_store,
        TermMatcher(["nude", "blockedword"]),
        upload_classifier,
        output_classifier,
    )


@pytest.fixture
def app(
    store, catalog, user_store, settings, sender, clock, verifiers, apple_client, safety_service
) -> FastAPI:
    throttle = LoginThrottle(
        settings.LOGIN_MAX_FAILURES, timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    )
    auth_service = AuthService(
        user_store,
        throttle,
        settings,
        lambda user_id: [store.delete(j.id) for j in store.list_for_user(user_id)],
        sender,
        clock,
        verifiers=verifiers,
        apple_client=apple_client,
    )
    app = FastAPI()
    install_validation_error_handler(app)
    quota_service = QuotaService(user_store, settings)
    app.include_router(router)
    app.include_router(templates_router)
    app.include_router(auth_router)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_quota_service] = lambda: quota_service
    app.dependency_overrides[get_safety_service] = lambda: safety_service
    app.dependency_overrides[get_referral_service] = lambda: ReferralService(settings, user_store, clock)
    return app


@pytest.fixture
def anon_client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture
def unconsented_client(app) -> TestClient:
    """A client signed in as ana@example.com, age-confirmed but without face-photo consent."""
    test_client = TestClient(app)
    test_client.headers.update(register_headers(test_client, "ana@example.com"))
    return test_client


@pytest.fixture
def client(unconsented_client, settings) -> TestClient:
    """A client signed in as ana@example.com, age-confirmed and consenting to the current version."""
    resp = unconsented_client.post(
        "/me/consent", json={"version": settings.CONSENT_VERSION}
    )
    assert resp.status_code == 200, resp.text
    return unconsented_client


@pytest.fixture
def user_id(client) -> str:
    return client.get("/me").json()["id"]


@pytest.fixture
def second_user_headers(anon_client) -> dict:
    return register_headers(anon_client, "ben@example.com")
