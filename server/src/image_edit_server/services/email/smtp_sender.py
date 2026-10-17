from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from image_edit_server.configs.settings import Settings

SMTP_TIMEOUT_SECONDS = 10


class SmtpSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        cfg = self._settings
        message = EmailMessage()
        message["From"] = cfg.SMTP_FROM
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        context = ssl.create_default_context()
        with self._connect(context) as server:
            if cfg.SMTP_SECURITY == "starttls":
                server.starttls(context=context)
            if cfg.SMTP_USERNAME:
                server.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
            server.send_message(message)

    def _connect(self, context: ssl.SSLContext) -> smtplib.SMTP:
        cfg = self._settings
        if cfg.SMTP_SECURITY == "ssl":
            return smtplib.SMTP_SSL(
                cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS, context=context
            )
        return smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
