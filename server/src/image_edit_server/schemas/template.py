from __future__ import annotations

from pydantic import BaseModel, Field

TEMPLATE_ID_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
MAX_TEMPLATE_PROMPT_CHARS = 500
MAX_POPULARITY = 100


class Template(BaseModel):
    id: str = Field(pattern=TEMPLATE_ID_PATTERN)
    title: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    popularity: int = Field(ge=0, le=MAX_POPULARITY)
    preview: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=MAX_TEMPLATE_PROMPT_CHARS)


class TemplateSummary(BaseModel):
    id: str
    title: str
    tags: list[str]
    preview_url: str
