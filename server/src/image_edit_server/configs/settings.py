from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    CORS_ORIGINS: list[str] = ["http://localhost:8081"]

    MODEL_BACKEND: str = "stub"
    SANA_MODEL_ID: str = "Efficient-Large-Model/Sana_1600M_1024px_diffusers"
    SANA_DEVICE: str = "cpu"
    SANA_TORCH_DTYPE: str = "float32"
    SANA_NUM_INFERENCE_STEPS: int = 20
    SANA_OUTPUT_WIDTH: int = 1024
    SANA_OUTPUT_HEIGHT: int = 1024

    def accepted_image_types_set(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.ACCEPTED_IMAGE_TYPES.split(","))
