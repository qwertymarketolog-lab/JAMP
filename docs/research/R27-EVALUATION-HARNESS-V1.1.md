# R27 Evaluation Harness v1.1

Implements PR-EVAL-PARAM-v1 and R27 Evaluation Contract v1.1.

- Frozen inference: temperature=0, top_p=1.0, max_tokens=256, stream=false, timeout=30s.
- PARAM_ACCEPTED is required for runtime PASS and R28 candidacy.
- PARAM_TRUNCATED and PARAM_UNRESOLVED are fail-closed as INCONCLUSIVE.
- PARAM_REJECTED is CONTRACT_VIOLATION.
- E01-E07 are deterministic predicates.
- E08 remains provenance-only.
- No silent retry with alternate parameter names.
- CI validates the deterministic contract; --execute is opt-in for real provider calls.
- Frozen Core and committed R27 provenance are read-only inputs.
