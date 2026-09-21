from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def derive_verdict(matrix: Iterable[Mapping[str, Any]]) -> str:
    """Keep R0 conservative: federation evidence alone never becomes SUPPORTED."""
    for row in matrix:
        if row.get("classification") == "CONFLICT":
            return "INCONCLUSIVE"
    return "INCONCLUSIVE"
