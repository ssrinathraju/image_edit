from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LogSender:
    """Writes the email to the server log; for development, where no mail account exists."""

    def send(self, to: str, subject: str, body: str) -> None:
        # WARNING, not INFO: uvicorn leaves application loggers below WARNING
        # unconfigured, and a developer must be able to read the code.
        logger.warning("Email not delivered, logged instead. To: %s | Subject: %s | %s", to, subject, body)
