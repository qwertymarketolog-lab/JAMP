"""Fixed real-world-shaped text fixtures; no network access."""
from __future__ import annotations

from .text_adapter import TextObservation

FIXTURES = (
    TextObservation(
        source_ref="fixture:text:001",
        raw_text="  Hello,\u00a0world!\\n\nThis is a source observation.  ",
        metadata={"fixture": "exp20", "kind": "article_excerpt"},
    ),
    TextObservation(
        source_ref="fixture:text:002",
        raw_text="Cafe\u0301   au   lait",
        metadata={"fixture": "exp20", "kind": "unicode_normalization"},
    ),
)
