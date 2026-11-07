from __future__ import annotations

from typing import Optional

FORWARDED_FOR_HEADER = "x-forwarded-for"
UNKNOWN_ADDRESS = "unknown"


def client_address(
    connection_host: Optional[str], forwarded_for: Optional[str], trusted_hops: int
) -> str:
    """The caller's network address; `trusted_hops` proxies append to X-Forwarded-For."""
    connection_address = connection_host or UNKNOWN_ADDRESS
    if trusted_hops == 0:
        return connection_address
    entries = [part.strip() for part in (forwarded_for or "").split(",")]
    entries = [entry for entry in entries if entry]
    if len(entries) < trusted_hops:
        return connection_address
    return entries[-trusted_hops]
