# EXP-19 CI friction profile

Status: research-only diagnostic record.

## Scope

This document records reproducible CI friction observed while validating satellite research PRs against the existing EXP-19 large-graph performance guard.

It does not change the EXP-19 threshold, workflow configuration, production/runtime code, or Frozen Core.

## Evidence

The affected guard is:

`tests/research/exp19/test_adjacency_graph.py::test_g4_large_graph_is_linear_scale`

The guard asserts an elapsed-time limit of 15 ms for the measured graph operations.

For PR #99, commit `0c0dc2a1ec715f0ea07323cbcaa284a06b149138`, the Developer Quality workflow was run twice:

- Attempt 1, DQ run `35361662299`: the full suite reported `1436 passed, 1 failed`; the EXP-19 guard measured approximately `0.027812824 s`.
- Attempt 2, the isolated DQ rerun of the same workflow: the full suite again reported `1436 passed, 1 failed`; the EXP-19 guard measured `0.029288530 s`.

In both attempts, the failing test was the same EXP-19 guard. The EXP-22 atomicity tests did not produce a failure.

The EXP-19 diagnostic evidence merged to `main` at `60069dc5f60198f665d48b586ea2da87097fd0bd` records increasing graph-operation timings across the tested 5k–40k edge range. That diagnostic supports continued performance investigation, but does not by itself establish a universal complexity bound or identify a single causal mechanism for the CI slowdown.

## Classification

Current evidence supports the following limited classification:

- The 15 ms EXP-19 guard is reproducibly exceeded on the GitHub Actions runner for the tested PR #99 DQ suite.
- The failure persisted across a direct DQ rerun with the same PR commit.
- The observed values are approximately 28–29 ms in these two attempts.
- The evidence is insufficient to attribute the slowdown uniquely to runner jitter, garbage collection, virtualization, or any other single cause.

Therefore this record is a **persistent CI friction observation**, not a root-cause claim.

## Architectural boundary

No changes are made here to:

- `src/jamp` / Frozen Core;
- PR #96;
- PR #99;
- the EXP-19 15 ms threshold;
- GitHub Actions workflow configuration;
- production/runtime behavior.

The purpose is only to preserve the measured evidence and prevent the unrelated EXP-19 guard failure from being misclassified as an EXP-22 atomicity assertion failure.

## Next diagnostic boundary

Any investigation of the cause or any proposal to alter the EXP-19 performance guard must be performed as a separate research/diagnostic change with its own evidence. This document alone does not authorize changing the threshold.
