# EXP-19 Benchmark Extraction

## Decision

EXP-19 synthetic scale timing is moved out of the blocking Developer Quality full-suite invocation into a separate diagnostic workflow.

The existing 15 ms assertion is retained unchanged in `tests/research/exp19/test_adjacency_graph.py`. The test is marked `exp19_perf`, so the blocking DQ suite excludes that marked stress benchmark while the dedicated EXP-19 workflow executes the diagnostic independently.

## Boundaries

- Frozen Core `src/jamp/run.py` remains untouched.
- Frozen Core blob remains `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- The 15 ms assertion is not recalibrated or rewritten.
- EXP-19 functional tests remain in the normal suite.
- The scale benchmark is diagnostic evidence, not a merge-blocking claim about universal complexity.
- The dedicated workflow produces a text artifact containing the measured diagnostics.
- PR #99 is not modified by this extraction.

## Diagnostic evidence

`tests/research/exp19/test_performance_diagnostic.py` already measures build, acyclic, and reachable timings at 5k, 10k, 20k, and 40k edges using repeated measurements and reports p50/p95/p99 values.

The extracted workflow runs that diagnostic independently and uploads its output as `exp19-performance-diagnostic`.

## Interpretation boundary

A successful diagnostic workflow means the diagnostic itself completed. It does not prove a universal O(V+E) bound, a fixed latency target at all scales, or a single environmental cause of timing variation.
