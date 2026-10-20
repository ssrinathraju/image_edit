from __future__ import annotations

FLAGGED_SCORE = 1.0
SAFE_SCORE = 0.0


class StubClassifier:
    """Scores everything as safe, or everything as flagged, for development and tests."""

    def __init__(self, flag: bool = False) -> None:
        self._flag = flag

    def score(self, image_bytes: bytes) -> float:
        return FLAGGED_SCORE if self._flag else SAFE_SCORE
