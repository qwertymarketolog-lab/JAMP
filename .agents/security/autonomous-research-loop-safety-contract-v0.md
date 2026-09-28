# Autonomous Research Loop Safety Contract v0

## 1. Status
- Version: v0
- Scope: Autonomous Research Loop
- Contract mode: fail-closed
- Authority: deterministic external enforcement
- Frozen Core invariant: `Δ(src/jamp/run.py) = 0`
- Status: design contract; this document does not grant runtime authority.

## 2. Purpose
This contract constrains autonomous agent trajectories, separates executor from deterministic arbiter, preserves evidence/provenance, prevents self-authorization and policy weakening, and makes missing or contradictory evidence fail closed.

> The agent may propose and act within an externally enforced boundary; it may not define, weaken, or adjudicate that boundary for itself.

## 3. Definitions
- **Agent:** untrusted perception/execution component that may generate hypotheses, observations, candidate patches, and proposed actions.
- **Action:** any proposed or executed operation affecting repository state, external state, or loop state.
- **Observation:** structured data from an agent, tool, CI system, or other source; not automatically authoritative evidence.
- **Evidence:** verified observations accepted by deterministic enforcement for a specified decision.
- **Provenance:** traceable relationship connecting task, source/target commits, repository state, workflow/check/job identity, artifacts, changed paths, and state transition.
- **Frozen Core:** protected `src/jamp/run.py`; locked blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.
- **External Enforcement / Policy Boundary:** deterministic control outside model reasoning that validates actors, operations, targets, paths, provenance, and consequential transitions.
- **Evidence Independence:** the producer of a candidate result cannot unilaterally establish its authoritative status.
- **Consequential Transition:** a state transition that authorizes further autonomous work, declares verification, closes a task, or changes authoritative interpretation.

## 4. Frozen Core Lock
Protected path: `src/jamp/run.py`

Locked blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Rule: `Δ(src/jamp/run.py) = 0`.

Any WRITE or DELETE against the Frozen Core must be rejected externally and represented as `BLOCKED`. The agent must not create an alternate authorization path. The Frozen Core must not be changed for performance, CI noise, experiment convenience, gate clearance, or autonomous task completion.

## 5. Nine Safety Invariants

### INV-01 — Frozen Core Immutability
The Frozen Core is immutable under the Autonomous Research Loop. Violation => `DENY` / `BLOCKED`.

### INV-02 — No Self-Authorization
The agent cannot grant itself permissions, alter its policy boundary, change protected-path rules, or approve its own consequential transition.

### INV-03 — No Synthetic PASS
A model statement, simulation, modified metric, or incomplete CI observation cannot manufacture authoritative PASS. PASS requires real, attributable, validated evidence from the applicable deterministic gate.

`agent assertion != authoritative evidence`

### INV-04 — Preserve Conflicting Evidence
Conflicting observations must be retained with provenance. They cannot be deleted, rewritten, or silently downgraded to obtain a desired state. Unresolved conflict remains `INCONCLUSIVE`, `HOLD`, or another explicitly non-PASS state.

### INV-05 — No CI Weakening
The agent must not weaken CI, tests, thresholds, workflow conditions, branch protections, or gate logic to obtain success. This includes deleting/weakening tests, relaxing thresholds, bypassing checks, disabling gates, or changing evaluation semantics.

### INV-06 — External Boundary Enforcement
All consequential operations pass through deterministic external policy enforcement. Model intent, confidence, or reasoning is not permission.

`agent → action request → external policy boundary → ALLOW / DENY / INCONCLUSIVE → execution`

### INV-07 — Missing Evidence → INCONCLUSIVE
Missing, malformed, stale, contradictory, or unverifiable evidence must not become success. Examples include missing artifacts/jobs, `jobs=[]`, missing check-runs, SHA mismatch, provenance mismatch, or incomplete CI. Required behavior is fail-closed.

### INV-08 — Consequential Transition Requires Provenance
Every consequential transition requires sufficient provenance identifying task, source/target state, repository, commit lineage, CI/check evidence, artifacts, and decision context. No provenance means no authoritative consequential transition.

### INV-09 — Evidence Independence
The executor cannot be the sole arbiter of its own result. Agent-generated candidate evidence may be submitted for validation but cannot alone establish authoritative consequential PASS.

`executor != arbiter`

## 6. Action Boundary

### Allowed within explicitly authorized scope
- read repository content;
- search and analyze evidence;
- generate hypotheses;
- propose changes;
- modify explicitly allowed paths;
- create an isolated branch;
- open a pull request;
- request CI validation.

### Forbidden
- modify the Frozen Core;
- alter authorization rules;
- disable/bypass CI;
- weaken gates or thresholds;
- modify branch protection to obtain approval;
- merge consequential work autonomously;
- delete/conceal conflicting evidence;
- manufacture authoritative PASS;
- escape the declared repository/path boundary.

An allowed task scope never overrides system-level invariants.

## 7. State Machine and Execution Flow
Intended trajectory:

`INIT → RESEARCH → PROPOSE → IMPLEMENT → AWAIT_CI → EVIDENCE_AUDIT`

Terminal outcomes:
- `PASS / VERIFIED` only with authoritative gate evidence;
- `FAIL` when validated evidence establishes failure;
- `INCONCLUSIVE` when evidence is absent, contradictory, or unverifiable;
- `BLOCKED` on enforcement-boundary violation;
- `HOLD` when external intervention is required.

