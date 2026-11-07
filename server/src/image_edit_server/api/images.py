from __future__ import annotations

import re
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from image_edit_server.api.deps import ClockDep, ResultUrlSecretDep, SettingsDep
from image_edit_server.core import url_signing
from image_edit_server.repos import file_storage

router = APIRouter(tags=["images"])

JOB_ID_PATTERN = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
MAX_EXPIRY_DIGITS = 12


def _not_found() -> HTTPException:
    # The same body as an unknown route, so a caller cannot tell why a request failed.
    return HTTPException(status_code=404, detail="Not Found")


def _parse_expiry(raw: Optional[str]) -> Optional[int]:
    if raw is None or not raw.isascii() or not raw.isdigit() or len(raw) > MAX_EXPIRY_DIGITS:
        return None
    return int(raw)


@router.get("/images/{job_id}.png")
async def get_image(
    job_id: str,
    settings: SettingsDep,
    secret: ResultUrlSecretDep,
    clock: ClockDep,
    exp: Annotated[Optional[str], Query()] = None,
    sig: Annotated[Optional[str], Query()] = None,
) -> FileResponse:
    expires_at = _parse_expiry(exp)
    if JOB_ID_PATTERN.fullmatch(job_id) is None or expires_at is None or sig is None:
        raise _not_found()
    if not url_signing.verify(job_id, expires_at, sig, secret, clock()):
        raise _not_found()
    path = file_storage.output_path(job_id, settings.STORAGE_ROOT)
    if path.is_symlink() or not path.is_file():
        raise _not_found()
    return FileResponse(
        path, media_type="image/png", headers={"Cache-Control": "private, no-store"}
    )
