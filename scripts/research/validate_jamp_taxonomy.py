#!/usr/bin/env python3
"""Validate JAMP 2D latency taxonomy against normalized R28-R31 Laguna evidence."""

import json
import sys
from pathlib import Path

import jsonschema

SCHEMA = Path("schemas/jamp_taxonomy_contract.json")
ALLOWED_ROOT_CAUSES = {"UNKNOWN", "UNPROVEN"}


def classify(t_gen, t_overhead):
    """Apply the fail-closed JAMP taxonomy decision rule."""
    if t_overhead > 100.0 and t_gen is None:
        return "TRANSPORT_STALL"
    if t_overhead > 100.0 and t_gen is not None and t_gen <= 6.0:
        return "TRANSPORT_STALL"
    if t_gen is not None and t_gen > 5.0 and t_overhead <= 3.0:
        return "GENERATION_THROTTLED"
    if t_gen is not None and t_gen <= 5.0 and t_overhead <= 3.0:
        return "NOMINAL_BASELINE"
    return "DUAL_AXIS_DEGRADED"


def validate_record(record, schema):
    """Validate schema, decision rule, and epistemic root-cause boundary."""
    jsonschema.Draft7Validator(schema).validate(record)
    expected = classify(
        record["metrics"]["t_gen_sec"],
        record["metrics"]["t_overhead_sec"],
    )
    if record["classification"] != expected:
        raise ValueError(f"{record['trace_id']}: {record['classification']} != {expected}")
    if record["root_cause"] not in ALLOWED_ROOT_CAUSES:
        raise ValueError(f"{record['trace_id']}: root_cause must remain unresolved")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_jamp_taxonomy.py <normalized-traces.json>")

    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    traces = data["traces"]

    if len(traces) != 22:
        raise SystemExit(f"expected 22 traces, got {len(traces)}")

    for trace in traces:
        validate_record(trace, schema)

    counts = {}
    for trace in traces:
        key = trace["classification"]
        counts[key] = counts.get(key, 0) + 1

    print(
        json.dumps(
            {
                "validated": len(traces),
                "classification_counts": counts,
                "status": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
