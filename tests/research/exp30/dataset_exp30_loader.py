"""Read-only EXP-30 reference dataset for the first ten non-trivial zeta zeros."""

from __future__ import annotations

from typing import Any

PRECISION_DPS = 30
ZERO_INDICES = tuple(range(1, 11))
SOURCE_REF_PREFIX = "exp30:zero_index="

# Finite reference observations acquired with mpmath.zetazero at 30 dps.
# Stored here so CI does not depend on mpmath at test time.
EXP30_STATIC_ZEROS: tuple[dict[str, Any], ...] = (
    {"index": 1, "real": "0.5", "imag": "14.134725141734693790", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 2, "real": "0.5", "imag": "21.022039638771554992", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 3, "real": "0.5", "imag": "25.010857580145688763", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 4, "real": "0.5", "imag": "30.424876125859513210", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 5, "real": "0.5", "imag": "32.935061587739189690", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 6, "real": "0.5", "imag": "37.586178158825671257", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 7, "real": "0.5", "imag": "40.918719012147495187", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 8, "real": "0.5", "imag": "43.327073280914999519", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 9, "real": "0.5", "imag": "48.005150881167159727", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
    {"index": 10, "real": "0.5", "imag": "49.773832477672302181", "acquisition_method": "mpmath.zetazero", "precision_dps": 30},
)


def load_exp30_observations() -> tuple[dict[str, Any], ...]:
    """Return the detached finite reference dataset."""
    return tuple(
        {
            "zero_index": item["index"],
            "real_part": item["real"],
            "imag_part": item["imag"],
            "metadata": {
                "acquisition_method": item["acquisition_method"],
                "precision_dps": item["precision_dps"],
            },
        }
        for item in EXP30_STATIC_ZEROS
    )


def source_ref(zero_index: int) -> str:
    return f"{SOURCE_REF_PREFIX}{zero_index}"
