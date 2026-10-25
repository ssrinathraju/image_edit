import pytest
from pydantic import ValidationError
from image_edit_server.configs.settings import Settings
from tests.helpers import write_apple_key_file


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
    assert Settings(
        SMTP_HOST="smtp.example.com", SMTP_FROM="a@example.com", SUPPORT_EMAIL="help@example.com"
    )


def test_smtp_host_without_a_support_address_is_rejected():
    with pytest.raises(ValidationError, match="SUPPORT_EMAIL"):
        Settings(SMTP_HOST="smtp.example.com", SMTP_FROM="a@example.com")


def test_the_support_address_is_optional_in_log_mode():
    assert Settings().SUPPORT_EMAIL == ""


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
    key = write_apple_key_file(tmp_path / "AuthKey.p8")
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
    key = write_apple_key_file(tmp_path / "AuthKey.p8")
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


def test_an_apple_key_file_that_is_not_a_pem_key_is_rejected(tmp_path):
    key = tmp_path / "AuthKey.p8"
    key.write_text("not a pem key")

    with pytest.raises(ValidationError, match="not a PEM private key"):
        Settings(
            APPLE_BUNDLE_ID="b",
            APPLE_TEAM_ID="T",
            APPLE_KEY_ID="K",
            APPLE_PRIVATE_KEY_PATH=str(key),
        )


def test_consent_version_defaults_to_one_and_can_be_overridden(monkeypatch):
    assert Settings().CONSENT_VERSION == "1"
    monkeypatch.setenv("IMAGE_EDIT_CONSENT_VERSION", "2")
    assert Settings().CONSENT_VERSION == "2"


def test_empty_consent_version_refuses_to_start(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_CONSENT_VERSION", "")
    with pytest.raises(ValidationError, match="CONSENT_VERSION"):
        Settings()


def test_safety_defaults():
    s = Settings()
    assert s.SAFETY_TERMS_FILE == "./seed/safety/blocked_terms.txt"
    assert s.SAFETY_MODEL_ID == "Falconsai/nsfw_image_detection"
    assert s.SAFETY_DEVICE == "cpu"
    assert s.SAFETY_NSFW_THRESHOLD == 0.7
    assert s.SAFETY_STUB_FLAG == "none"
    assert s.STRIKE_LIMIT == 3
    assert s.STRIKE_WINDOW_HOURS == 24
    assert s.REPORTS_PER_DAY == 20
    assert s.REPORT_RETENTION_DAYS == 30


@pytest.mark.parametrize(
    "field,value",
    [
        ("SAFETY_NSFW_THRESHOLD", -0.1),
        ("SAFETY_NSFW_THRESHOLD", 1.1),
        ("STRIKE_LIMIT", 0),
        ("STRIKE_WINDOW_HOURS", 0),
        ("REPORTS_PER_DAY", 0),
        ("REPORT_RETENTION_DAYS", 0),
    ],
)
def test_safety_bounds_are_enforced_by_name(field, value):
    with pytest.raises(ValidationError, match=field):
        Settings(**{field: value})


def test_threshold_bounds_are_inclusive():
    assert Settings(SAFETY_NSFW_THRESHOLD=0).SAFETY_NSFW_THRESHOLD == 0
    assert Settings(SAFETY_NSFW_THRESHOLD=1).SAFETY_NSFW_THRESHOLD == 1


def test_unknown_stub_flag_is_refused():
    with pytest.raises(ValidationError, match="SAFETY_STUB_FLAG"):
        Settings(SAFETY_STUB_FLAG="sometimes")


@pytest.mark.parametrize("flag", ["outputs", "all"])
def test_stub_flag_with_a_real_backend_is_refused(flag):
    with pytest.raises(ValidationError, match="SAFETY_STUB_FLAG"):
        Settings(SAFETY_STUB_FLAG=flag, MODEL_BACKEND="sana")


def test_stub_flag_none_is_fine_with_a_real_backend():
    assert Settings(MODEL_BACKEND="sana").SAFETY_STUB_FLAG == "none"
