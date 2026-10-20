"""Review user reports (operator tooling; there is no public endpoint).

Run from server/:
    uv run python scripts/reports.py list
    uv run python scripts/reports.py show REPORT_ID --out image.png
    uv run python scripts/reports.py resolve REPORT_ID --outcome removed
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from image_edit_server.configs.settings import Settings
from image_edit_server.repos import file_storage
from image_edit_server.repos.user_store import SqliteUserStore, auth_db_path

NOTE_PREVIEW_CHARS = 60
EXIT_NOT_FOUND = 1
EXIT_BAD_ARGUMENT = 2
EXIT_NO_DATABASE = 3
EXIT_NO_IMAGE = 4


def _open_store(settings: Settings) -> Optional[SqliteUserStore]:
    db_path = Path(auth_db_path(settings)).resolve()
    if not db_path.is_file():
        # The store would happily create and migrate an empty database here.
        print(
            f"no database at {db_path}; run from the server's directory or set "
            "IMAGE_EDIT_STORAGE_ROOT / IMAGE_EDIT_AUTH_DB_PATH",
            file=sys.stderr,
        )
        return None
    return SqliteUserStore(str(db_path))


def _one_line(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= NOTE_PREVIEW_CHARS else flat[: NOTE_PREVIEW_CHARS - 1] + "…"


def list_reports(settings: Optional[Settings] = None) -> int:
    """Print the open reports, newest first."""
    settings = settings or Settings()
    store = _open_store(settings)
    if store is None:
        return EXIT_NO_DATABASE
    try:
        reports = store.list_open_reports()
    finally:
        store.close()
    if not reports:
        print("no open reports")
        return 0
    for report in reports:
        print(
            f"{report.id}  {report.created_at.isoformat()}  {report.category:<8}"
            f" {report.image_source:<6} job={report.job_id}  {_one_line(report.note)}"
        )
    return 0


def show_report(report_id: str, out: str, settings: Optional[Settings] = None) -> int:
    """Write the report's image to `out` and print its details."""
    settings = settings or Settings()
    store = _open_store(settings)
    if store is None:
        return EXIT_NO_DATABASE
    try:
        report = store.get_report(report_id)
    finally:
        store.close()
    if report is None:
        print(f"no report {report_id!r}", file=sys.stderr)
        return EXIT_NOT_FOUND
    destination = Path(out)
    if destination.exists():
        print(f"{destination} already exists; choose a new file", file=sys.stderr)
        return EXIT_BAD_ARGUMENT
    source = file_storage.report_image_path(report.image_name or "", settings.STORAGE_ROOT)
    if report.image_name is None or not source.is_file():
        print(f"report {report_id} has no image to save", file=sys.stderr)
        return EXIT_NO_IMAGE
    shutil.copyfile(source, destination)
    print(f"saved {report.image_source} image to {destination}")
    print(f"category={report.category} job={report.job_id} reporter={report.reporter_id}")
    print(f"note: {report.note}")
    return 0


def resolve_report(report_id: str, outcome: str, settings: Optional[Settings] = None) -> int:
    """Mark an open report resolved with a short outcome."""
    settings = settings or Settings()
    if not outcome.strip():
        print("--outcome must not be empty", file=sys.stderr)
        return EXIT_BAD_ARGUMENT
    store = _open_store(settings)
    if store is None:
        return EXIT_NO_DATABASE
    try:
        resolved = store.resolve_report(report_id, outcome.strip(), datetime.now(timezone.utc))
    finally:
        store.close()
    if not resolved:
        print(f"no open report {report_id!r}", file=sys.stderr)
        return EXIT_NOT_FOUND
    print(f"report {report_id} resolved: {outcome.strip()}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list open reports, newest first")
    show = commands.add_parser("show", help="save a report's image")
    show.add_argument("report_id")
    show.add_argument("--out", required=True)
    resolve = commands.add_parser("resolve", help="mark a report resolved")
    resolve.add_argument("report_id")
    resolve.add_argument("--outcome", required=True)
    args = parser.parse_args(argv)
    if args.command == "list":
        return list_reports()
    if args.command == "show":
        return show_report(args.report_id, args.out)
    return resolve_report(args.report_id, args.outcome)


if __name__ == "__main__":
    sys.exit(main())
