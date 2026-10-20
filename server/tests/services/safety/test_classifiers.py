import io
import threading
import time

import pytest
from PIL import Image

from image_edit_server.services.safety.local_classifier import LocalImageClassifier
from image_edit_server.services.safety.stub_classifier import StubClassifier


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), (1, 2, 3)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_stub_scores_everything_safe_by_default():
    assert StubClassifier().score(b"anything") == 0.0


def test_stub_flags_everything_when_set_to_flag():
    assert StubClassifier(flag=True).score(b"anything") == 1.0


def test_local_classifier_picks_the_nsfw_label_score():
    seen = []

    def fake_pipeline(image):
        seen.append(image.mode)
        return [{"label": "normal", "score": 0.2}, {"label": "nsfw", "score": 0.8}]

    classifier = LocalImageClassifier("model", "cpu", classify=fake_pipeline)

    assert classifier.score(_png()) == pytest.approx(0.8)
    assert seen == ["RGB"]


def test_local_classifier_without_an_nsfw_label_raises():
    classifier = LocalImageClassifier(
        "model", "cpu", classify=lambda image: [{"label": "cat", "score": 0.9}]
    )

    with pytest.raises(ValueError, match="nsfw"):
        classifier.score(_png())


def test_local_classifier_rejects_bytes_that_are_not_an_image():
    classifier = LocalImageClassifier("model", "cpu", classify=lambda image: [])

    with pytest.raises(Exception):
        classifier.score(b"not an image")


def test_local_classifier_serialises_concurrent_calls():
    active = 0
    peak = 0
    guard = threading.Lock()

    def slow_pipeline(image):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with guard:
            active -= 1
        return [{"label": "nsfw", "score": 0.1}]

    classifier = LocalImageClassifier("model", "cpu", classify=slow_pipeline)
    data = _png()
    threads = [threading.Thread(target=classifier.score, args=(data,)) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert peak == 1


def test_local_classifier_loads_the_pipeline_lazily_with_model_and_device(monkeypatch):
    import sys
    from types import ModuleType

    calls = []
    transformers = ModuleType("transformers")
    transformers.pipeline = lambda task, model, device: calls.append((task, model, device)) or (
        lambda image: [{"label": "nsfw", "score": 0.3}]
    )
    monkeypatch.setitem(sys.modules, "transformers", transformers)

    classifier = LocalImageClassifier("some/model", "cpu")

    assert calls == [("image-classification", "some/model", "cpu")]
    assert classifier.score(_png()) == pytest.approx(0.3)
