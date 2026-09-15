# Q3b: neutral Artifact Contract v0

## Q3b.1 — Specification

typed metadata: `artifact_version`, `adapter`, `adapter_contract` (optional),
`steps`, `iterations`, `stop_reason`

opaque payload: `final_state`, `provenance`

versioning: `artifact_version` independent of `run_contract_version`

Not claimed: third-domain neutrality, production exporter transfer,
cross-domain semantic equivalence of provenance

## Q3b.2 — Implementation evidence

Commit: `4b08da31b1f451b0e573060760ae5b99766f65a9`

Working tree: clean at execution

Command:

```text
PYTHONPATH=src:. python -m pytest -q tests/research/test_artifact_v0.py
```

Result: `2 passed in 0.29s`

Verified: JSON round-trip; two distinct payload forms;
`adapter_contract` as independent optional field

Core: `src/jamp/run.py` unchanged (SHA `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` before and after)

## Q3b.3 — Production integration

Status: pending
