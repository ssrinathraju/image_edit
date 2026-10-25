import smtplib
import ssl

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.services.email.smtp_sender import SMTP_TIMEOUT_SECONDS, SmtpSender


class FakeSmtp:
    instances: list["FakeSmtp"] = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.contexts = [context] if context is not None else []
        self.calls: list[str] = []
        self.sent = []
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.contexts.append(context)
        self.calls.append("starttls")

    def login(self, username, password):
        self.calls.append(f"login:{username}:{password}")

    def send_message(self, message):
        self.calls.append("send")
        self.sent.append(message)


class FakeSmtpSsl(FakeSmtp):
    pass


@pytest.fixture(autouse=True)
def fake_smtplib(monkeypatch):
    FakeSmtp.instances = []
    monkeypatch.setattr(smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSmtpSsl)


def _sender(**overrides) -> SmtpSender:
    values = dict(
        SMTP_HOST="smtp.example.com", SMTP_PORT=2525, SMTP_FROM="noreply@example.com", SUPPORT_EMAIL="help@example.com"
    )
    return SmtpSender(Settings(**{**values, **overrides}))


def _assert_verifying(smtp) -> None:
    assert len(smtp.contexts) == 1 and smtp.contexts[0] is not None
    assert smtp.contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert smtp.contexts[0].check_hostname is True


def test_starttls_mode_upgrades_logs_in_and_sends_the_message():
    _sender(SMTP_USERNAME="user", SMTP_PASSWORD="pw").send("ana@example.com", "Subj", "Body 123456")

    smtp = FakeSmtp.instances[0]
    assert type(smtp) is FakeSmtp
    assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.example.com", 2525, SMTP_TIMEOUT_SECONDS)
    assert smtp.calls == ["starttls", "login:user:pw", "send"]
    _assert_verifying(smtp)
    message = smtp.sent[0]
    assert message["From"] == "noreply@example.com"
    assert message["To"] == "ana@example.com"
    assert message["Subject"] == "Subj"
    assert message.get_content().strip() == "Body 123456"


def test_ssl_mode_uses_the_ssl_connection_without_starttls():
    _sender(SMTP_SECURITY="ssl", SMTP_USERNAME="user", SMTP_PASSWORD="pw").send("a@example.com", "S", "B")

    smtp = FakeSmtp.instances[0]
    assert type(smtp) is FakeSmtpSsl
    assert smtp.calls == ["login:user:pw", "send"]
    _assert_verifying(smtp)


def test_none_mode_skips_starttls_and_skips_login_without_a_username():
    _sender(SMTP_SECURITY="none").send("a@example.com", "S", "B")

    smtp = FakeSmtp.instances[0]
    assert type(smtp) is FakeSmtp
    assert smtp.calls == ["send"]
    assert smtp.sent[0]["To"] == "a@example.com"
