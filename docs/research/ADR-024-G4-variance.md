# JAMP Epistemic Decision Record: ADR-024 (Revision 1)

**Subject:** Empirical Characterization of G4 Variance across Shared CI Environments  
**Status:** PROPOSED (EVIDENCE-SAFE RESEARCH RECORD)  
**Frozen Core:** LOCKED (Δ = 0)  
**Contract:** G4 ≤ 15.000 ms (ACTIVE)

## 1. Empirical Grounding (N=3)

CI matrix evidence is recorded by workflow run **35647703972** from commit **e032d3fc5d9a1b930f66da349127dd3582d9101e**. The matrix checks out the fixed target revision **d15312ae17a6564f2b519a2753cd332cb43d8327**.

| Environment | CPU/vCPU | μ (ms) | Min (ms) | Max (ms) | Range (ms) | σ_sample | Verdict split |
|---|---:|---:|---:|---:|---:|---:|---|
| Ubuntu 24 | x86_64 / 4 CPU | 15.331 | 11.095 | 18.157 | 7.062 | 3.737 | 1 PASS / 2 FAIL |
| macOS 26 | ARM64 / 3 CPU | 13.652 | 11.272 | 17.183 | 5.911 | 3.120 | 2 PASS / 1 FAIL |

Observed evidence supports the following bounded statements:

- Both environments produced PASS and FAIL outcomes around the active 15.000 ms threshold.
- The observed sample standard deviations are above 1.5 ms; therefore the hypothesis σ ≤ 1.5 ms is falsified by this observed sample.
- In-situ telemetry recorded wall time approximately equal to process CPU time; across the six measurements, |wall - CPU| ≤ 0.001 ms.
- Runner CPU-count telemetry matches the recorded 4-CPU Ubuntu and 3-CPU macOS ARM64 configurations.
- No change to `src/jamp` or to the G4 threshold is part of this research finding.

### Causal attribution bound

**The observed variance is environment-dependent; its causal mechanism is unresolved. Hypervisor/scheduling effects remain a working hypothesis, not a demonstrated cause.**

The N=3 sample does not establish that the variance originates specifically from hypervisor scheduling, nor does it isolate runner jitter from other environmental factors.

## 2. Epistemic Falsifications

### Model A — Binary OS Tiering

The proposition that Linux deterministically fails while macOS deterministically passes is falsified by mixed PASS/FAIL outcomes in both environments.

### Model B — Tight Jitter Bound

The hypothesis σ ≤ 1.5 ms is falsified by the observed sample standard deviations (3.737 ms and 3.120 ms).

These falsifications describe the observed sample; they do not establish a universal distribution or causal mechanism for CI variance.

## 3. Governance Directives

### Invariant Preservation

`src/jamp` remains strictly Δ = 0. No production/runtime modification or algorithmic workaround is authorized by this ADR.

### Contract Integrity

**G4 ≤ 15.000 ms remains an active and enforcing contract.**

A single-run G4 FAIL is not reclassified as compliant by this ADR. No retrospective threshold redefinition or individual-run waiver is granted.

### PR #134

PR #134 is treated as **research evidence attached to an environment-variance finding**, not as a contract bypass or production compliance clearance.

### EXP-21

**EXP-21 remains UNVERIFIED** until governance policy explicitly defines how stochastic CI variance is handled relative to the strict G4 SLA gate.

Candidate policy questions for a separate governance discussion include:

- statistical retry policy;
- tier-isolated CI matrix evaluation;
- strict physical-hardware requirements;
- explicit evidence requirements for distinguishing environmental variance from algorithmic non-compliance.

No such policy is adopted by ADR-024 itself.

## 4. Evidence Boundary

This ADR records what the current experiment demonstrates and explicitly leaves unresolved what it does not demonstrate.

**Demonstrated:** environment-dependent variance in the observed N=3 matrix, mixed threshold outcomes, observed sample variance above the 1.5 ms hypothesis, and near-zero wall/CPU delta in the six measurements.

**Not demonstrated:** a specific hypervisor-scheduling causal mechanism, a universal CI jitter distribution, or permission to ignore an individual G4 FAIL.

## 5. Current State

- Frozen Core: **LOCKED**
- G4 contract: **ACTIVE / ENFORCED**
- PR #134: **OPEN / DRAFT / research evidence**
- EXP-21: **UNVERIFIED**
- Causal mechanism: **UNRESOLVED / ENVIRONMENT-DEPENDENT**
