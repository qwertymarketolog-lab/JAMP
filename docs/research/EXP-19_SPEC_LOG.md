# EXP-19 — Observation Adjacency & Canonical Topology

Status: SPEC/IMPLEMENTATION STARTED
Base: 8bfd0821c544b1f1d733721a34cd1ccbf0f312da
Branch: research/exp19-adjacency

Research boundary:
- research/exp19/ contains the experimental operator.
- tests/research/exp19/ contains the EXP-19 contract tests.
- src/jamp and production/runtime remain untouched.

Canonical edge identity:
compute_edge_hash(source_id, target_id, relation_type, params)
uses JSON sort_keys=True, compact separators, ensure_ascii=False, followed by SHA-256.

Structural invariants:
- directed edges use distinct source and target identifiers;
- self-loops raise the exact required ValueError;
- ObservationRelation is frozen/immutable;
- edge_hash is deterministic and endpoint-direction sensitive;
- acyclicity is validated only over the supplied relation subset;
- no import from JAMP core/runtime is permitted.

Coverage target:
- A Determinism: 20 tests x 50 deterministic cases = 1000 repetitions
- B Directedness: 20 tests
- C Self-loop: 20 tests
- D Param Sensitivity: 25 tests
- E DAG/Subgraph: 20 tests
- F Isolation/Delta: 15 tests
- Total target: >=120 tests.

Execution note:
This step creates the research artifact and test suite. CI is the authoritative
execution environment for repository evidence; no VERIFIED/CLOSED status is
assigned until the required CI gates pass on the exact HEAD.
