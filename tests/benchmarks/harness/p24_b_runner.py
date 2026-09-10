"""P24-B orchestrator for single-factor ablation against a frozen baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tests.benchmarks.harness.orchestrator import run_benchmark_cycle
from tests.benchmarks.harness.p24_b_ablation import AblationRegistry
from tests.benchmarks.harness.p24_b_controls import evaluate_f6_semantic_gate
from tests.benchmarks.harness.p24_b_metrics import classify_ablation

FACTORS = ("F1", "F2", "F3", "F4", "F5", "F6")


def run_p24_b_experiment(factor_id: str, baseline_payload: dict[str, Any]) -> dict[str, Any]:
    if factor_id not in FACTORS:
        raise ValueError(f"Unknown factor ID: {factor_id}")

    if factor_id == "F6":
        control = run_benchmark_cycle(ctx_override={})
        gate_pass, gate_details = evaluate_f6_semantic_gate(baseline_payload, control)
        return {
            "protocol": "P24-B",
            "factor": "F6",
            "semantic_gate_pass": gate_pass,
            "gate_details": gate_details,
            "raw_payload": control,
            "metrics": classify_ablation("F6", baseline_payload, control),
        }

    intervention = AblationRegistry.get_intervention(factor_id)
    context = intervention({})
    result = run_benchmark_cycle(ctx_override=context)
    return {
        "protocol": "P24-B",
        "factor": factor_id,
        "raw_payload": result,
        "metrics": classify_ablation(factor_id, baseline_payload, result),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--factor", choices=FACTORS, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    result = run_p24_b_experiment(args.factor, baseline)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
