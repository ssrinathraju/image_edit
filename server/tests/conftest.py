from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from image_edit_server.api.generations import get_store, router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.template_catalog import TemplateCatalog, load_catalog
from tests.helpers import build_templates_dir


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
def client(store, catalog) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.include_router(templates_router)
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
    return TestClient(app)
