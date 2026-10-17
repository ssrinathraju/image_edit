from __future__ import annotations

import smtplib
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
        with self._connect() as server:
            if cfg.SMTP_SECURITY == "starttls":
                server.starttls()
            if cfg.SMTP_USERNAME:
                server.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
            server.send_message(message)

    def _connect(self) -> smtplib.SMTP:
        cfg = self._settings
        factory = smtplib.SMTP_SSL if cfg.SMTP_SECURITY == "ssl" else smtplib.SMTP
        return factory(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
