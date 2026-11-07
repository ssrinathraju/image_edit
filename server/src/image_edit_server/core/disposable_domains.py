from __future__ import annotations

from pathlib import Path
from typing import Optional

COMMENT_PREFIX = "#"


class DisposableDomains:
    """A set of disposable email domains, matched on the domain and all of its parents."""

    def __init__(self, domains: frozenset[str]) -> None:
        self._domains = domains

    def listed_domain(self, email: str) -> Optional[str]:
        """The listed domain that the address's domain equals or sits under, else None."""
        domain = email.rsplit("@", 1)[-1].strip().lower()
        labels = domain.split(".")
        for start in range(len(labels)):
            candidate = ".".join(labels[start:])
            if candidate in self._domains:
                return candidate
        return None

    def is_disposable(self, email: str) -> bool:
        return self.listed_domain(email) is not None


def load_disposable_domains(path: str) -> DisposableDomains:
    """Read one domain per line, skipping blanks and `#` comments; a missing file is an error."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(
            f"disposable-domain list {path!r} cannot be read: {error}; "
            "check DISPOSABLE_DOMAINS_FILE"
        ) from error
    domains = (line.strip().lower() for line in lines)
    return DisposableDomains(
        frozenset(d for d in domains if d and not d.startswith(COMMENT_PREFIX))
    )
