from __future__ import annotations

import io
import threading
from typing import Any, Callable, Optional

from PIL import Image

NSFW_LABEL = "nsfw"


def _load_transformers_pipeline(model_id: str, device: str) -> Callable[[Image.Image], list[dict]]:
    from transformers import pipeline  # type: ignore[import]  # optional `ml` group

    return pipeline("image-classification", model=model_id, device=device)


class LocalImageClassifier:
    """Scores images with a Hugging Face image-classification model that runs on this server."""

    def __init__(
        self,
        model_id: str,
        device: str,
        classify: Optional[Callable[[Image.Image], list[dict[str, Any]]]] = None,
    ) -> None:
        self._classify = classify or _load_transformers_pipeline(model_id, device)
        # Hugging Face pipelines are not guaranteed thread-safe, and the worker and
        # submit-time checks share this instance.
        self._lock = threading.Lock()

    def score(self, image_bytes: bytes) -> float:
        with Image.open(io.BytesIO(image_bytes)) as opened:
            image = opened.convert("RGB")
        with self._lock:
            predictions = self._classify(image)
        for prediction in predictions:
            if str(prediction["label"]).lower() == NSFW_LABEL:
                return float(prediction["score"])
        raise ValueError(f"classifier output has no {NSFW_LABEL!r} label")
