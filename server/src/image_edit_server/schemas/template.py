from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, Field

from image_edit_server.schemas.api import ErrorBody

TEMPLATE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_TEMPLATE_ID_CHARS = 64
MAX_TEMPLATE_TITLE_CHARS = 60
MAX_TEMPLATE_TAGS = 10
MAX_TEMPLATE_TAG_CHARS = 30
MAX_TEMPLATE_PROMPT_CHARS = 500
MAX_POPULARITY = 100


class Template(BaseModel):
    id: str = Field(pattern=TEMPLATE_ID_PATTERN, max_length=MAX_TEMPLATE_ID_CHARS)
    title: str = Field(min_length=1, max_length=MAX_TEMPLATE_TITLE_CHARS)
    tags: list[Annotated[str, Field(min_length=1, max_length=MAX_TEMPLATE_TAG_CHARS)]] = (
        Field(default_factory=list, max_length=MAX_TEMPLATE_TAGS)
    )
    popularity: int = Field(ge=0, le=MAX_POPULARITY)
    preview: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=MAX_TEMPLATE_PROMPT_CHARS)


class StoredTemplate(Template):
    """A template as the database holds it, with its lifecycle state."""

    retired: bool = False
    updated_at: str


class TemplateSummary(BaseModel):
    id: str
    title: str
    tags: list[str]
    preview_url: str


class AdminTemplate(TemplateSummary):
    popularity: int
    prompt: str
    retired: bool
    updated_at: str


class FieldErrorBody(ErrorBody):
    """An error that names the request field that caused it."""

    field: Optional[str] = None
