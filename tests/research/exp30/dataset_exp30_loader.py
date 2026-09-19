"""Read-only EXP-30 acquisition of the first ten non-trivial zeta zeros."""

from __future__ import annotations

from typing import Any

import mpmath

PRECISION_DPS = 30
ZERO_INDICES = tuple(range(1, 11))
SOURCE_REF_PREFIX = "exp30:zero_index="


def load_exp30_observations() -> tuple[dict[str, Any], ...]:
    """Acquire a detached finite dataset at fixed precision."""
    with mpmath.workdps(PRECISION_DPS):
        return tuple(
            {
                "zero_index": index,
                "real_part": str(mpmath.re(mpmath.zetazero(index))),
                "imag_part": str(mpmath.im(mpmath.zetazero(index))),
                "metadata": {
                    "acquisition_method": "mpmath.zetazero",
                    "precision_dps": PRECISION_DPS,
                },
            }
            for index in ZERO_INDICES
        )


def source_ref(zero_index: int) -> str:
    return f"{SOURCE_REF_PREFIX}{zero_index}"
