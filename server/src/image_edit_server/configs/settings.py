from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="IMAGE_EDIT_")

    STORAGE_ROOT: str = "./storage"
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_FACES: int = 4
    MIN_FACES: int = 1
    MAX_PROMPT_CHARS: int = 500
    JOB_CONCURRENCY: int = 1
    OUTPUT_RETENTION_HOURS: int = 24
    ACCEPTED_IMAGE_TYPES: str = "image/jpeg,image/png,image/webp"

    MODEL_BACKEND: str = "stub"
    SANA_MODEL_ID: str = "Efficient-Large-Model/Sana_1600M_1024px_diffusers"
    SANA_DEVICE: str = "cpu"
    SANA_TORCH_DTYPE: str = "float32"
    SANA_NUM_INFERENCE_STEPS: int = 20
    SANA_OUTPUT_WIDTH: int = 1024
    SANA_OUTPUT_HEIGHT: int = 1024

    def accepted_image_types_set(self) -> frozenset[str]:
        return frozenset(t.strip() for t in self.ACCEPTED_IMAGE_TYPES.split(","))
