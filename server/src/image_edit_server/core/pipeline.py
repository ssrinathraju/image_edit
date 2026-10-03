from __future__ import annotations

from pathlib import Path
from typing import Protocol


class GenerationPipeline(Protocol):
    async def run(self, faces: list[Path], prompt: str, output_path: Path) -> Path:
        """Run the generation pipeline and write the result to output_path. Return output_path."""
        ...
