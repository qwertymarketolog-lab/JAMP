"""Isolated factor intervention wrappers for P24-B (F1-F5)."""
from __future__ import annotations

from typing import Any, Callable

Context = dict[str, Any]
Intervention = Callable[[Context], Context]


class AblationRegistry:
    """Map one P24-B factor to exactly one harness intervention."""

    _INTERVENTIONS: dict[str, Intervention] = {}

    @classmethod
    def get_intervention(cls, factor_id: str) -> Intervention:
        try:
            return cls._INTERVENTIONS[factor_id]
        except KeyError as exc:
            raise ValueError(f"Unknown factor ID: {factor_id}") from exc

    @staticmethod
    def _f1_lineage_neutralize(ctx: Context) -> Context:
        result = dict(ctx)
        result["lineage_override"] = None
        return result

    @staticmethod
    def _f2_causal_bypass(ctx: Context) -> Context:
        result = dict(ctx)
        result["causal_chain_override"] = []
        return result

    @staticmethod
    def _f3_verification_disable(ctx: Context) -> Context:
        result = dict(ctx)
        result["skip_verification"] = True
        return result

    @staticmethod
    def _f4_scoring_suppress(ctx: Context) -> Context:
        result = dict(ctx)
        result["skip_scoring"] = True
        return result

    @staticmethod
    def _f5_calibration_bypass(ctx: Context) -> Context:
        result = dict(ctx)
        result["skip_calibration"] = True
        return result


AblationRegistry._INTERVENTIONS = {
    "F1": AblationRegistry._f1_lineage_neutralize,
    "F2": AblationRegistry._f2_causal_bypass,
    "F3": AblationRegistry._f3_verification_disable,
    "F4": AblationRegistry._f4_scoring_suppress,
    "F5": AblationRegistry._f5_calibration_bypass,
}
