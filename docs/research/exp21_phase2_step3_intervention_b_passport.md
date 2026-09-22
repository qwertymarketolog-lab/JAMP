# Experiment Passport: Intervention B (Refined Scope)

- Target: `ObservationAdjacencyGraph.reachable()`
- Hypothesis: Replacing `for target in adj[node]:` with indexed `while i < len(adj_node):` reduces traversal micro-overhead.
- Single Factor Constraint: Zero modifications to deque, frontier/queue semantics, visited set, adjacency container structure, or I/O contracts.
- Baseline SHA: `29ba828f7cea6e19b6a9a40f5dd9f35952c4959e`
- Evaluation: N ≥ 11 paired G4 runs (20,000 edges = 10,000 chain + 10,000 offset), metric ΔT = median(B) - median(Control) < 0.
- Falsification: ΔT ≥ 0 or non-convergent dispersion → FALSIFIED for Intervention B.
- Positive boundary: ΔT < 0 is attributed strictly to the `adjacency_iteration` mechanism in `reachable()`; it is not evidence of a global G4 root cause.
- Frozen Core invariant: Δ `src/jamp` = 0.
- Runner policy: telemetry/descriptive output only; no automatic scientific verdict.
- Provenance rule: implementation must remain on the isolated branch `research/exp21-phase2-step3-intervention-b` and target the recorded baseline only.
