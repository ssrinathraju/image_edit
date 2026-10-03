import pytest
from pathlib import Path

from PIL import Image

from image_edit_server.services.pipelines.stub import StubPipeline


async def test_stub_writes_valid_png(tmp_path):
    pipeline = StubPipeline()
    out = tmp_path / "outputs" / "test.png"
    result = await pipeline.run(faces=[], prompt="a family at sunset", output_path=out)

    assert result == out
    assert out.exists()

    img = Image.open(out)
    assert img.size == (1024, 1024)
    assert img.format == "PNG"


async def test_stub_deterministic(tmp_path):
    pipeline = StubPipeline()
    prompt = "same prompt every time"
    out1 = tmp_path / "a.png"
    out2 = tmp_path / "b.png"
    await pipeline.run([], prompt, out1)
    await pipeline.run([], prompt, out2)

    assert out1.read_bytes() == out2.read_bytes()
