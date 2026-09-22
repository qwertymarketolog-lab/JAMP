# Phase 2 Closure Record: EXP21 G4 Traversal Diagnostic

## 1. Verified Evidence & References

- **Step 4 (Dispersion Diagnostic):** PR #141 (archival). Diagnostic artifact `10680173546` recorded an N=100 start-node sample with p50 edge inspections = 102 and max = 20,000.
- **Step 5 (Anchor Validation):** PR #142, HEAD `d5a4737728c6eba84444e5e3acb423f57538f4a0`. CI Run `35707357657`, Job `106679397121`, completed successfully.

## 2. Frozen Core Invariant

- **Status:** `LOCKED`
- Phase 2 made no changes under `src/jamp`; the compare from `research/exp21-multi-ai-federation-r0` to the Step 5 HEAD contains only the Step 5 workflow and research harness policy.
- Production runtime impact from the Phase 2 closure changes: `0`.

## 3. Step 5 Anchor Contract

- The G4 CI harness uses the fixed architectural target `CANONICAL_G4_FIXED_ANCHOR_NODE = 0`.
- The anchor is structural and deterministic; it is not derived from telemetry, p50, dispersion, or post-hoc sample selection.
- Step 5 validates the anchor policy and Frozen Core boundary; it does not itself measure G4 latency.

## 4. Causal Scope

- **Verified within the Phase 2 evidence boundary:** observed G4 variance is associated with start-node-dependent reachability/topology, while the tested micro-optimization interventions did not remove the observed variance.
- **Not established by Step 5 alone:** a universal causal attribution excluding every possible implementation or runtime factor. Phase 2 therefore records the causal conclusion only within the tested intervention and workload scope.
- Interventions A and B did not provide evidence authorizing a production micro-optimization change.

## 5. Algorithmic Intervention Status

- **Status:** `NOT_AUTHORIZED_BY_PHASE2`
- The observed worst-case reachability cost (approximately 20,000 edge inspections in the diagnostic workload) is compatible with the intended component-traversal semantics.
- Phase 2 authorizes no production algorithmic change to mitigate that structural behavior.

## 6. Phase 3 Status

- **Status:** `PROPOSAL_ONLY`
- Any architectural mitigation, including reachability caching, memoization, or an exploration bound, must be separately pre-registered and evaluated on its own evidence.
- No Phase 3 intervention is authorized by this closure record.

## 7. Closure Boundary

Phase 2 is closed as a diagnostic phase. Closure records the verified harness boundary, evidence scope, and non-authorization of production intervention. It does not claim that a future algorithmic proposal is unnecessary; that question belongs to a separate Phase 3 research decision.
