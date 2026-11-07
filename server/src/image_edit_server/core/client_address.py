from __future__ import annotations

from fastapi import Request

FORWARDED_FOR_HEADER = "x-forwarded-for"
UNKNOWN_ADDRESS = "unknown"


def client_address(request: Request, trusted_hops: int) -> str:
    """The caller's network address; `trusted_hops` proxies append to X-Forwarded-For."""
    connection_address = request.client.host if request.client else UNKNOWN_ADDRESS
    if trusted_hops == 0:
        return connection_address
    entries = [part.strip() for part in request.headers.get(FORWARDED_FOR_HEADER, "").split(",")]
    entries = [entry for entry in entries if entry]
    if len(entries) < trusted_hops:
        return connection_address
    return entries[-trusted_hops]
