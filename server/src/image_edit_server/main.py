from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from image_edit_server.api.generations import get_store, router as generations_router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.configs.settings import Settings
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.template_catalog import load_catalog
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


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    store = InMemoryJobStore()
    templates_dir = Path(cfg.TEMPLATES_DIR)
    catalog = load_catalog(templates_dir)
    pipeline = _make_pipeline(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        outputs_dir = Path(cfg.STORAGE_ROOT) / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        workers = [
            asyncio.create_task(run_worker(store, pipeline, cfg))
            for _ in range(cfg.JOB_CONCURRENCY)
        ]
        yield
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    app = FastAPI(title="image-edit", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
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
