#!/usr/bin/env python3
"""Validate JAMP 2D latency taxonomy against R28-R31 Laguna raw evidence."""
import json, sys
from pathlib import Path

try:
    import jsonschema
except ImportError as exc:
    raise SystemExit("jsonschema is required") from exc

SCHEMA = Path("schemas/jamp_taxonomy_contract.json")

def classify(t_gen, t_overhead):
    # Fail closed: missing backend/generation evidence plus >100 s wall overhead
    # is a transport-stall classification, not a fabricated generation value.
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
    jsonschema.Draft7Validator(schema).validate(record)
    expected = classify(record["metrics"]["t_gen_sec"], record["metrics"]["t_overhead_sec"])
    if record["classification"] != expected:
        raise ValueError(f'{record["trace_id"]}: classification={record["classification"]}, expected={expected}')
    if record["root_cause"] not in {"UNKNOWN", "UNPROVEN"}:
        raise ValueError(f'{record["trace_id"]}: root_cause must remain epistemically unresolved')
    
def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate_jamp_taxonomy.py <normalized-traces.json>")
    data = json.loads(Path(sys.argv[1]).read_text())
    schema = json.loads(SCHEMA.read_text())
    traces = data["traces"]
    if len(traces) != 22:
        raise SystemExit(f"expected 22 traces, got {len(traces)}")
    for trace in traces:
        validate_record(trace, schema)
    counts = {}
    for trace in traces:
        counts[trace["classification"]] = counts.get(trace["classification"], 0) + 1
    print(json.dumps({"validated": len(traces), "classification_counts": counts, "status": "PASS"}, sort_keys=True))
if __name__ == "__main__":
    main()