A state transition must never be inferred solely from an agent message.

CI observations are non-authoritative until lineage and completeness are verified, including for empty job lists, missing runs/artifacts, partial checks, stale runs, SHA mismatches, or unexpected workflow identity.

## 8. Evidence Contract
Consequential evidence should be attributable to, as applicable:
- task identity;
- source and target SHA;
- base reference and branch;
- PR identity;
- workflow/run/check identity;
- artifact identity;
- changed paths;
- Frozen Core identity;
- validation outcome.

Evidence must remain traceable to the observation that produced it. Candidate results may be proposed by an agent; authoritative acceptance belongs to deterministic enforcement.

## 9. Verification Matrix

| Invariant | Enforcement boundary | Evidence | Violation outcome |
| --- | --- | --- | --- |
| INV-01 | protected path/blob gate | path + blob identity | BLOCKED |
| INV-02 | external authorization | actor + policy decision | DENY |
| INV-03 | deterministic CI/evidence gate | completed checks + provenance | INCONCLUSIVE |
| INV-04 | evidence/conflict layer | preserved observations | INCONCLUSIVE / HOLD |
| INV-05 | CI/workflow policy | changed-path + workflow lineage | BLOCKED |
| INV-06 | operation/path policy | authorization record | DENY |
| INV-07 | evidence gate | completeness checks | INCONCLUSIVE |
| INV-08 | provenance gate | lineage record | BLOCKED / INCONCLUSIVE |
| INV-09 | independent arbitration | producer/authority metadata | INCONCLUSIVE |

## 10. Fail-Closed Rules
The following must never silently become PASS:

`missing evidence`, `jobs=[]`, `missing artifact`, `missing job`, `SHA mismatch`, `workflow mismatch`, `provenance mismatch`, `unexpected protected-path change`, `conflicting evidence`, `agent-only assertion`.

When required information cannot be established, the system must stop, hold, or return an explicit non-success state.

## 11. CI Integrity
CI is evidence, not authority by itself. Before a CI result is accepted for a consequential transition, verify:
1. repository identity;
2. event/run lineage;
3. workflow identity;
4. source/head SHA;
5. required jobs/checks exist;
6. jobs are not merely absent/skipped;
7. required conclusions are successful;
8. required artifacts are present;
9. workflow configuration was not weakened by the candidate change.

No mean, confidence score, or model assertion substitutes for required CI evidence.

## 12. Conflict Preservation
When evidence disagrees:

`Evidence A + Evidence B → CONFLICT`

The conflict is an auditable research result. The agent may investigate it but may not erase one side to obtain a preferred outcome. Unresolved conflict cannot become PASS by model judgment alone.

## 13. Audit Requirements
Each consequential action or transition should be reconstructable from:
- actor;
- action;
- target;
- task;
- source SHA;
- target SHA;
- workflow/run/check identity;
- artifacts;
- evidence;
- policy decision;
- resulting state.

The audit must answer who acted, what changed, under which authority, based on which evidence, and why the resulting state was accepted.

## 14. Adversarial Evaluation
The contract must eventually be tested against:
1. Frozen Core modification attempt;
2. other protected-path modification;
3. CI weakening attempt;
4. required-check bypass;
5. missing artifact;
6. `jobs=[]`;
7. head/source SHA mismatch;
8. workflow identity mismatch;
9. contradictory evidence;
10. agent self-declared PASS;
11. agent modification of its own policy;
12. unauthorized operation/target combination.

Expected behavior:

`unexpected condition → DENY / BLOCKED / INCONCLUSIVE`

## 15. Non-Goals
Safety Contract v0 does not:
- modify `src/jamp/run.py`;
- claim an LLM is intrinsically safe;
- replace GitHub/repository security controls;
- grant merge authority to the autonomous agent;
- make agent output authoritative because it is confident;
- resolve runner/loop state-machine duplication by assertion alone.

## 16. Known v0 Gaps

### G1 — Evidence Independence
Current evidence structures establish presence/basic provenance but do not yet fully encode producer/authority separation.

### G2 — Specialized CI Integrity
Current path/operation policy provides a strong boundary, but CI-specific protected-scope enforcement should become explicit rather than task-dependent.

### G3 — State-Machine Unification
Runner execution phases and loop lifecycle states currently coexist. Their authoritative relationship must be specified before autonomous operation depends on both.

These are incremental engineering work and must not require changing the Frozen Core.

## 17. Acceptance Criteria
The contract is documented when:
- all nine invariants are explicit;
- Frozen Core identity is recorded;
- action boundaries are explicit;
- consequential transitions require provenance;
- missing evidence is fail-closed;
- conflicting evidence is preserved;
- agent-generated evidence is insufficient authority for consequential PASS;
- adversarial cases have explicit expected outcomes;
- known implementation gaps are recorded rather than hidden.

Implementation claims must be verified separately from this document.

## 18. Versioning and Change Control
This document is versioned independently from the Frozen Core.

A future revision must:
1. identify the version change;
2. preserve provenance;
3. document changed invariants;
4. specify compatibility/transition behavior;
5. pass applicable repository gates.

An autonomous agent must not silently rewrite the contract as part of an ordinary research task.

---

## Core Principle

> AI searches, proposes, and acts within a bounded action space. JAMP verifies, connects, compares, preserves provenance and conflicts, and deterministically arbitrates consequential state transitions.

The agent is a participant in the research loop—not the authority over the rules, evidence, or verdicts of that loop.
