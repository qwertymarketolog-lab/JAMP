# Independent Verifier — Known Limitations (v0)

Status: Track 4 limitation record — v0  
Scope: PR #479, merge commit `53ef75e812fcf9f1a1b27750e7b790facabd79d5`  
Frozen Core: unchanged (blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`, Δ=0)

## 1. Purpose

This file records the verified scope and limitations of the independent
verifier introduced in PR #479 (`independent_verifier.py`, blob
`c8d8f9beff098bcb62e7c064698665d290e10897`).

The verifier is a necessary but not sufficient component of the provenance
chain. Its presence and its passing CI do NOT constitute proof that
`PROVENANCE-CONTRACT-v0` is satisfied end-to-end.

## 2. Implemented scope

The verifier operates on caller-supplied inputs: an envelope, a JampVerdict,
a trace, optional raw evidence bytes, and optional exported JSONL chain
records for three stores:

- traces
- verdicts
- universal_verdicts

For a given input set, it checks the signed chain:

    JampVerdict → UniversalVerdict → trace

and returns a `VerificationReport` describing the outcome for those inputs.
The verifier does not access persistence directly and does not re-derive a
normative Verdict from first principles.

A `VERIFIED` report requires all 12 checks to be PASS. In particular, raw
evidence and all three exported stores must be supplied and pass their
respective checks. Missing mandatory inputs result in an INCONCLUSIVE report;
a missing signing secret results in REFUSE.

## 3. Limitations (v0)

L1. Bounded verdict-chain scope.  
    Verified chain: JampVerdict → UniversalVerdict → trace.  
    This is not full PROVENANCE-CONTRACT-v0 coverage.

L2. No persistence access.  
    The verifier requires caller-provided exports of traces, verdicts and
    universal_verdicts. It does not query any store itself. Trust in the
    export as a faithful snapshot of persistence is out of scope.

L3. Raw Evidence bytes required for VERIFIED status.  
    The caller must supply raw evidence bytes, keyed by source_sha256 (the
    API accepts base64-encoded values). If referenced raw bytes are absent,
    the evidence check is skipped and the report cannot reach VERIFIED.

L4. No external trusted anchor.  
    The verifier checks the supplied hash-chain segment, but has no external
    trusted anchor for the expected chain head or complete file. Therefore,
    it cannot independently detect truncation or wholesale replacement of
    an entire exported file by a self-consistent chain.

L5. Shared HMAC secret.  
    Signature verification relies on a shared HMAC secret. Compromise of
    that secret undermines trust in signature verification. The v0 design
    does not establish production-grade secret custody, rotation, or
    hardware-backed protection. Asymmetric signing and KMS/HSM integration
    remain future work.

L6. VerificationReport ≠ normative Verdict.  
    The verifier returns a VerificationReport. It does not independently
    recompute a normative Verdict from the complete v0 specification and
    criteria chain. A VerificationReport SHALL NOT be presented as a
    substitute for the normative Verdict object.

L7. Offline replay — DEFERRED.  
    Full offline replay from a frozen bundle is not implemented in v0.
    It is DEFERRED and NOT assigned to any specific stage pending explicit
    roadmap confirmation. No commitment is implied by this record.

L8. CI coverage gap.  
    PostgreSQL integration tests were skipped in Post-merge CI because
    JAMP_DATABASE_URL was absent. This is a coverage gap, not evidence of
    verifier failure. The PostgreSQL integration path remains unverified
    by that run.

## 4. Non-blocking observations

- import-historical.yml: failure with an empty jobs list — known orphaned
  anomaly. It does not block this documentation task and is tracked
  separately.
- Repeated PostgreSQL FATAL: role "root" does not exist messages appear in
  Pytest logs; jobs complete SUCCESS. Root cause is not declared resolved.
- Test logs report 177 warnings.

## 5. Contract

L1–L8 are binding when interpreting any verifier result in v0.

A verifier result of VERIFIED SHALL NOT be presented, internally or
externally, as full PROVENANCE-CONTRACT-v0 conformance.

## 6. Provenance

- Introduced by: PR #479
- Merge commit: 53ef75e812fcf9f1a1b27750e7b790facabd79d5
- independent_verifier.py blob: c8d8f9beff098bcb62e7c064698665d290e10897
- Post-merge CI evidence:
  - Run Pytest: 41034231014 / Job 123991013849
  - Developer Quality: 41034230762 / Job 123991012697
  - P36.2 G4 MinIO: 41034230814 / Job 123991012871
  - P23.0-B Cold Replay: 41034230978 / Job 123991013363
- Frozen Core: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a (Δ=0)
