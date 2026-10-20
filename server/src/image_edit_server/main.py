from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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
from image_edit_server.api.generations import get_store, router as generations_router
from image_edit_server.api.templates import get_catalog, router as templates_router
from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_sender import EmailSender
from image_edit_server.core.identity_verifier import IdentityVerifier
from image_edit_server.core.pipeline import GenerationPipeline
from image_edit_server.core.login_throttle import LoginThrottle
from image_edit_server.core.safety import ImageClassifier, TermMatcher, load_terms
from image_edit_server.repos.in_memory_job_store import InMemoryJobStore
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path
from image_edit_server.repos.template_catalog import load_catalog
from image_edit_server.services.account_cleanup import purge_user_jobs
from image_edit_server.services.apple_revocation import AppleRevocationClient
from image_edit_server.services.auth_service import AuthService
from image_edit_server.services.email.log_sender import LogSender
from image_edit_server.services.email.smtp_sender import SmtpSender
from image_edit_server.services.identity.apple_verifier import AppleVerifier
from image_edit_server.services.identity.google_verifier import GoogleVerifier
from image_edit_server.services.quota_service import QuotaService
from image_edit_server.services.referral_service import ReferralService
from image_edit_server.services.safety.local_classifier import LocalImageClassifier
from image_edit_server.services.safety.safety_service import SafetyService
from image_edit_server.services.safety.stub_classifier import StubClassifier
from image_edit_server.services.retention_service import run_retention, sweep
from image_edit_server.services.template_service import PREVIEW_URL_PREFIX
from image_edit_server.services.worker import run_worker

logger = logging.getLogger(__name__)


def _make_pipeline(cfg: Settings) -> GenerationPipeline:
    if cfg.MODEL_BACKEND == "stub":
        from image_edit_server.services.pipelines.stub import StubPipeline
        return StubPipeline()
    if cfg.MODEL_BACKEND == "sana":
        from image_edit_server.services.pipelines.sana import SanaPipeline
        return SanaPipeline(cfg)
    raise ValueError(f"Unknown MODEL_BACKEND: {cfg.MODEL_BACKEND!r}")


def _make_classifiers(cfg: Settings) -> tuple[ImageClassifier, ImageClassifier]:
    """Return the (upload, output) classifiers; a real backend must load the real model."""
    if cfg.MODEL_BACKEND == "stub":
        return (
            StubClassifier(flag=cfg.SAFETY_STUB_FLAG == "all"),
            StubClassifier(flag=cfg.SAFETY_STUB_FLAG in ("outputs", "all")),
        )
    try:
        shared = LocalImageClassifier(cfg.SAFETY_MODEL_ID, cfg.SAFETY_DEVICE)
    except Exception as error:
        logger.exception("Image classifier %r failed to load", cfg.SAFETY_MODEL_ID)
        raise RuntimeError(
            f"image classifier could not be loaded ({cfg.SAFETY_MODEL_ID!r}): {error}; "
            "install the `ml` dependency group and pre-fetch the model"
        ) from error
    return shared, shared


def _make_email_sender(cfg: Settings) -> EmailSender:
    if cfg.SMTP_HOST:
        return SmtpSender(cfg)
    logger.warning(
        "IMAGE_EDIT_SMTP_HOST is not set: emails are NOT delivered, codes are written to the log"
    )
    return LogSender()


def _make_verifiers(cfg: Settings) -> dict[str, IdentityVerifier]:
    verifiers: dict[str, IdentityVerifier] = {}
    if cfg.is_google_configured():
        verifiers["google"] = GoogleVerifier(cfg.GOOGLE_CLIENT_IDS)
    if cfg.is_apple_configured():
        verifiers["apple"] = AppleVerifier(cfg.APPLE_BUNDLE_ID)
    return verifiers


def _make_apple_client(cfg: Settings) -> Optional[AppleRevocationClient]:
    if cfg.is_apple_revocation_configured():
        return AppleRevocationClient(cfg)
    if cfg.is_apple_configured():
        logger.warning(
            "Apple key settings are not set: Apple tokens will not be revoked when accounts are deleted"
        )
    return None


def _open_user_store(cfg: Settings) -> SqliteUserStore:
    db_path = Path(auth_db_path(cfg))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteUserStore(str(db_path))


def create_app(
    settings: Settings | None = None,
    sender: EmailSender | None = None,
    verifiers: dict[str, IdentityVerifier] | None = None,
    apple_client: AppleRevocationClient | None = None,
) -> FastAPI:
    """Build the app; `verifiers` and `apple_client` replace the real provider clients in tests."""
    cfg = settings or Settings()
    email_sender = sender or _make_email_sender(cfg)
    store = InMemoryJobStore()
    templates_dir = Path(cfg.TEMPLATES_DIR)
    catalog = load_catalog(templates_dir)
    upload_classifier, output_classifier = _make_classifiers(cfg)
    pipeline = _make_pipeline(cfg)
    user_store = _open_user_store(cfg)
    auth_service = AuthService(
        user_store,
        LoginThrottle(cfg.LOGIN_MAX_FAILURES, timedelta(minutes=cfg.LOGIN_LOCKOUT_MINUTES)),
        cfg,
        lambda user_id: purge_user_jobs(user_id, store, cfg.STORAGE_ROOT),
        email_sender,
        verifiers=verifiers if verifiers is not None else _make_verifiers(cfg),
        apple_client=apple_client or _make_apple_client(cfg),
    )

    quota_service = QuotaService(user_store, cfg)
    safety_service = SafetyService(
        cfg,
        user_store,
        TermMatcher(load_terms(cfg.SAFETY_TERMS_FILE)),
        upload_classifier,
        output_classifier,
    )
    referral_service = ReferralService(cfg, user_store)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        outputs_dir = Path(cfg.STORAGE_ROOT) / "outputs"
        outputs_dir.mkdir(parents=True, exist_ok=True)

        # Jobs are in memory, so none survived the restart; give their
        # generations back before the first request is served.
        interrupted = quota_service.refund_interrupted()
        if interrupted:
            logger.info("Refunded %d interrupted generation(s)", interrupted)

        # Deletes images past their retention and faces left by a lost run, so
        # nothing stale is served. A failure must not stop the server starting;
        # the periodic task retries.
        try:
            await sweep(store, cfg, datetime.now(timezone.utc))
        except Exception:
            logger.exception("Startup retention sweep failed")

        try:
            user_store.prune_email_rows(datetime.now(timezone.utc))
        except Exception:
            logger.exception("Startup pruning of email-keyed rows failed")

        workers = [
            asyncio.create_task(run_worker(
                store,
                pipeline,
                cfg,
                lambda user_id: user_store.get_by_id(user_id) is not None,
                quota_service.release,
                quota_service.settle,
            ))
            for _ in range(cfg.JOB_CONCURRENCY)
        ]
        retention = asyncio.create_task(run_retention(store, cfg))
        yield
        for w in [*workers, retention]:
            w.cancel()
        await asyncio.gather(*workers, retention, return_exceptions=True)
        user_store.close()

    app = FastAPI(title="image-edit", version="0.1.0", lifespan=lifespan)
    install_validation_error_handler(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.dependency_overrides[get_settings] = lambda: cfg
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_catalog] = lambda: catalog
    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_quota_service] = lambda: quota_service
    app.dependency_overrides[get_safety_service] = lambda: safety_service
    app.dependency_overrides[get_referral_service] = lambda: referral_service
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

