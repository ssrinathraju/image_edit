from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMAGE_EDIT_")

    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_FACES: int = 4
    MIN_FACES: int = 1
    MAX_PROMPT_CHARS: int = 500
    JOB_CONCURRENCY: int = 1
    OUTPUT_RETENTION_HOURS: int = Field(default=24, ge=1)
    RETENTION_SWEEP_MINUTES: int = Field(default=10, ge=1)
    ACCEPTED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"

    TEMPLATES_DIR: str = "./seed/templates"

    AUTH_DB_PATH: str = ""  # empty means <STORAGE_ROOT>/app.db
    SESSION_TTL_DAYS: int = 30
    PASSWORD_MIN_CHARS: int = 8
    PASSWORD_MAX_CHARS: int = 128
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    FREE_DAILY_LIMIT: int = 3
    PREMIUM_DAILY_LIMIT: int = 30
    REFERRAL_BONUS: int = 5
    REFERRAL_MAX_REWARDS: int = 10

    CONSENT_VERSION: str = Field(default="1", min_length=1)

    SMTP_HOST: str = ""  # empty means codes are written to the log instead of emailed
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_SECURITY: Literal["starttls", "ssl", "none"] = "starttls"
    SUPPORT_EMAIL: str = ""  # named in the email-changed notice; required with SMTP_HOST
    EMAIL_CODE_TTL_MINUTES: int = Field(default=15, ge=1)
    EMAIL_CODE_MAX_ATTEMPTS: int = Field(default=5, ge=1)
    EMAIL_RESEND_SECONDS: int = Field(default=60, ge=1)
    EMAIL_MAX_PER_HOUR: int = Field(default=5, ge=1)

    # Comma-separated in the environment; the iOS, Android and web/server client IDs.
    GOOGLE_CLIENT_IDS: Annotated[list[str], NoDecode] = []
    APPLE_BUNDLE_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY_PATH: str = ""

    CORS_ORIGINS: list[str] = ["http://localhost:8081"]

    MODEL_BACKEND: str = "stub"
    SANA_MODEL_ID: str = "Efficient-Large-Model/Sana_1600M_1024px_diffusers"
    SANA_DEVICE: str = "cpu"
    SANA_TORCH_DTYPE: str = "float32"
    SANA_NUM_INFERENCE_STEPS: int = 20
    SANA_OUTPUT_WIDTH: int = 1024
    SANA_OUTPUT_HEIGHT: int = 1024

    SAFETY_TERMS_FILE: str = "./seed/safety/blocked_terms.txt"
    SAFETY_MODEL_ID: str = "Falconsai/nsfw_image_detection"
    SAFETY_DEVICE: str = "cpu"
    SAFETY_NSFW_THRESHOLD: float = Field(default=0.7, ge=0, le=1)
    SAFETY_STUB_FLAG: Literal["none", "outputs", "all"] = "none"
    STRIKE_LIMIT: int = Field(default=3, ge=1)
    STRIKE_WINDOW_HOURS: int = Field(default=24, ge=1)
    REPORTS_PER_DAY: int = Field(default=20, ge=1)
    REPORT_RETENTION_DAYS: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def _require_sender_address_with_smtp(self) -> "Settings":
        if self.SMTP_HOST and not self.SMTP_FROM:
            raise ValueError("SMTP_FROM must be set when SMTP_HOST is set")
        if self.SMTP_HOST and not self.SUPPORT_EMAIL:
            raise ValueError("SUPPORT_EMAIL must be set when SMTP_HOST is set")
        return self

    @model_validator(mode="after")
    def _refuse_stub_flagging_with_a_real_backend(self) -> "Settings":
        if self.SAFETY_STUB_FLAG != "none" and self.MODEL_BACKEND != "stub":
            raise ValueError(
                "SAFETY_STUB_FLAG is for the stub backend only; "
                f"it is {self.SAFETY_STUB_FLAG!r} with MODEL_BACKEND {self.MODEL_BACKEND!r}"
            )
        return self

    @field_validator("GOOGLE_CLIENT_IDS", mode="before")
    @classmethod
    def _split_google_client_ids(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def _check_apple_key_settings(self) -> "Settings":
        key_settings = {
            "APPLE_TEAM_ID": self.APPLE_TEAM_ID,
            "APPLE_KEY_ID": self.APPLE_KEY_ID,
            "APPLE_PRIVATE_KEY_PATH": self.APPLE_PRIVATE_KEY_PATH,
        }
        missing = [name for name, value in key_settings.items() if not value]
        if len(missing) == len(key_settings):
            return self
        if missing:
            raise ValueError(
                "Apple key settings must be set together; missing " + ", ".join(missing)
            )
        if not self.APPLE_BUNDLE_ID:
            raise ValueError("APPLE_BUNDLE_ID must be set when the Apple key settings are set")
        self._check_apple_key_file()
        return self

    def _check_apple_key_file(self) -> None:
        path = self.APPLE_PRIVATE_KEY_PATH
        try:
            key_bytes = Path(path).read_bytes()
        except OSError as error:
            raise ValueError(
                f"APPLE_PRIVATE_KEY_PATH {path!r} cannot be read: {error}"
            ) from error
        try:
            serialization.load_pem_private_key(key_bytes, password=None)
        except (ValueError, TypeError, UnsupportedAlgorithm) as error:
            raise ValueError(
                f"APPLE_PRIVATE_KEY_PATH {path!r} is not a PEM private key: {error}"
            ) from error

    def is_google_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_IDS)

    def is_apple_configured(self) -> bool:
        return bool(self.APPLE_BUNDLE_ID)

    def is_apple_revocation_configured(self) -> bool:
        return bool(self.APPLE_PRIVATE_KEY_PATH)

    def accepted_image_types_set(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.ACCEPTED_IMAGE_TYPES.split(","))
