"""Read-only adapter for the verified EXP-28 finite observation dataset."""

from __future__ import annotations

from typing import Any

from tests.research.exp28.test_real_millennium_input import OBSERVATIONS

SOURCE_REF_PREFIX = "exp28:zero_index="


def load_exp28_observations() -> tuple[dict[str, Any], ...]:
    """Return a detached, read-only view of the EXP-28 observations."""
    return tuple(
        {
            "zero_index": observation["zero_index"],
            "real_part": observation["real_part"],
            "imag_part": observation["imag_part"],
            "metadata": dict(observation["metadata"]),
        }
        for observation in OBSERVATIONS
    )


def source_ref(zero_index: int) -> str:
    return f"{SOURCE_REF_PREFIX}{zero_index}"
