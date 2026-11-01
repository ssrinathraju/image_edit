from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException

from image_edit_server.core.template_preview import InvalidPreview, normalise_preview
from image_edit_server.core.user_store import UserStore
from image_edit_server.repos.template_catalog import CatalogHolder, catalog_from_stored
from image_edit_server.repos.user_store_templates import TemplateExistsError
from image_edit_server.schemas.template import (
    MAX_POPULARITY,
    MAX_TEMPLATE_ID_CHARS,
    MAX_TEMPLATE_PROMPT_CHARS,
    MAX_TEMPLATE_TAG_CHARS,
    MAX_TEMPLATE_TAGS,
    MAX_TEMPLATE_TITLE_CHARS,
    TEMPLATE_ID_PATTERN,
    FieldErrorBody,
    StoredTemplate,
)
from image_edit_server.services.safety.safety_service import SafetyService
from image_edit_server.services.template_seed import hashed_preview_name, write_preview_file

logger = logging.getLogger(__name__)

PREVIEW_SUFFIX = ".webp"
POPULARITY_PATTERN = re.compile(r"-?[0-9]+")
MAX_LOGGED_ID_CHARS = 64


@dataclass(frozen=True)
class RawTemplateFields:
    """Form values exactly as sent; None means the field was not supplied."""

    id: Optional[str] = None
    title: Optional[str] = None
    tags: Optional[str] = None
    popularity: Optional[str] = None
    prompt: Optional[str] = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _refusal(status: int, code: str, detail: str, field: Optional[str] = None) -> HTTPException:
    body = FieldErrorBody(error=code, detail=detail, field=field)
    return HTTPException(status, body.model_dump(exclude_none=True))


def _invalid_field(field: str, detail: str) -> HTTPException:
    return _refusal(400, "invalid_template_field", detail, field)


def _not_found(template_id: str) -> HTTPException:
    return _refusal(404, "template_not_found", f"no template with id '{template_id}'")


def _clean_id(raw: Optional[str]) -> str:
    if raw is None:
        raise _invalid_field("id", "id is required")
    if len(raw) > MAX_TEMPLATE_ID_CHARS or not re.fullmatch(TEMPLATE_ID_PATTERN, raw):
        raise _invalid_field(
            "id",
            f"id must be 1 to {MAX_TEMPLATE_ID_CHARS} lower-case letters, digits and single hyphens",
        )
    return raw


def _clean_title(raw: str) -> str:
    title = raw.strip()
    if not 1 <= len(title) <= MAX_TEMPLATE_TITLE_CHARS:
        raise _invalid_field("title", f"title must be 1 to {MAX_TEMPLATE_TITLE_CHARS} characters")
    return title


def _clean_prompt(raw: str) -> str:
    prompt = raw.strip()
    if not 1 <= len(prompt) <= MAX_TEMPLATE_PROMPT_CHARS:
        raise _invalid_field(
            "prompt", f"prompt must be 1 to {MAX_TEMPLATE_PROMPT_CHARS} characters"
        )
    return prompt


def _clean_popularity(raw: str) -> int:
    text = raw.strip()
    if not POPULARITY_PATTERN.fullmatch(text) or not 0 <= int(text) <= MAX_POPULARITY:
        raise _invalid_field("popularity", f"popularity must be a whole number from 0 to {MAX_POPULARITY}")
    return int(text)


def _clean_tags(raw: str) -> list[str]:
    tags: list[str] = []
    for piece in raw.split(","):
        tag = piece.strip().lower()
        if not tag:
            continue
        if len(tag) > MAX_TEMPLATE_TAG_CHARS:
            raise _invalid_field("tags", f"each tag must be 1 to {MAX_TEMPLATE_TAG_CHARS} characters")
        if tag not in tags:
            tags.append(tag)
    if len(tags) > MAX_TEMPLATE_TAGS:
        raise _invalid_field("tags", f"at most {MAX_TEMPLATE_TAGS} tags are allowed")
    return tags


def _clean_supplied(raw: RawTemplateFields) -> dict:
    """Clean the fields that were supplied, keyed by name; the first bad one raises."""
    cleaners = (
        ("title", _clean_title),
        ("tags", _clean_tags),
        ("popularity", _clean_popularity),
        ("prompt", _clean_prompt),
    )
    return {
        name: clean(getattr(raw, name))
        for name, clean in cleaners
        if getattr(raw, name) is not None
    }


def _loggable_id(template_id: str) -> str:
    return repr(template_id[:MAX_LOGGED_ID_CHARS])


