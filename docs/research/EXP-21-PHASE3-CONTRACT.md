# EXP-21 Phase 3 — CPU topology placement

Contract: EXP-21-PHASE3-TOPOLOGY-V1.

- N = 30 paired observations.
- Canonical workload: EXP-21-PHASE0-G4-CANONICAL-V1.
- Workload definition hash: f8875a20af579bd102afaf064dbcc435cc3e6a4b82e2b28829af9ba4b2072f92.
- Paired Wilcoxon signed-rank, alpha = 0.01.
- Treatment is a verified SMT-sibling CPU relative to control.
- Every observation must prove CPU affinity and Linux topology from sysfs.
- Missing or ambiguous topology is INCONCLUSIVE.
- No production code is modified; src/jamp/run.py remains Frozen Core.

A supported effect establishes only the effect of this topology intervention. It does not establish hypervisor or host scheduling as the root cause.

Artifact: artifacts/research/exp21_phase3_topology_results.json
