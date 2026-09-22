# EXP-21 Phase 3 Cache-Scope Protocol Addendum

State: QUANTITATIVE PRE-REGISTRATION LOCKED / CACHE SCOPE LOCKED

The comparative treatment uses Model 1: isolated cold-start per query. For every pre-registered N=100 start node, a fresh treatment candidate is created with an empty cache, exactly one reachability query is measured, and the candidate is discarded before the next start node. No cache state is carried between sampled nodes.

This is required for apples-to-apples comparison with the Phase 2 independent start-node dispersion sweep. Cumulative warm-state amortization is excluded from the registered experiment and cannot establish X=50% or epsilon=0%.

## Seed fixture

The exact ordered N=100 start-node sequence is frozen in tests/research/fixtures/phase2_n100_seeds.json.

Source evidence: Phase 2 Step 4 artifact 10680173546, diagnostic payload start_node_dispersion.rows, canonical G4 fixture 20,000 edges / 20,000 vertices, anchor 0.

Changing cache scope, sample sequence, sample size, workload identity, or decision thresholds after treatment results are observed is a protocol change and cannot retroactively establish the registered result.

Frozen Core remains locked: Delta(src/jamp) = 0.
