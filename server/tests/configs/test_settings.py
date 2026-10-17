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


def test_email_defaults():
    s = Settings()
    assert s.SMTP_HOST == ""
    assert s.SMTP_PORT == 587
    assert s.SMTP_USERNAME == ""
    assert s.SMTP_PASSWORD == ""
    assert s.SMTP_FROM == ""
    assert s.SMTP_SECURITY == "starttls"
    assert s.EMAIL_CODE_TTL_MINUTES == 15
    assert s.EMAIL_CODE_MAX_ATTEMPTS == 5
    assert s.EMAIL_RESEND_SECONDS == 60
    assert s.EMAIL_MAX_PER_HOUR == 5


def test_email_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_EMAIL_MAX_PER_HOUR", "9")
    monkeypatch.setenv("IMAGE_EDIT_SMTP_SECURITY", "ssl")
    s = Settings()
    assert s.EMAIL_MAX_PER_HOUR == 9
    assert s.SMTP_SECURITY == "ssl"


def test_smtp_host_without_sender_address_is_rejected():
    with pytest.raises(ValidationError, match="SMTP_FROM"):
        Settings(SMTP_HOST="smtp.example.com")
    assert Settings(SMTP_HOST="smtp.example.com", SMTP_FROM="a@example.com")


def test_unknown_smtp_security_is_rejected():
    with pytest.raises(ValidationError, match="SMTP_SECURITY"):
        Settings(SMTP_SECURITY="tls13")


@pytest.mark.parametrize(
    "field",
    ["EMAIL_CODE_TTL_MINUTES", "EMAIL_CODE_MAX_ATTEMPTS", "EMAIL_RESEND_SECONDS", "EMAIL_MAX_PER_HOUR"],
)
def test_email_numeric_settings_below_one_are_rejected_by_name(field):
    with pytest.raises(ValidationError, match=field):
        Settings(**{field: 0})


def test_social_sign_in_defaults():
    s = Settings()
    assert s.GOOGLE_CLIENT_IDS == []
    assert (s.APPLE_BUNDLE_ID, s.APPLE_TEAM_ID, s.APPLE_KEY_ID, s.APPLE_PRIVATE_KEY_PATH) == ("", "", "", "")
    assert not s.is_google_configured()
    assert not s.is_apple_configured()
    assert not s.is_apple_revocation_configured()


def test_google_client_ids_are_parsed_from_the_environment(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_GOOGLE_CLIENT_IDS", "ios.apps, web.apps ,")
    s = Settings()
    assert s.GOOGLE_CLIENT_IDS == ["ios.apps", "web.apps"]
    assert s.is_google_configured()


def test_apple_bundle_id_alone_configures_sign_in_but_not_revocation():
    s = Settings(APPLE_BUNDLE_ID="com.example.app")
    assert s.is_apple_configured()
    assert not s.is_apple_revocation_configured()


def test_all_apple_key_settings_with_a_readable_key_are_accepted(tmp_path):
    key = tmp_path / "AuthKey.p8"
    key.write_text("key")
    s = Settings(
        APPLE_BUNDLE_ID="com.example.app",
        APPLE_TEAM_ID="TEAM",
        APPLE_KEY_ID="KEY",
        APPLE_PRIVATE_KEY_PATH=str(key),
    )
    assert s.is_apple_revocation_configured()


def test_partial_apple_key_settings_are_rejected_naming_the_missing_ones():
    with pytest.raises(ValidationError, match="APPLE_KEY_ID"):
        Settings(APPLE_BUNDLE_ID="b", APPLE_TEAM_ID="TEAM", APPLE_PRIVATE_KEY_PATH="/k")


def test_apple_key_settings_without_a_bundle_id_are_rejected(tmp_path):
    key = tmp_path / "AuthKey.p8"
    key.write_text("key")
    with pytest.raises(ValidationError, match="APPLE_BUNDLE_ID"):
        Settings(APPLE_TEAM_ID="T", APPLE_KEY_ID="K", APPLE_PRIVATE_KEY_PATH=str(key))


def test_an_unreadable_apple_key_file_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="cannot be read"):
        Settings(
            APPLE_BUNDLE_ID="b",
            APPLE_TEAM_ID="T",
            APPLE_KEY_ID="K",
            APPLE_PRIVATE_KEY_PATH=str(tmp_path / "missing.p8"),
        )
