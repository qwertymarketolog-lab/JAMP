# JAMP OS Readiness Plan v1

**Status:** DESIGN / READINESS NOT VERIFIED  
**Decision:** HOLD for a release-grade JAMP OS image; READ-ONLY audit is the next authorized action.  
**Scope:** Documentation-only readiness contract. This file does not claim that JAMP is already an operating system or that the requirements below have passed.  
**Frozen Core:** src/jamp/run.py, locked Git blob 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a; required delta Δ = 0.

## 1. Purpose and decision boundary

This document records the minimum evidence required before packaging JAMP as a Linux-based operating environment.

Three distinct targets must not be conflated:

1. **JAMP on Linux:** install and run the existing application/services on a supported Linux distribution.
2. **JAMP OS distribution:** assemble a bootable image based on an existing Linux distribution, with JAMP services and a management UI.
3. **New operating-system kernel:** implement or maintain a kernel and its drivers, process/memory management, filesystem and hardware support.

The recommended sequence is target 1 → target 2. A new kernel is out of scope unless a separately evidenced requirement cannot be met by the existing Linux kernel. A bootable image is not authorized for release until the gates in Section 5 have sufficient evidence.

## 2. Architecture principles

- Linux remains responsible for kernel, process, memory, device, filesystem and network primitives.
- JAMP remains an evidence-first layer for provenance, evidence evaluation, task routing, audit and explicit uncertainty.
- The UI, adapters, packaging and operating-system integration must remain outside the Frozen Core.
- No service receives administrator/root privileges merely because it is part of JAMP. Use least privilege and explicit boundaries for privileged operations.
- A successful process start, HTTP response, unit test or CI workflow does not independently prove the correctness or security of the entire system.
- Missing, stale, conflicting or insufficient evidence must remain UNKNOWN / INCONCLUSIVE and must not be promoted to VERIFIED.
- Do not bypass the Capability Router or manufacture an EXECUTE result when the executor was not actually invoked.
- Preserve raw evidence separately from derived summaries. Bind claims to the exact run, job, artifact and relevant digests where applicable.
- Do not create duplicate implementation or documentation if the repository already contains an equivalent, current artifact. Inspect repository state before every subsequent change.

## 3. Readiness audit scope (READ-ONLY first)

The initial audit must inspect the current default-branch commit and existing open work before proposing code changes.

### 3.1 Repository and change boundary
- Record the exact base commit SHA and audit timestamp.
- Identify existing implementation, tests, workflows, documentation and open PRs relevant to Linux/runtime/security.
- Record exact files and commands inspected.
- Confirm the audit introduces no runtime, workflow, test-policy or Frozen Core changes.
- Compare the Frozen Core blob to the locked value above. Any mismatch is a hard HOLD; do not repair or modify it as part of this audit.

### 3.2 Linux installation and reproducibility
- Identify supported Linux distribution/version and supported Python/runtime versions from repository evidence; do not assume compatibility.
- On a clean disposable VM, follow a written install procedure from a fresh checkout.
- Install pinned/reproducible dependencies where feasible and record package/tool versions.
- Run the existing test suite and relevant lint/type/security checks without silently excluding failures.
- Verify documented start, stop, restart and clean-shutdown procedures.
- Record commands, exit codes, logs, environment details and artifacts. If no clean VM run was performed, mark this gate UNKNOWN.

### 3.3 End-to-end task path
Inspect and, in a controlled test environment, verify the actual path:

User/API → input validation → Capability Router → executor → result → Evidence/Audit persistence → retrievable artifact

Required scenarios:
- An allowed task executes through the expected route.
- Unknown task/profile or missing required evidence fails closed.
- Executor exceptions do not create false success.
- Storage failure, interrupted execution and unavailable dependencies are handled explicitly.
- The audit record identifies what actually ran and what did not run.

A unit test or offline vertical slice must not be described as proof of an end-to-end path unless it exercises that exact path.

### 3.4 Evidence integrity and persistence
Verify, using implementation and executable tests:
- raw evidence versus derived evidence boundaries;
- provenance binding and artifact identity;
- SHA-256 or other specified digest verification;
- detection of missing, altered, stale or mismatched artifacts;
- persistence after process restart;
- behavior when storage is unavailable or partially written;
- no VERIFIED status solely from file existence, a green CI check or a successful transport response.

### 3.5 Runtime/service operation
Inspect or verify:
- explicit entry points and configuration;
- secrets supplied through supported secret/configuration mechanisms, never committed;
- lifecycle and signal handling;
- health/readiness checks with clearly limited meaning;
- structured logs and diagnostic context without leaking secrets;
- bounded retries/timeouts where applicable;
- crash/restart behavior;
- controlled update and rollback strategy.

A health endpoint only demonstrates its documented health predicate; it is not a general correctness or qualification certificate.

