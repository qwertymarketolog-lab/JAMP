"""Aggregate stratified N=20 G4 telemetry without changing Gate 1."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean, quantiles, stdev


def percentile(values: list[float], p: float) -> float:
    if len(values) == 1:
        return values[0]
    return quantiles(values, n=100, method="inclusive")[int(p) - 1]


def stats(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "count": len(values),
        "min_ms": min(ordered),
        "max_ms": max(ordered),
        "mean_ms": mean(ordered),
        "p50_ms": percentile(ordered, 50),
        "p90_ms": percentile(ordered, 90),
        "p95_ms": percentile(ordered, 95),
        "p99_ms": percentile(ordered, 99),
        "sample_variance_ms2": sum((x - mean(ordered)) ** 2 for x in ordered) / (len(ordered) - 1)
        if len(ordered) > 1 else 0.0,
        "std_dev_ms": stdev(ordered) if len(ordered) > 1 else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("g4_distribution_n20.json"))
    parser.add_argument("--target-commit", required=True)
    args = parser.parse_args()

    raw = []
    for path in sorted(args.input_dir.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw.extend(payload.get("raw_observations", []))

    if len(raw) != 20:
        raise SystemExit(f"expected exactly 20 raw observations, found {len(raw)}")

    target_commits = {item.get("target_commit") for item in raw}
    if target_commits != {args.target_commit}:
        raise SystemExit(f"target commit mismatch: {sorted(target_commits)}")

    strata = {}
    for stratum in ("ubuntu-latest", "macos-latest"):
        rows = [item for item in raw if item["stratum"] == stratum]
        if len(rows) != 10:
            raise SystemExit(f"{stratum}: expected 10 observations, found {len(rows)}")
        strata[stratum] = stats([float(item["wall_ms"]) for item in rows])

    payload = {
        "target_commit": args.target_commit,
        "sampling_protocol": "N=20 Research Sampling (Not ADR-025 Arbitration)",
        "raw_observations": sorted(raw, key=lambda item: item["sample_id"]),
        "derived_stratified_stats": strata,
        "epistemic_status": "STRATIFIED DISTRIBUTION EVIDENCE",
        "gate_1_effect": "NO AUTOMATIC RECLASSIFICATION",
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
