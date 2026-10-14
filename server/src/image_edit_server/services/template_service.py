from __future__ import annotations

from typing import Optional

from image_edit_server.repos.template_catalog import TemplateCatalog
from image_edit_server.schemas.template import TemplateSummary

PREVIEW_URL_PREFIX = "/template-previews"


def list_templates(catalog: TemplateCatalog, query: Optional[str]) -> list[TemplateSummary]:
    """Return catalog templates matching `query`, without their prompts."""
    return [
        TemplateSummary(
            id=t.id,
            title=t.title,
            tags=list(t.tags),
            preview_url=f"{PREVIEW_URL_PREFIX}/{t.preview}",
        )
        for t in catalog.search(query)
    ]
