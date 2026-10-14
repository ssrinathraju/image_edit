from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from image_edit_server.repos.template_catalog import TemplateCatalog
from image_edit_server.schemas.template import TemplateSummary
from image_edit_server.services import template_service

router = APIRouter(prefix="/templates", tags=["templates"])


def get_catalog() -> TemplateCatalog:
    raise RuntimeError("template catalog is not configured; create_app must override get_catalog")


CatalogDep = Annotated[TemplateCatalog, Depends(get_catalog)]


@router.get("", response_model=list[TemplateSummary])
async def list_templates(
    catalog: CatalogDep,
    q: Annotated[Optional[str], Query()] = None,
) -> list[TemplateSummary]:
    return template_service.list_templates(catalog, q)
