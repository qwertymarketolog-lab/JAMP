"""Two-level contract validation for P24-B intervention points."""
from __future__ import annotations

import pytest

from tests.benchmarks.harness.orchestrator import run_benchmark_cycle
from tests.benchmarks.harness.p24_b_ablation import AblationRegistry


def test_level_a_wrapper_context_modification() -> None:
    for factor in ("F1", "F2", "F3", "F4", "F5"):
        fn = AblationRegistry.get_intervention(factor)
        modified = fn({"base": True})
        assert modified != {"base": True}


@pytest.mark.parametrize(
    ("factor_id", "override_key"),
    [
        ("F1", "lineage_override"),
        ("F2", "causal_chain_override"),
        ("F3", "skip_verification"),
        ("F4", "skip_scoring"),
        ("F5", "skip_calibration"),
    ],
)
def test_level_b_orchestrator_consumption(factor_id: str, override_key: str) -> None:
    fn = AblationRegistry.get_intervention(factor_id)
    context = fn({})
    assert override_key in context
    payload = run_benchmark_cycle(ctx_override=context)
    assert payload.get("status") == "OK"
    assert override_key in payload.get("consumed_overrides", [])