### 3.6 Security and software supply chain
Document and test the relevant boundaries:
- least-privilege service accounts and filesystem permissions;
- API authentication/authorization and network exposure;
- secret storage and log redaction;
- dependency/version provenance and vulnerability review;
- integrity and provenance of downloaded packages, images and installed artifacts;
- build-to-artifact identity, signing/verification where supported, and update authenticity;
- separation of privileged administration from ordinary task execution;
- threat model, recovery procedure and known limitations.

The XZ Utils incident is motivation for supply-chain scrutiny, not evidence that JAMP itself prevents all operating-system attacks. JAMP does not replace Linux security controls, sandboxing, patching or independent security review.

### 3.7 Frozen Core
- Expected path: src/jamp/run.py.
- Expected locked blob: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.
- Required invariant: Δ = 0.
- Verify before and after any later integration change.
- Keep OS packaging, adapters, UI and service wiring outside this file.
- If the locked blob differs, stop and report the mismatch; do not claim the invariant passed.

## 4. Evidence and status vocabulary

Use only these readiness labels:

- **VERIFIED** — the stated acceptance predicate is supported by direct, reproducible evidence tied to the exact audited commit/environment.
- **PARTIAL** — only a defined subset of the predicate has been demonstrated; explicitly name the missing portion.
- **UNKNOWN** — evidence is absent, inaccessible, stale, ambiguous or not bound to the relevant artifact.
- **FAILED** — a check ran and demonstrated that its acceptance predicate was not met.
- **HOLD** — a decision state preventing the next gated action while required evidence is missing or a blocker exists.

Do not convert UNKNOWN, INCONCLUSIVE or PARTIAL into VERIFIED. A successful CI run is evidence only for the checks and code that it actually exercised.

Every reported check should include, where applicable:
- repository and exact commit SHA;
- command/workflow and version/environment;
- terminal Run → Job → artifact chain for CI-based claims;
- exit status and raw logs/artifact identifiers;
- relevant digest(s);
- acceptance predicate and observed result;
- limitations and unresolved questions.

## 5. Release-readiness gates

All mandatory gates must be supported by evidence before claiming release readiness.

| Gate | Acceptance condition | Initial status |
|---|---|---|
| G1 — Linux Runtime | Reproducible installation and launch on a clean, declared Linux environment | UNKNOWN |
| G2 — End-to-end routing | Actual allowed path and fail-closed path verified, including exception behavior | UNKNOWN |
| G3 — Evidence integrity | Provenance, digest validation, persistence and failure behavior verified | UNKNOWN |
| G4 — Security boundary | Least privilege, exposed interfaces, secrets and supply-chain controls reviewed and tested to the declared scope | UNKNOWN |
| G5 — Reliability | Stop/restart, interrupted execution, dependency/storage failures and recovery behavior tested | UNKNOWN |
| G6 — Frozen Core | Locked blob identity confirmed and Δ = 0 before/after changes | UNKNOWN until rechecked for the audited commit |
| G7 — Image build/boot | Image build is reproducible enough for the declared scope and boots in a disposable VM with recorded evidence | NOT STARTED / UNKNOWN |

**Gate rule:** Until all mandatory gates pass, release-grade image status remains HOLD. Planning and isolated disposable-VM experiments may proceed without implying release readiness. Any gate may be PARTIAL only when the tested subset and missing evidence are explicit.

## 6. Proposed implementation sequence

1. **READ-ONLY audit:** inventory existing implementation, tests, workflows, open PRs and current main SHA; produce a single readiness report without changing runtime code.
2. **Close demonstrated blockers only:** avoid duplicate PRs and do not implement speculative fixes before the audit identifies a concrete gap.
3. **Linux runtime validation:** run the existing application on a clean disposable VM and bind results to the exact commit.
4. **Service hardening:** implement only required lifecycle, permission, logging, configuration and recovery gaps.
5. **Disposable image prototype:** choose the base distribution only after requirements and package compatibility are known. Debian/Ubuntu are candidates, not a final decision. Buildroot is appropriate only if a constrained/minimal image is justified.
6. **Image verification:** test boot, service startup, fail-closed behavior, persistence, update/recovery and Frozen Core identity.
7. **Release decision:** record terminal evidence and unresolved risks. Do not claim production/security certification from this checklist alone.

## 7. Out of scope for this readiness record

- Writing a new OS kernel.
- Changing the Frozen Core or relaxing evidence rules.
- Declaring JAMP OS implemented or secure before tests.
- Making live external provider calls or changing model qualification as part of the OS audit.
- Creating implementation PRs before the READ-ONLY audit establishes need.
- Treating a design document as execution evidence.

## 8. Required audit report contents

The eventual audit report should record:
1. audited base commit SHA and timestamp;
2. repository state and related open PRs inspected;
3. files/components inspected;
4. commands and tests actually executed;
5. terminal Run → Job → artifact references for CI evidence;
6. Frozen Core blob comparison;
7. per-gate status with direct evidence and limitations;
8. blockers ordered by dependency/impact;
9. one recommended next action;
10. explicit decision: HOLD or readiness for the next gate.

This plan is a requirements record only. It is not the completed audit report and does not itself satisfy any readiness gate.
