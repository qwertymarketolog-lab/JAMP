# EXP-22 Phase 1 — Boundary-Preserving Operation Decomposition Contract

Status: OPEN / CONTRACT-ONLY
Base commit: 98992070b59450a760da63544164af94a6520914

Purpose: descriptive decomposition of the VERIFIED Phase 0 timed region into its two existing operations: A=graph.is_acyclic(), B=graph.reachable("0"). No causal verdict and no G4 clearance.

Locked invariants:
- src/jamp/run.py byte-for-byte unchanged; Frozen Core blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
- G4 threshold remains T_wall <= 15.000 ms.
- workload_spec_id = EXP-21-PHASE0-G4-CANONICAL-V1.
- workload_definition_hash = f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92.
- exact target_commit must equal checked-out HEAD; synthetic merge SHAs forbidden.

Design:
- N=30 complete paired repetitions.
- Each repetition measures three modes in deterministic shuffled order: combined (exact Phase 0 A then B), acyclic_only (A), reachable_only (B).
- Workload construction, imports, validation, logging and serialization remain outside timed regions.
- Timing APIs remain time.perf_counter_ns and time.process_time_ns.

Terminal meaning:
- VERIFIED = all 30 repetitions complete, all identity/boundary checks pass, and artifact validates.
- INCONCLUSIVE = any required evidence is missing, invalid or contradictory.
- No fallback, imputation, synthetic observation or repair.

Required artifact: artifacts/research/exp22_phase1_boundary_decomposition.json

Interpretation boundary:
- OBSERVED: per-mode timing, environment, workload identity.
- VERIFIED: integrity/completeness only.
- INFERRED: none.
- UNKNOWN: causal explanation of G4 latency and whether either isolated operation is a root cause.

State: Phase 0 VERIFIED (run 35800042542, job 106989440071, artifact 10726090268); Phase 1 OPEN; G4 Gate 1 CONTRACT_VIOLATION; root cause UNKNOWN; Frozen Core LOCKED.