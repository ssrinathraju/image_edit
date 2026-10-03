from __future__ import annotations

import shutil
from pathlib import Path

from image_edit_server.configs.settings import Settings


def _settings() -> Settings:
    return Settings()


def input_dir(job_id: str, storage_root: str | None = None) -> Path:
    root = Path(storage_root or _settings().STORAGE_ROOT)
    return root / "inputs" / job_id


def output_path(job_id: str, storage_root: str | None = None) -> Path:
    root = Path(storage_root or _settings().STORAGE_ROOT)
    return root / "outputs" / f"{job_id}.png"


def save_upload(job_id: str, index: int, data: bytes, storage_root: str | None = None) -> Path:
    """Write upload bytes to inputs/<job_id>/face_<index>.jpg and return the path."""
    dest_dir = input_dir(job_id, storage_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"face_{index}.jpg"
    dest.write_bytes(data)
    return dest


def delete_inputs(job_id: str, storage_root: str | None = None) -> None:
    """Remove the entire inputs/<job_id>/ directory if it exists."""
    target = input_dir(job_id, storage_root)
    if target.exists():
        shutil.rmtree(target)
