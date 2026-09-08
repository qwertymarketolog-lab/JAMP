# JAMP Milestone Matrix

Status is evidence-based. A milestone is not declared GREEN without actual telemetry.

| Milestone | Status | Evidence / boundary |
|---|---|---|
| P16 | 🟢 CLOSED | Causal Event DAG, deterministic causal ordering, replay/time travel, Vector Clock and SHA-256 integrity. Mainline CI validated the milestone. |
| P17.1 | 🟢 CLOSED | Stateless trajectory/outcome evaluator; readonly registry boundary; deterministic causal-efficiency scoring. 62/62 tests. |
| P17.2 | 🟢 CLOSED | Cross-session pattern index; deterministic ranking; digest isolation; anti-pattern separation. Commit `07420aee`. 72 tests. |
| P17.3 | 🟢 CLOSED | Dynamic policy adaptor with positive exploration floor, fixed total weight and deterministic pure update. CI Run #95, 78/78. |
| P17.4 | 🟢 CLOSED | Immutable PolicyUpdateEvent, strict causal parent validation, tamper/divergence detection and deterministic replay. CI Run #101, 85/85. |
| P17.5 | 🟢 CLOSED | Search boundary consumes policy without recalculating it; deterministic trajectory generation, causal attribution, replay verification and exploration floor. CI Run #108. |
| P17.6 | 🟢 CLOSED | Closed-loop deterministic experiment, canonical report, SHA-256 report digest, policy differentiation and replay verification. |
| P18.1.2 | 🟢 CLOSED | Experiment Registry bridge. Commit `aa27c651e56d1b56c451dbf41b024f0f81bf0041`, CI Run #135. |
| P18.2 | 🟢 CLOSED | Task-family isolation and zero-transfer default. 125+ tests and adversarial isolation vectors validated. |
| P18.3 | 🟢 CLOSED | Controlled cross-task pattern transfer with explicit authorization, source/target integrity, no shared references and provenance. Production commit `a68bd08b...`, CI Run #141: 134 passed + P17.6 report success. |
| **P18.4** | **🔴 PENDING VERIFIED CI** | Causal-necessity ablation. Production guardrail is locked. Exact target SHA `7b717a8dea269bc5c33d9c128634f55c0bad27b0`. Original target CI Run #165 (`34212659566`) had 139 passed / 1 failed because the test fixture used a mismatched authorization source family and never reached the intended PermissionError branch. Test-only correction must be pushed and revalidated. |

## P18.4 required evidence

The following four observations are required before P18.4 can be marked GREEN:

1. **Baseline:** all guardrails enabled and full suite passes.
2. **Authorization ablation:** authorization disabled permits the otherwise unauthorized transfer and the breach is observable.
3. **Isolation ablation:** isolation disabled permits a shared mutable reference and the breach is observable.
4. **Digest ablation:** digest validation disabled permits tampered source material and the breach is observable.

The P18.4 production guardrail must remain unchanged. Only the frozen test harness may be corrected to reach the intended authorization branch.
