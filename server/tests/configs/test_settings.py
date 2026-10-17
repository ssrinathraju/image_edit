import pytest
from pydantic import ValidationError
from image_edit_server.configs.settings import Settings


def test_defaults():
    s = Settings()
    assert s.MAX_FACES == 4
    assert s.MIN_FACES == 1
    assert s.MAX_PROMPT_CHARS == 500
    assert s.MAX_UPLOAD_BYTES == 10 * 1024 * 1024
    assert s.JOB_CONCURRENCY == 1
    assert s.OUTPUT_RETENTION_HOURS == 24
    assert s.STORAGE_ROOT == "./storage"
    assert "image/jpeg" in s.ACCEPTED_IMAGE_TYPES


def test_auth_defaults():
    s = Settings()
    assert s.AUTH_DB_PATH == ""
    assert s.SESSION_TTL_DAYS == 30
    assert s.PASSWORD_MIN_CHARS == 8
    assert s.PASSWORD_MAX_CHARS == 128
    assert s.LOGIN_MAX_FAILURES == 5
    assert s.LOGIN_LOCKOUT_MINUTES == 15


def test_retention_defaults_and_override(monkeypatch):
    s = Settings()
    assert s.OUTPUT_RETENTION_HOURS == 24
    assert s.RETENTION_SWEEP_MINUTES == 10
    monkeypatch.setenv("IMAGE_EDIT_RETENTION_SWEEP_MINUTES", "30")
    assert Settings().RETENTION_SWEEP_MINUTES == 30


@pytest.mark.parametrize(
    "field", ["OUTPUT_RETENTION_HOURS", "RETENTION_SWEEP_MINUTES"]
)
def test_retention_settings_below_one_are_rejected_by_name(field):
    with pytest.raises(ValidationError, match=field):
        Settings(**{field: 0})


def test_plan_and_referral_defaults():
    s = Settings()
    assert s.FREE_DAILY_LIMIT == 3
    assert s.PREMIUM_DAILY_LIMIT == 30
    assert s.REFERRAL_BONUS == 5
    assert s.REFERRAL_MAX_REWARDS == 10


def test_plan_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_PREMIUM_DAILY_LIMIT", "100")
    assert Settings().PREMIUM_DAILY_LIMIT == 100


def test_auth_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_LOGIN_MAX_FAILURES", "3")
    assert Settings().LOGIN_MAX_FAILURES == 3


def test_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_MAX_FACES", "2")
    s = Settings()
    assert s.MAX_FACES == 2


def test_templates_dir_default_and_override(monkeypatch):
    assert Settings().TEMPLATES_DIR == "./seed/templates"
    monkeypatch.setenv("IMAGE_EDIT_TEMPLATES_DIR", "/tmp/custom")
    assert Settings().TEMPLATES_DIR == "/tmp/custom"


def test_accepted_image_types_set():
    s = Settings()
    types = s.accepted_image_types_set()
    assert "image/jpeg" in types
    assert "image/png" in types
    assert "image/webp" in types
