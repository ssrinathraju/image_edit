from io import BytesIO

from PIL import Image

from image_edit_server.core.template_preview import normalise_preview


def _jpeg_with_orientation(orientation: int) -> bytes:
    image = Image.new("RGB", (200, 100), (255, 0, 0))
    image.paste((0, 0, 255), (100, 0, 200, 100))
    exif = Image.Exif()
    exif[0x0112] = orientation
    out = BytesIO()
    image.save(out, format="JPEG", quality=95, exif=exif)
    return out.getvalue()


def test_a_photo_tagged_sideways_is_stored_upright():
    stored = Image.open(BytesIO(normalise_preview(_jpeg_with_orientation(6)))).convert("RGB")

    # Orientation 6 turns the left half to the top: red above, blue below.
    assert stored.getpixel((256, 20))[0] > 200
    assert stored.getpixel((256, 490))[2] > 200


def test_an_untagged_photo_is_left_as_it_is():
    stored = Image.open(BytesIO(normalise_preview(_jpeg_with_orientation(1)))).convert("RGB")

    assert stored.getpixel((20, 256))[0] > 200
    assert stored.getpixel((490, 256))[2] > 200
