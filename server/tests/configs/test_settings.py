import pytest
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


def test_env_override(monkeypatch):
    monkeypatch.setenv("IMAGE_EDIT_MAX_FACES", "2")
    s = Settings()
    assert s.MAX_FACES == 2


def test_accepted_image_types_set():
    s = Settings()
    types = s.accepted_image_types_set()
    assert "image/jpeg" in types
    assert "image/png" in types
    assert "image/webp" in types
