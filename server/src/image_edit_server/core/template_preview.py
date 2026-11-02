from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_PREVIEW_BYTES = 2 * 1024 * 1024
PREVIEW_SIZE = 512
PREVIEW_WEBP_QUALITY = 80
ACCEPTED_PREVIEW_FORMATS = ("PNG", "JPEG", "WEBP")


class InvalidPreview(Exception):
    """Raised when an uploaded preview is too large or is not a decodable PNG, JPEG or WebP."""


def normalise_preview(data: bytes) -> bytes:
    """Decode an uploaded image and return it as a centre-cropped 512x512 WebP."""
    if len(data) > MAX_PREVIEW_BYTES:
        raise InvalidPreview(f"the preview is larger than {MAX_PREVIEW_BYTES // (1024 * 1024)} MB")
    try:
        _check_format_and_size(data)
        with Image.open(BytesIO(data)) as image:
            image.load()
            upright = ImageOps.exif_transpose(image)
            rgb = upright.convert("RGB")
    except InvalidPreview:
        raise
    except (
        UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError
    ) as error:
        raise InvalidPreview("the preview is not a decodable PNG, JPEG or WebP image") from error
    square = ImageOps.fit(rgb, (PREVIEW_SIZE, PREVIEW_SIZE), Image.Resampling.LANCZOS)
    out = BytesIO()
    square.save(out, format="WEBP", quality=PREVIEW_WEBP_QUALITY)
    return out.getvalue()


def _check_format_and_size(data: bytes) -> None:
    # The decoded format decides, never the file name or the Content-Type.
    with Image.open(BytesIO(data)) as probe:
        if probe.format not in ACCEPTED_PREVIEW_FORMATS:
            raise InvalidPreview("the preview must be a PNG, JPEG or WebP image")
        pixel_limit = Image.MAX_IMAGE_PIXELS
        if pixel_limit is not None and probe.width * probe.height > pixel_limit:
            raise InvalidPreview("the preview has too many pixels")
        probe.verify()
