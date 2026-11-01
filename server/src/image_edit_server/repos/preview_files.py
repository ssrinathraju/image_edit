from __future__ import annotations

import logging
import os
from pathlib import Path

from image_edit_server.core.user_store import UserStore

logger = logging.getLogger(__name__)


def write_preview_file(previews_dir: Path, name: str, content: bytes) -> None:
    """Write via a temporary name so a crash never leaves a half-written preview."""
    previews_dir.mkdir(parents=True, exist_ok=True)
    temp_path = previews_dir / f".{name}.tmp"
    temp_path.write_bytes(content)
    os.replace(temp_path, previews_dir / name)


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
