from __future__ import annotations

import asyncio
from pathlib import Path

from image_edit_server.configs.settings import Settings

_DTYPE_MAP = {
    "float32": None,  # resolved lazily to avoid importing torch at module level
    "float16": None,
    "bfloat16": None,
}


def _resolve_dtype(dtype_str: str):
    import torch

    return {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }[dtype_str]


class SanaPipeline:
    def __init__(self, settings: Settings) -> None:
        from diffusers import SanaPipeline as _SanaPipeline  # type: ignore[import]

        dtype = _resolve_dtype(settings.SANA_TORCH_DTYPE)
        self._pipe = _SanaPipeline.from_pretrained(
            settings.SANA_MODEL_ID,
            torch_dtype=dtype,
        ).to(settings.SANA_DEVICE)
        self._settings = settings

    async def run(self, faces: list[Path], prompt: str, output_path: Path) -> Path:
        cfg = self._settings
        result = await asyncio.to_thread(
            self._pipe,
            prompt,
            num_inference_steps=cfg.SANA_NUM_INFERENCE_STEPS,
            width=cfg.SANA_OUTPUT_WIDTH,
            height=cfg.SANA_OUTPUT_HEIGHT,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.images[0].save(output_path, format="PNG")
        return output_path