class TemplateAdminService:
    def __init__(
        self,
        store: UserStore,
        holder: CatalogHolder,
        safety: SafetyService,
        previews_dir: Path,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._store = store
        self._holder = holder
        self._safety = safety
        self._previews_dir = previews_dir
        self._clock = clock
        self._lock: Optional[asyncio.Lock] = None

    def _write_lock(self) -> asyncio.Lock:
        # Created on first use: before Python 3.10 a Lock binds to the loop current at
        # construction, and the app is built before the server's loop exists.
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def list_all(self) -> list[StoredTemplate]:
        """Every template, retired ones last, each group in the public order."""
        rows = self._store.list_templates()
        return sorted(rows, key=lambda t: (t.retired, -t.popularity, t.title))

    async def create(
        self, admin_id: str, raw: RawTemplateFields, preview: Optional[bytes]
    ) -> StoredTemplate:
        return await self._audited("create", raw.id or "", admin_id, self._create(admin_id, raw, preview))

    async def edit(
        self, admin_id: str, template_id: str, raw: RawTemplateFields, preview: Optional[bytes]
    ) -> StoredTemplate:
        return await self._audited("edit", template_id, admin_id, self._edit(admin_id, template_id, raw, preview))

    async def retire(self, admin_id: str, template_id: str) -> StoredTemplate:
        return await self._audited("retire", template_id, admin_id, self._set_retired(admin_id, template_id, True))

    async def restore(self, admin_id: str, template_id: str) -> StoredTemplate:
        return await self._audited("restore", template_id, admin_id, self._set_retired(admin_id, template_id, False))

    async def _audited(self, action: str, template_id: str, admin_id: str, operation):
        try:
            return await operation
        except HTTPException as error:
            logger.info(
                "template_admin_refused action=%s template=%s admin=%s reason=%s",
                action, _loggable_id(template_id), admin_id, error.detail["error"],
            )
            raise

    def _log_success(self, action: str, template_id: str, admin_id: str, fields: str = "") -> None:
        suffix = f" fields={fields}" if fields else ""
        logger.info("template_admin action=%s template=%s admin=%s%s", action, template_id, admin_id, suffix)

    async def _create(
        self, admin_id: str, raw: RawTemplateFields, preview: Optional[bytes]
    ) -> StoredTemplate:
        template_id = _clean_id(raw.id)
        for name in ("title", "tags", "popularity", "prompt"):
            if getattr(raw, name) is None:
                raise _invalid_field(name, f"{name} is required")
        fields = _clean_supplied(raw)
        self._screen(fields)
        if preview is None:
            raise _refusal(400, "invalid_preview", "a preview image is required", "preview")
        webp = await self._normalise(preview)
        async with self._write_lock():
            if self._store.get_template(template_id) is not None:
                raise _refusal(409, "template_exists", f"template '{template_id}' already exists")
            name = hashed_preview_name(template_id, webp, PREVIEW_SUFFIX)
            row = StoredTemplate(
                id=template_id, preview=name, retired=False,
                updated_at=self._clock().isoformat(), **fields,
            )
            await self._write_file_then(name, webp, lambda: self._store.insert_template(row))
            self._swap_catalog()
        self._log_success("create", template_id, admin_id)
        return row

    async def _edit(
        self, admin_id: str, template_id: str, raw: RawTemplateFields, preview: Optional[bytes]
    ) -> StoredTemplate:
        if self._store.get_template(template_id) is None:
            raise _not_found(template_id)
        fields = _clean_supplied(raw)
        if not fields and preview is None:
            raise _invalid_field("fields", "supply at least one of title, tags, popularity, prompt, preview")
        self._screen(fields)
        webp = await self._normalise(preview) if preview is not None else None
        async with self._write_lock():
            current = self._store.get_template(template_id)
            if current is None:
                raise _not_found(template_id)
            changes = _to_columns(fields)
            now = self._clock().isoformat()
            if webp is None:
                self._commit(lambda: self._store.update_template(template_id, changes, now))
            else:
                name = hashed_preview_name(template_id, webp, PREVIEW_SUFFIX)
                changes["preview_file"] = name
                await self._write_file_then(
                    name, webp, lambda: self._store.update_template(template_id, changes, now)
                )
            self._swap_catalog()
            if webp is not None and current.preview != changes["preview_file"]:
                self._delete_file_if_unreferenced(current.preview)
            updated = self._store.get_template(template_id)
        changed = [*fields, *(["preview"] if webp is not None else [])]
        self._log_success("edit", template_id, admin_id, ",".join(changed))
        return updated

    async def _set_retired(self, admin_id: str, template_id: str, retired: bool) -> StoredTemplate:
        async with self._write_lock():
            current = self._store.get_template(template_id)
            if current is None:
                raise _not_found(template_id)
            if current.retired != retired:
                now = self._clock().isoformat()
                self._commit(lambda: self._store.set_template_retired(template_id, retired, now))
                self._swap_catalog()
            updated = self._store.get_template(template_id)
        self._log_success("retire" if retired else "restore", template_id, admin_id)
        return updated

    def _screen(self, fields: dict) -> None:
        for name in ("title", "tags", "prompt"):
            value = fields.get(name)
            texts = value if isinstance(value, list) else [value]
            if any(text is not None and self._safety.is_prompt_blocked(text) for text in texts):
                raise _refusal(
                    400, "template_text_blocked", f"{name} contains a blocked term", name
                )

    async def _normalise(self, data: bytes) -> bytes:
        try:
            return await asyncio.to_thread(normalise_preview, data)
        except InvalidPreview as error:
            raise _refusal(400, "invalid_preview", str(error), "preview") from error

    async def _write_file_then(self, name: str, content: bytes, commit: Callable[[], object]) -> None:
        await asyncio.to_thread(write_preview_file, self._previews_dir, name, content)
        try:
            self._commit(commit)
        except HTTPException:
            self._delete_file_if_unreferenced(name)
            raise

    def _commit(self, write: Callable[[], object]) -> None:
        try:
            write()
        except TemplateExistsError as error:
            raise _refusal(409, "template_exists", "template already exists") from error
        except Exception as error:
            logger.exception("template store write failed")
            raise _refusal(
                500, "template_store_failed", "the change could not be saved; nothing was changed"
            ) from error

    def _swap_catalog(self) -> None:
        self._holder.replace(catalog_from_stored(self._store.list_templates()))

    def _delete_file_if_unreferenced(self, name: str) -> None:
        if any(row.preview == name for row in self._store.list_templates()):
            return
        try:
            (self._previews_dir / name).unlink(missing_ok=True)
        except OSError:
            # The startup sweep removes it later.
            logger.exception("could not delete preview file %s", name)


def _to_columns(fields: dict) -> dict:
    columns = dict(fields)
    if "tags" in columns:
        columns["tags_json"] = json.dumps(columns.pop("tags"))
    return columns
