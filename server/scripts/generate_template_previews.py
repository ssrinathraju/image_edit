"""Generate template preview images (512x512 WebP) for the seed catalog.

Run from server/:
    uv run python scripts/generate_template_previews.py --placeholder
    uv run --group ml python scripts/generate_template_previews.py [--force] [--only ID]
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

from image_edit_server.configs.settings import Settings
from image_edit_server.schemas.template import Template

logger = logging.getLogger("generate_template_previews")

PREVIEW_SIZE = 512
WEBP_QUALITY = 80
TITLE_WRAP_CHARS = 18
TEXT_COLOR = (255, 255, 255)


def load_templates(templates_dir: Path) -> list[Template]:
    raw = json.loads((templates_dir / "catalog.json").read_text(encoding="utf-8"))
    return [Template.model_validate(entry) for entry in raw]


def _color_for(template_id: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(template_id.encode("utf-8")).digest()
    return (40 + digest[0] % 140, 40 + digest[1] % 140, 40 + digest[2] % 140)


def write_placeholder(template: Template, destination: Path) -> None:
    image = Image.new("RGB", (PREVIEW_SIZE, PREVIEW_SIZE), _color_for(template.id))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=36)
    text = "\n".join(textwrap.wrap(template.title, TITLE_WRAP_CHARS))
    draw.multiline_text(
        (PREVIEW_SIZE / 2, PREVIEW_SIZE / 2),
        text,
        fill=TEXT_COLOR,
        font=font,
        anchor="mm",
        align="center",
    )
    image.save(destination, format="WEBP", quality=WEBP_QUALITY)


def _select(
    templates: list[Template], previews_dir: Path, force: bool, only: Optional[str]
) -> list[Template]:
    chosen = [t for t in templates if only is None or t.id == only]
    if only is not None and not chosen:
        raise SystemExit(f"no template with id '{only}'")
    if force or only is not None:
        return chosen
    return [t for t in chosen if not (previews_dir / t.preview).exists()]


def generate_placeholders(
    templates_dir: Path, force: bool = False, only: Optional[str] = None
) -> list[str]:
    previews_dir = templates_dir / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for template in _select(load_templates(templates_dir), previews_dir, force, only):
        write_placeholder(template, previews_dir / template.preview)
        written.append(template.id)
    return written


def generate_with_sana(
    templates_dir: Path, force: bool = False, only: Optional[str] = None
) -> list[str]:
    from image_edit_server.services.pipelines.sana import SanaPipeline

    previews_dir = templates_dir / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    pending = _select(load_templates(templates_dir), previews_dir, force, only)
    if not pending:
        return []

    pipeline = SanaPipeline(Settings())
    written: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        for template in pending:
            logger.info("Generating preview for %s", template.id)
            raw_path = Path(tmp) / f"{template.id}.png"
            asyncio.run(pipeline.run([], template.prompt, raw_path))
            with Image.open(raw_path) as raw:
                resized = raw.convert("RGB").resize((PREVIEW_SIZE, PREVIEW_SIZE))
            resized.save(previews_dir / template.preview, format="WEBP", quality=WEBP_QUALITY)
            written.append(template.id)
    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--templates-dir", type=Path, default=Path(Settings().TEMPLATES_DIR))
    parser.add_argument("--placeholder", action="store_true", help="Pillow-only solid-color previews")
    parser.add_argument("--force", action="store_true", help="Regenerate existing previews")
    parser.add_argument("--only", metavar="ID", help="Generate a single template")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    generate = generate_placeholders if args.placeholder else generate_with_sana
    written = generate(args.templates_dir, force=args.force, only=args.only)
    logger.info("Wrote %d preview(s): %s", len(written), ", ".join(written) or "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
