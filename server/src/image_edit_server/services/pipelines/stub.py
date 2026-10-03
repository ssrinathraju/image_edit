from __future__ import annotations

from pathlib import Path

from PIL import Image


class StubPipeline:
    """Returns a solid-color PNG derived deterministically from the prompt."""

    async def run(self, faces: list[Path], prompt: str, output_path: Path) -> Path:
        color = self._prompt_to_color(prompt)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1024, 1024), color=color)
        img.save(output_path, format="PNG")
        return output_path

    @staticmethod
    def _prompt_to_color(prompt: str) -> tuple[int, int, int]:
        h = hash(prompt) & 0xFFFFFF
        return (h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF
