"""Tests for SanaPipeline — patches diffusers so no ML deps are needed."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


def _make_stubs():
    """Return (diffusers_stub, torch_stub, mock_pipeline_cls, mock_pipe_instance)."""
    diffusers = ModuleType("diffusers")
    torch = ModuleType("torch")
    torch.float32 = "float32"  # type: ignore[attr-defined]
    torch.float16 = "float16"  # type: ignore[attr-defined]
    torch.bfloat16 = "bfloat16"  # type: ignore[attr-defined]

    mock_pipe_instance = MagicMock()
    mock_pipe_instance.images = [MagicMock()]

    mock_pipeline_cls = MagicMock()
    mock_pipeline_cls.from_pretrained.return_value = MagicMock(
        to=lambda _: mock_pipe_instance
    )
    diffusers.SanaPipeline = mock_pipeline_cls  # type: ignore[attr-defined]
    return diffusers, torch, mock_pipeline_cls, mock_pipe_instance


def test_constructor_calls_from_pretrained(tmp_path):
    diffusers_stub, torch_stub, mock_cls, _ = _make_stubs()
    with patch.dict(sys.modules, {"diffusers": diffusers_stub, "torch": torch_stub}):
        if "image_edit_server.services.pipelines.sana" in sys.modules:
            del sys.modules["image_edit_server.services.pipelines.sana"]

        from image_edit_server.configs.settings import Settings
        from image_edit_server.services.pipelines.sana import SanaPipeline

        settings = Settings(SANA_MODEL_ID="test-model", SANA_DEVICE="cpu")
        SanaPipeline(settings)

    mock_cls.from_pretrained.assert_called_once()
    assert mock_cls.from_pretrained.call_args.args[0] == "test-model"


async def test_run_writes_png(tmp_path):
    diffusers_stub, torch_stub, mock_cls, mock_pipe_instance = _make_stubs()

    from PIL import Image

    real_image = Image.new("RGB", (4, 4), color=(128, 0, 0))
    mock_pipe_result = MagicMock()
    mock_pipe_result.images = [real_image]
    mock_pipe_instance.return_value = mock_pipe_result
    mock_cls.from_pretrained.return_value.to.return_value = mock_pipe_instance

    with patch.dict(sys.modules, {"diffusers": diffusers_stub, "torch": torch_stub}):
        if "image_edit_server.services.pipelines.sana" in sys.modules:
            del sys.modules["image_edit_server.services.pipelines.sana"]

        from image_edit_server.configs.settings import Settings
        from image_edit_server.services.pipelines.sana import SanaPipeline

        settings = Settings(STORAGE_ROOT=str(tmp_path))
        pipeline = SanaPipeline(settings)

        out = tmp_path / "out.png"
        result = await pipeline.run(faces=[], prompt="a sunset", output_path=out)

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0
