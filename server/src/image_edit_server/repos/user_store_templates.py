from __future__ import annotations

import json
import sqlite3
import threading
from typing import Optional

from image_edit_server.schemas.template import StoredTemplate

SEEDED_MARKER = "templates_seeded"

_TEMPLATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    popularity INTEGER NOT NULL,
    prompt TEXT NOT NULL,
    preview_file TEXT NOT NULL,
    retired INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_COLUMNS = "id, title, tags_json, popularity, prompt, preview_file, retired, updated_at"
_UPDATABLE = {"title", "tags_json", "popularity", "prompt", "preview_file"}


class TemplateExistsError(Exception):
    """Raised when a template id is already stored."""


def _to_template(row: tuple) -> StoredTemplate:
    return StoredTemplate(
        id=row[0],
        title=row[1],
        tags=json.loads(row[2]),
        popularity=row[3],
        prompt=row[4],
        preview=row[5],
        retired=bool(row[6]),
        updated_at=row[7],
    )


def _insert(conn: sqlite3.Connection, template: StoredTemplate) -> None:
    try:
        conn.execute(
            f"INSERT INTO templates ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                template.id,
                template.title,
                json.dumps(template.tags),
                template.popularity,
                template.prompt,
                template.preview,
                int(template.retired),
                template.updated_at,
            ),
        )
    except sqlite3.IntegrityError as error:
        raise TemplateExistsError(template.id) from error


class TemplatesMixin:
    _conn: sqlite3.Connection
    _lock: threading.Lock

    def insert_template(self, template: StoredTemplate) -> None:
        """Store a new template; raises TemplateExistsError on a duplicate id."""
        with self._lock, self._conn:
            _insert(self._conn, template)

    def update_template(self, template_id: str, changes: dict, updated_at: str) -> bool:
        """Apply column changes; returns False when the id is not stored."""
        unknown = set(changes) - _UPDATABLE
        if unknown:
            raise ValueError(f"cannot update columns {sorted(unknown)}")
        assignments = ", ".join(f"{column} = ?" for column in changes)
        with self._lock, self._conn:
            cursor = self._conn.execute(
                f"UPDATE templates SET {assignments}, updated_at = ? WHERE id = ?",
                (*changes.values(), updated_at, template_id),
            )
        return cursor.rowcount == 1

    def set_template_retired(self, template_id: str, retired: bool, updated_at: str) -> bool:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "UPDATE templates SET retired = ?, updated_at = ? WHERE id = ?",
                (int(retired), updated_at, template_id),
            )
        return cursor.rowcount == 1

    def get_template(self, template_id: str) -> Optional[StoredTemplate]:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {_COLUMNS} FROM templates WHERE id = ?", (template_id,)
            ).fetchone()
        return _to_template(row) if row else None

    def list_templates(self) -> list[StoredTemplate]:
        """Every stored template, retired ones included, in no particular order."""
        with self._lock:
            rows = self._conn.execute(f"SELECT {_COLUMNS} FROM templates").fetchall()
        return [_to_template(row) for row in rows]

    def are_templates_seeded(self) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM meta WHERE key = ?", (SEEDED_MARKER,)
            ).fetchone()
        return row is not None

    def import_seed_templates(self, templates: list[StoredTemplate]) -> None:
        """Insert the seed templates and set the seeded marker in one transaction."""
        with self._lock, self._conn:
            for template in templates:
                _insert(self._conn, template)
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, '1')", (SEEDED_MARKER,)
            )
