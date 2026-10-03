import pytest
from fastapi.testclient import TestClient

from image_edit_server.api.generations import get_store, router
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from fastapi import FastAPI


@pytest.fixture
def store() -> InMemoryJobStore:
    return InMemoryJobStore()


@pytest.fixture
def client(store) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_store] = lambda: store
    return TestClient(app)
