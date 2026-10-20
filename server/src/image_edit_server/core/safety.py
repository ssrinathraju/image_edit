from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable, Protocol

LETTER_SWAPS = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_SINGLE_LETTER_RUN = re.compile(r"(?<![a-z])[a-z](?: [a-z])+(?![a-z])")
COMMENT_PREFIX = "#"


class ImageClassifier(Protocol):
    def score(self, image_bytes: bytes) -> float:
        """Return the probability in [0, 1] that the image is not safe for work."""
        ...


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, reverse letter swaps, and collapse non-letters to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    swapped = stripped.lower().translate(LETTER_SWAPS)
    letters_only = "".join(ch if ch.isalpha() else " " for ch in swapped)
    return " ".join(letters_only.split())


def _join_single_letter_runs(normalized: str) -> str:
    return _SINGLE_LETTER_RUN.sub(lambda match: match.group(0).replace(" ", ""), normalized)


class TermMatcher:
    """Whole-word and whole-phrase matching of blocked terms against free text."""

    def __init__(self, terms: Iterable[str]) -> None:
        normalized = {normalize_text(term) for term in terms}
        normalized.discard("")
        self._terms = frozenset(f" {term} " for term in normalized)
        self._single_word_terms = frozenset(
            term for term in self._terms if term.strip().count(" ") == 0
        )

    def matches(self, prompt: str) -> bool:
        """True when the prompt contains any blocked term as a whole word or phrase."""
        normalized = normalize_text(prompt)
        padded = f" {normalized} "
        if any(term in padded for term in self._terms):
            return True
        joined = f" {_join_single_letter_runs(normalized)} "
        return any(term in joined for term in self._single_word_terms)


def load_terms(path: str) -> list[str]:
    """Read one term per line, skipping blanks and `#` comments; refuse an empty list."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError(f"blocked-term list {path!r} cannot be read: {error}") from error
    terms = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith(COMMENT_PREFIX)
    ]
    if not terms:
        raise ValueError(f"blocked-term list {path!r} has no terms; add at least one")
    return terms
