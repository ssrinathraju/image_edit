from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from image_edit_server.schemas.template import Template

CATALOG_FILENAME = "catalog.json"
PREVIEWS_DIRNAME = "previews"


class CatalogError(Exception):
    """Raised when the template catalog is missing, malformed, or inconsistent."""


class TemplateCatalog:
    def __init__(self, templates: list[Template]) -> None:
        ordered = sorted(templates, key=lambda t: (-t.popularity, t.title))
        self._templates: tuple[Template, ...] = tuple(ordered)
        self._by_id = {t.id: t for t in ordered}

    def all(self) -> list[Template]:
        return list(self._templates)

    def get(self, template_id: str) -> Optional[Template]:
        return self._by_id.get(template_id)

    def search(self, query: Optional[str]) -> list[Template]:
        needle = (query or "").strip().lower()
        if not needle:
            return self.all()
        return [t for t in self._templates if _matches(t, needle)]


def _matches(template: Template, needle: str) -> bool:
    if needle in template.title.lower():
        return True
    return any(needle in tag.lower() for tag in template.tags)


def load_catalog(templates_dir: Path) -> TemplateCatalog:
    """Load and validate the catalog; raise CatalogError naming the bad entry."""
    catalog_file = templates_dir / CATALOG_FILENAME
    raw = _read_entries(catalog_file)

    templates: list[Template] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        template = _parse_entry(entry, index)
        if template.id in seen:
            raise CatalogError(f"duplicate template id '{template.id}'")
        seen.add(template.id)
        preview_path = templates_dir / PREVIEWS_DIRNAME / template.preview
        if not preview_path.is_file():
            raise CatalogError(
                f"template '{template.id}' references missing preview '{template.preview}'"
            )
        templates.append(template)
    return TemplateCatalog(templates)


def _read_entries(catalog_file: Path) -> list[object]:
    if not catalog_file.is_file():
        raise CatalogError(f"catalog file not found: {catalog_file}")
    try:
        data = json.loads(catalog_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"catalog is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise CatalogError("catalog must be a JSON array of templates")
    return data


def _parse_entry(entry: object, index: int) -> Template:
    try:
        return Template.model_validate(entry)
    except ValidationError as exc:
        entry_id = entry.get("id") if isinstance(entry, dict) else None
        label = f"'{entry_id}'" if entry_id else f"at index {index}"
        raise CatalogError(f"invalid template {label}: {exc}") from exc
