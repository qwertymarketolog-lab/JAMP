# JAMP

**Causal Experimental Architecture for Machine Discovery**

JAMP is an experimental architecture for building machine-discovery systems whose search results are reproducible, causally ordered, integrity-verifiable, and replayable.

## Core principles

- **Causal Event DAG** — decisions and observations are represented as an auditable causal history.
- **Deterministic search** — equivalent inputs produce deterministic, replayable trajectories.
- **Replay & time travel** — prior states and causal histories can be reconstructed and verified.
- **Policy learning** — search policy can adapt from evidence without mutating the causal record retroactively.
- **Task isolation** — evidence, policy and registry state are isolated by task family by default.
- **Controlled knowledge transfer** — cross-task transfer requires explicit cryptographically bound authorization and preserves provenance.
- **Causal ablation** — mechanisms are tested by removing causal guardrails, not only by comparing final scores.
- **Evidence first** — a milestone is not GREEN without observable CI telemetry and reproducible evidence.

## Research status

| Milestone | Status |
|---|---|
| P16 — Causal Event DAG, Replay & Time Travel | 🟢 CLOSED |
| P17.1 — Trajectory & Outcome Evaluator | 🟢 CLOSED |
| P17.2 — Cross-Session Pattern Index | 🟢 CLOSED |
| P17.3 — Dynamic Policy Adaptor | 🟢 CLOSED |
| P17.4 — PolicyUpdateEvent & Replay | 🟢 CLOSED |
| P17.5 — Search Boundary & Policy Integration | 🟢 CLOSED |
| P17.6 — Closed-Loop Learning Experiments | 🟢 CLOSED |
| P18.1.2 — Experiment Registry Bridge | 🟢 CLOSED |
| P18.2 — Task Family Isolation | 🟢 CLOSED |
| P18.3 — Controlled Cross-Task Pattern Transfer | 🟢 CLOSED |
| **P18.4 — Causal Necessity / Ablation** | 🔴 **PENDING VERIFIED CI** |

P18.4 is intentionally not marked GREEN until the exact target SHA and all required ablation telemetry are observed in CI.

## Research protocol

JAMP is intended to preserve the path of discovery rather than retrofit a mechanism to a known answer. Experiments should retain the observation, question, hypotheses, actions, failures, causal links, state digests and replay evidence needed to reconstruct how a result was obtained.

See [`docs/research-protocol.md`](docs/research-protocol.md).

## Evidence

The repository separates architecture, milestone records and evidence so that implementation claims can be checked against concrete commits, CI runs, experiment reports and cryptographic digests.

See [`status/milestone-matrix.md`](status/milestone-matrix.md) and [`docs/evidence/README.md`](docs/evidence/README.md).

## License

The JAMP repository is licensed under the Apache License 2.0. The existing repository license is Apache-2.0; no license change is made by this commit.

## Current boundary

The public repository is the research-facing JAMP core and evidence layer. Future production or enterprise infrastructure can remain architecturally separated from the research core.
