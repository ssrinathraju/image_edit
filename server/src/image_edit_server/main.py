from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from image_edit_server.api.auth import router as auth_router
from image_edit_server.api.deps import get_auth_service, get_user_store
from image_edit_server.api.generations import get_store, router as generations_router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.configs.settings import Settings
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.repos.template_catalog import load_catalog
from image_edit_server.services.account_cleanup import purge_user_jobs
from image_edit_server.services.auth_service import AuthService
from image_edit_server.services.template_service import PREVIEW_URL_PREFIX
from image_edit_server.services.worker import run_worker


def _make_pipeline(cfg: Settings) -> GenerationPipeline:
    if cfg.MODEL_BACKEND == "stub":
        from image_edit_server.services.pipelines.stub import StubPipeline
        return StubPipeline()
    if cfg.MODEL_BACKEND == "sana":
        from image_edit_server.services.pipelines.sana import SanaPipeline
        return SanaPipeline(cfg)
    raise ValueError(f"Unknown MODEL_BACKEND: {cfg.MODEL_BACKEND!r}")


def _open_user_store(cfg: Settings) -> SqliteUserStore:
    db_path = Path(cfg.AUTH_DB_PATH or Path(cfg.STORAGE_ROOT) / "app.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteUserStore(str(db_path))


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    store = InMemoryJobStore()
    templates_dir = Path(cfg.TEMPLATES_DIR)
    catalog = load_catalog(templates_dir)
    pipeline = _make_pipeline(cfg)
    user_store = _open_user_store(cfg)
    auth_service = AuthService(
        user_store,
        LoginThrottle(cfg.LOGIN_MAX_FAILURES, timedelta(minutes=cfg.LOGIN_LOCKOUT_MINUTES)),
        cfg,
        lambda user_id: purge_user_jobs(user_id, store, cfg.STORAGE_ROOT),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        outputs_dir = Path(cfg.STORAGE_ROOT) / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        workers = [
            asyncio.create_task(run_worker(
                store,
                pipeline,
                cfg,
                lambda user_id: user_store.get_by_id(user_id) is not None,
            ))
            for _ in range(cfg.JOB_CONCURRENCY)
        ]
        yield
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        user_store.close()

    app = FastAPI(title="image-edit", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.include_router(auth_router)
    app.include_router(generations_router)
    app.include_router(templates_router)

    outputs_dir = Path(cfg.STORAGE_ROOT) / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/images", StaticFiles(directory=str(outputs_dir)), name="images")
    app.mount(
        PREVIEW_URL_PREFIX,
        StaticFiles(directory=str(templates_dir / "previews")),
        name="template-previews",
    )

    return app


app = create_app()
