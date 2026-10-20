from __future__ import annotations

import os
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


def staging_path(job_id: str, storage_root: str | None = None) -> Path:
    """Where a pipeline writes before the safety check; outside the publicly served outputs/."""
    return _root(storage_root) / "staging" / f"{job_id}.png"


def promote_staged_output(job_id: str, storage_root: str | None = None) -> Path:
    """Atomically move a checked image from staging/ into outputs/ and return its path."""
    destination = output_path(job_id, storage_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging_path(job_id, storage_root), destination)
    return destination


def delete_staged(job_id: str, storage_root: str | None = None) -> None:
    staging_path(job_id, storage_root).unlink(missing_ok=True)


def clear_staging(storage_root: str | None = None) -> int:
    """Delete every file in staging/ (only a crash mid-job leaves any) and return how many."""
    folder = _root(storage_root) / "staging"
    if not folder.is_dir():
        return 0
    removed = 0
    for entry in folder.iterdir():
        if entry.is_file() or entry.is_symlink():
            entry.unlink(missing_ok=True)
            removed += 1
    return removed


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


def _root(storage_root: str | None) -> Path:
    return Path(storage_root or _settings().STORAGE_ROOT)


def list_output_files(storage_root: str | None = None) -> list[Path]:
    """Generated images: regular `*.png` files directly in outputs/, never symlinks."""
    folder = _root(storage_root) / "outputs"
    if not folder.is_dir():
        return []
    return [
        entry
        for entry in folder.iterdir()
        if entry.suffix == ".png" and entry.is_file() and not entry.is_symlink()
    ]


def list_input_job_ids(storage_root: str | None = None) -> list[str]:
    """Job ids that have a reference-face folder: real directories directly in inputs/."""
    folder = _root(storage_root) / "inputs"
    if not folder.is_dir():
        return []
    return [
        entry.name
        for entry in folder.iterdir()
        if entry.is_dir() and not entry.is_symlink()
    ]


def delete_output(job_id: str, storage_root: str | None = None) -> None:
    """Remove outputs/<job_id>.png if it exists."""
    output_path(job_id, storage_root).unlink(missing_ok=True)


def report_image_path(image_name: str, storage_root: str | None = None) -> Path:
    return _root(storage_root) / "reports" / image_name


def copy_output_to_report(job_id: str, image_name: str, storage_root: str | None = None) -> None:
    """Copy outputs/<job_id>.png into reports/; raises FileNotFoundError when the output is gone."""
    destination = report_image_path(image_name, storage_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(output_path(job_id, storage_root), destination)


def save_report_image(image_name: str, data: bytes, storage_root: str | None = None) -> None:
    destination = report_image_path(image_name, storage_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)


def delete_report_image(image_name: str, storage_root: str | None = None) -> None:
    report_image_path(image_name, storage_root).unlink(missing_ok=True)


def list_report_image_files(storage_root: str | None = None) -> list[Path]:
    """Regular files directly in reports/, never symlinks."""
    folder = _root(storage_root) / "reports"
    if not folder.is_dir():
        return []
    return [entry for entry in folder.iterdir() if entry.is_file() and not entry.is_symlink()]
