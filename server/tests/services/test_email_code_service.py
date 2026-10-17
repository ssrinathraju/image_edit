import logging
from datetime import datetime, timezone

import pytest

from image_edit_server.configs.settings import Settings
from image_edit_server.core.email_codes import CodePurpose, ConsumeResult
from image_edit_server.repos.user_store import SqliteUserStore
from image_edit_server.services import email_code_service

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
SETTINGS = Settings()


@pytest.fixture
def users() -> SqliteUserStore:
    return SqliteUserStore(":memory:")


@pytest.fixture
def uid(users) -> str:
    return users.create_user("ana@example.com", "hash").id


class RecordingSender:
    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))


class FailingSender:
    def send(self, to, subject, body):
        raise ConnectionRefusedError(f"refused while sending {body}")


def test_issue_returns_a_six_digit_code_that_the_store_accepts(users, uid):
    outcome = email_code_service.issue_code(users, uid, CodePurpose.VERIFY_EMAIL, SETTINGS, NOW)

    assert len(outcome.code) == 6 and outcome.code.isdigit()
    result = users.consume_code(uid, CodePurpose.VERIFY_EMAIL, outcome.code, NOW, 5)
    assert result is ConsumeResult.OK


def test_a_limited_issue_passes_retry_after_through(users, uid):
    email_code_service.issue_code(users, uid, CodePurpose.VERIFY_EMAIL, SETTINGS, NOW)

    outcome = email_code_service.issue_code(
        users, uid, CodePurpose.VERIFY_EMAIL, SETTINGS, NOW.replace(second=20)
    )

    assert outcome.code is None
    assert outcome.retry_after_seconds == 40


@pytest.mark.parametrize("purpose", list(CodePurpose))
def test_the_message_names_the_code_and_the_minutes(purpose):
    sender = RecordingSender()

    email_code_service.deliver(sender, "u1", "ana@example.com", purpose, "123456", 15)

    to, subject, body = sender.sent[0]
    assert to == "ana@example.com"
    assert "123456" in body and "15 minutes" in body
    assert subject


def test_a_raising_sender_is_logged_without_the_code_and_does_not_raise(caplog):
    with caplog.at_level(logging.ERROR):
        email_code_service.deliver(
            FailingSender(), "u1", "ana@example.com", CodePurpose.VERIFY_EMAIL, "123456", 15
        )

    assert "ConnectionRefusedError" in caplog.text
    assert "u1" in caplog.text
    assert "123456" not in caplog.text
