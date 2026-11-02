from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, File, Form, UploadFile

from image_edit_server.api.deps import AdminDep, TemplateAdminDep
from image_edit_server.core.template_preview import MAX_PREVIEW_BYTES
from image_edit_server.schemas.template import AdminTemplate
from image_edit_server.services.template_admin_service import RawTemplateFields
from image_edit_server.services.template_service import to_admin_template

router = APIRouter(prefix="/admin/templates", tags=["admin-templates"])

TextForm = Annotated[Optional[str], Form()]
PreviewFile = Annotated[Optional[UploadFile], File()]


async def _read_preview(preview: Optional[UploadFile]) -> Optional[bytes]:
    """Read at most one byte past the cap, so an oversized upload is seen without loading it all."""
    if preview is None:
        return None
    return await preview.read(MAX_PREVIEW_BYTES + 1)


@router.get("", response_model=list[AdminTemplate])
async def list_all_templates(admin: AdminDep, service: TemplateAdminDep) -> list[AdminTemplate]:
    return [to_admin_template(t) for t in service.list_all()]


@router.post("", status_code=201, response_model=AdminTemplate)
async def create_template(
    admin: AdminDep,
    service: TemplateAdminDep,
    id: TextForm = None,
    title: TextForm = None,
    tags: TextForm = None,
    popularity: TextForm = None,
    prompt: TextForm = None,
    preview: PreviewFile = None,
) -> AdminTemplate:
    fields = RawTemplateFields(id, title, tags, popularity, prompt)
    created = await service.create(admin.id, fields, await _read_preview(preview))
    return to_admin_template(created)


@router.patch("/{template_id}", response_model=AdminTemplate)
async def edit_template(
    template_id: str,
    admin: AdminDep,
    service: TemplateAdminDep,
    title: TextForm = None,
    tags: TextForm = None,
    popularity: TextForm = None,
    prompt: TextForm = None,
    preview: PreviewFile = None,
) -> AdminTemplate:
    fields = RawTemplateFields(None, title, tags, popularity, prompt)
    edited = await service.edit(admin.id, template_id, fields, await _read_preview(preview))
    return to_admin_template(edited)


@router.post("/{template_id}/retire", response_model=AdminTemplate)
async def retire_template(
    template_id: str, admin: AdminDep, service: TemplateAdminDep
) -> AdminTemplate:
    return to_admin_template(await service.retire(admin.id, template_id))


@router.post("/{template_id}/restore", response_model=AdminTemplate)
async def restore_template(
    template_id: str, admin: AdminDep, service: TemplateAdminDep
) -> AdminTemplate:
    return to_admin_template(await service.restore(admin.id, template_id))
