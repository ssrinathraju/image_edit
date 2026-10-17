from __future__ import annotations

from typing import Protocol


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None:
        """Deliver one plain-text email; raises when delivery fails."""
        ...
