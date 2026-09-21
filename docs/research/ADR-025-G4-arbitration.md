# JAMP Epistemic Decision Record: ADR-025

**Subject:** G4 Stochastic CI Arbitration Policy (Gate 1)  
**Status:** PROPOSED (GOVERNANCE PROTOCOL)  
**Frozen Core:** LOCKED (Δ = 0)  
**Contract:** G4 ≤ 15.000 ms (ACTIVE)

## 1. Axioms and Constraints

- **No Mean-Based Clearance:** A sample mean (μ ≤ 15.000 ms) containing an active contract failure does **not** grant clearance.
- **No Causal Speculation:** Arbitration grants procedural clearance based on temporal bounds, not causal attribution. The mechanism of variance remains formally unproven.
- **Core Integrity:** Zero code modifications to src/jamp are permitted to satisfy environment jitter (Δ = 0).

## 2. Arbitration Matrix

| Trigger / Condition | Verdict / State | CI Pipeline Action |
|---|---|---|
| Single Run ≤ 15.000 ms | G4 PASS | Green / Proceed |
| Single Run > 15.000 ms | STOCHASTIC_SUSPECT | Red / Blocked (Triggers N=3 arbitration) |
| Arbitration: 3/3 runs ≤ 15.000 ms | G4 CLEARANCE | Transient variance procedurally cleared. Root cause unresolved. |
| Arbitration: ≥ 1/3 runs > 15.000 ms | CONTRACT_VIOLATION | Arbitration failed. Requires code optimization or formal SLA revision. |

## 3. Decision Flow

[G4 Execution] > 15.000 ms
      │
      ▼
[STOCHASTIC_SUSPECT] (CI: Blocked)
      │
      ▼
[Initiate N=3 Arbitration Suite]
      │
 ┌────┴────┐
 ▼         ▼
3/3 PASS   ≥1 FAIL
 │         │
 ▼         ▼
[CLEARANCE] [CONTRACT_VIOLATION]
 │         │
 ▼         ▼
(Gate 1    (Optimization /
 PASS)      SLA Review)

## 4. Governance Interpretation

### Strict contract remains active

A single-run G4 result above 15.000 ms remains a contractual failure at the execution level. ADR-025 does not redefine the threshold, erase the failure, or authorize a retrospective waiver.

### Procedural clearance

The G4 CLEARANCE state is a governance result produced only by the defined N=3 arbitration procedure. It does not assert that the original failing measurement was caused by hypervisor jitter, scheduling, garbage collection, or any specific mechanism.

The evidence-safe statement is:

> The arbitration series satisfied the temporal criterion defined by this governance policy. The causal mechanism of the observed deviation remains unresolved.

### No averaging

A mean, median, variance estimate, or other aggregate statistic cannot substitute for the required 3/3 contractual outcomes. In particular, μ ≤ 15.000 ms with one or more individual failures does not produce clearance.

## 5. Frozen Core Protection

ADR-025 authorizes no changes to:

- src/jamp;
- the 15.000 ms G4 threshold;
- the existing contractual G4 assertion;
- production/runtime behavior.

Any attempt to satisfy G4 by modifying the Frozen Core requires a separate evidence-based decision and is outside this ADR.

## 6. Gate 1 State Machine

G4 > 15.000 ms
      │
      ▼
STOCHASTIC_SUSPECT
      │
      ▼
N=3 arbitration
      │
      ├── 3/3 ≤ 15.000 ms ──► G4 CLEARANCE
      │                         │
      │                         └── Gate 1 PASS
      │
      └── ≥1 > 15.000 ms ────► CONTRACT_VIOLATION
                                │
                                └── Optimization / SLA Review

G4 CLEARANCE means procedural clearance under this ADR. It is not a causal explanation and does not imply that the environment is proven to be the source of the variance.

## 7. Evidence Boundary

**Demonstrated by this policy:** a deterministic decision procedure for handling an observed G4 threshold exceedance without weakening the active contract or changing the Frozen Core.

**Not demonstrated by this policy:** the physical or software cause of CI timing variance, a universal distribution of runner jitter, or the correctness of any particular causal hypothesis.

## 8. Downstream Gate Dependency

ADR-025 defines Gate 1 governance only.

- **Gate 1:** G4 Governance — governed by ADR-025.
- **Gate 2:** EXP-21 Verification — remains subject to its own evidence and verification criteria.
- **Gate 3:** EXP-18 Atomic Ingress — remains pending its own implementation and verification.
- **Gate 4:** Golden Replay E2E — remains pending.

ADR-025 does not by itself mark EXP-21 VERIFIED or alter any downstream gate status.

## 9. Current Protocol State

- Frozen Core: **LOCKED**
- G4 contract: **ACTIVE / ENFORCED**
- Arbitration policy: **PROPOSED**
- Causal mechanism of variance: **UNRESOLVED**
- Any individual G4 FAIL: **remains a FAIL unless cleared by the defined arbitration procedure**
