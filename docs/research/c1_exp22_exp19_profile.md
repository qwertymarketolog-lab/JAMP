# C1 — EXP-22 / EXP-19 Research Profile

## Scope

This document is a research-only evidence note. It records observations relevant to the
EXP-22 atomicity research vectors and the EXP-19 timing guard. It does not change runtime
semantics, the Frozen Core, the EXP-19 threshold, or any production path.

## Repository invariants

- Frozen Core: `src/jamp/run.py`
- Frozen Core blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- EXP-19 macro-gard threshold: 15 ms
- The threshold is intentionally unchanged by this artifact.
- PR #99 remains a separate research PR and is not modified by this document.

## EXP-22 observation

PR #99 (`0c0dc2a1ec715f0ea07323cbcaa284a06b149138`) contains six atomicity research
vectors covering payload identity, deterministic unchanged atomization, composite mutation,
provenance binding, transcript boundaries, and absence of semantic verdicts.

The recorded PR #99 CI attempts showed the EXP-22 test vectors passing; the blocking failure
was the pre-existing EXP-19 timing guard
`tests/research/exp19/test_adjacency_graph.py::test_g4_large_graph_is_linear_scale`.

This note records that separation explicitly:

- EXP-22 semantic/test observations: PASS on the tested vectors.
- PR #99 mandatory CI package: HOLD / NOT VERIFIED while the EXP-19 guard fails.
- No inference is made from the timing failure to semantic correctness of EXP-22.

## EXP-19 timing observations

The relevant CI runs recorded repeated failures of the same 15 ms guard on the synthetic
large-graph test, with measured elapsed times including approximately:

- 27.81 ms (PR #99 DQ attempt 1)
- 29.29 ms (PR #99 DQ attempt 2)
- 31.68 ms (PR #99 DQ attempt 3)
- 16.13 ms (post-merge CI for PR #101, first DQ attempt)

The same PR #101 DQ job subsequently passed on rerun without changing the threshold or the
test logic. This establishes observed run-to-run timing variability under the existing
guard; it does not establish a universal complexity bound or identify a single causal
mechanism.

Earlier EXP-19 diagnostic telemetry also recorded increasing build-time medians across the
tested synthetic graph sizes. Those measurements are retained as experiment observations,
not as a proof of universal O(V+E) behavior or as proof that one environmental factor is
the sole cause.

## Governance boundary

This artifact is documentation only. It intentionally does not:

- modify `src/jamp`;
- modify PR #96;
- modify PR #99;
- change the 15 ms EXP-19 threshold;
- change production/runtime behavior;
- declare PR #99 VERIFIED or CLOSED.

The next architectural decision about the EXP-19 macro-gard must remain separate from the
EXP-22 semantic evidence.
