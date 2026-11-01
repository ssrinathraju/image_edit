from __future__ import annotations

import hashlib
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from image_edit_server.core.user_store import UserStore
from image_edit_server.repos.template_catalog import (
    PREVIEWS_DIRNAME,
    CatalogHolder,
    catalog_from_stored,
    check_stored_previews,
    load_catalog,
)
from image_edit_server.schemas.template import StoredTemplate, Template

logger = logging.getLogger(__name__)

PREVIEW_HASH_CHARS = 12


def hashed_preview_name(template_id: str, content: bytes, suffix: str) -> str:
    """The stored file name for a preview; a new image always gets a new name."""
    digest = hashlib.sha256(content).hexdigest()[:PREVIEW_HASH_CHARS]
    return f"{template_id}-{digest}{suffix}"


def write_preview_file(previews_dir: Path, name: str, content: bytes) -> None:
    """Write via a temporary name so a crash never leaves a half-written preview."""
    previews_dir.mkdir(parents=True, exist_ok=True)
    temp_path = previews_dir / f".{name}.tmp"
    temp_path.write_bytes(content)
    os.replace(temp_path, previews_dir / name)


def seed_templates_if_needed(store: UserStore, seed_dir: Path, previews_dir: Path) -> bool:
    """Import the seed catalog once; returns True when it imported. A bad seed raises CatalogError."""
    if store.are_templates_seeded():
        return False
    seed = load_catalog(seed_dir)
    now = datetime.now(timezone.utc).isoformat()
    rows = [_copy_into_storage(template, seed_dir, previews_dir, now) for template in seed.all()]
    store.import_seed_templates(rows)
    logger.info("Imported %d seed template(s)", len(rows))
    return True


def _copy_into_storage(
    template: Template, seed_dir: Path, previews_dir: Path, now: str
) -> StoredTemplate:
    source = seed_dir / PREVIEWS_DIRNAME / template.preview
    name = hashed_preview_name(template.id, source.read_bytes(), source.suffix)
    previews_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, previews_dir / name)
    return StoredTemplate(
        **{**template.model_dump(exclude={"retired", "updated_at"}), "preview": name},
        retired=False,
        updated_at=now,
    )


def remove_unreferenced_previews(store: UserStore, previews_dir: Path) -> int:
    """Delete files no stored template references (left by a crash); returns how many went."""
    referenced = {row.preview for row in store.list_templates()}
    removed = 0
    for path in previews_dir.iterdir():
        if not path.is_file() or path.name in referenced:
            continue
        try:
            path.unlink()
            removed += 1
        except OSError:
            logger.exception("Could not remove unreferenced preview file %s", path.name)
    return removed


def load_template_catalog(store: UserStore, seed_dir: Path, previews_dir: Path) -> CatalogHolder:
    """Seed if never seeded, check every stored preview exists, sweep strays, build the catalog."""
    seed_templates_if_needed(store, seed_dir, previews_dir)
    rows = store.list_templates()
    previews_dir.mkdir(parents=True, exist_ok=True)
    check_stored_previews(rows, previews_dir)
    remove_unreferenced_previews(store, previews_dir)
    return CatalogHolder(catalog_from_stored(rows))
