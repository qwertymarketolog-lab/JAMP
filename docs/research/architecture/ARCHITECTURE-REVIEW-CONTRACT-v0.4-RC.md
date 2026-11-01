# ARCHITECTURE-REVIEW-CONTRACT-v0.4-RC

Status: RATIFIED DESIGN — RC FREEZE — IMPLEMENTATION PENDING
Ratified: 2026-11-01
Base: main 2644857a5fc3ef55648d80f4d0e3c294a4c60975
Frozen Core: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a (Δ=0 at RC freeze)

This is the Release Candidate of the Verdict Architecture. It consolidates
all ratified iterations v0.1 → v0.4 and patches P1–P5, B1–B7, У1, У2 rev2,
Genesis/Advance/G2.2/G2.3/G2.3a/Binding/release_payload fixes.

RC FREEZE means: no further conceptual review of the full document. Future
changes require a concrete counterexample from implementation or tests, not
re-reading. Known Issues are listed explicitly and are not treated as
ratified.

Ratification does NOT authorize implementation. Implementation requires
separate explicit approval.

## 1. Architecture — full chain

    Frozen Specification (spec_hash, spec_id)
        ↓
    Specification Gate (gate_sha256 as implementation closure)
        ↓
    Criterion Set (frozen, criterion_set_ref)
        ↓
    Raw Evidence Bundle (evidence_bundle_ref)
        ↓
    Evidence Selector (per-class, evidence_selector_sha256)
        ↓
    Criterion Evaluator (per-type, criterion_evaluator_sha256)
        ↓
    Criterion Results (ordered, bijection with Criterion Set)
        ↓
    Frozen Aggregation Rule (declarative + reference impl, aggregation_rule_sha256)
        ↓
    Aggregating Evaluator (evaluator_sha256)
        ↓
    Verdict (verdict_id + external verdict_object_ref)
        ↓
    Verdict Report (independent verification)
        ↓
    Chain Report (#479 verifier)
        ↓
    Evidence Package (three reports bundled)

## 2. Three levels of trust

| Level | Question | Object |
|---|---|---|
| Chain Integrity | Evidence not corrupted, refs resolve? | Chain Report |
| Verdict Correctness | Result matches Criterion Results + Frozen Rule? | Verdict + Verdict Report |
| Claim Adequacy | Are criteria sufficient for the claim? | NOT SOLVED by Evidence Package |

JAMP MUST NOT present a package passing levels 1 and 2 as proof of level 3.

## 3. Three object types (mutually exclusive)

| Object | When | Contains verdict_status |
|---|---|---|
| Verdict | Input well-formed, rule applied, one of four statuses | YES |
| EvaluationRefusal | Input structurally invalid | NO |
| EvaluationError | Evaluator invariant violated (bug) | NO |

Verdict with verdict_status=REFUSE exists only for invalid Specification
or empty Criterion Set. Structural failures → EvaluationRefusal. Guard
clause firing → EvaluationError.

## 4. Four implementation identities (content-addressed)

| Role | Field |
|---|---|
| Aggregating Evaluator | evaluator_sha256 |
| Criterion Evaluator | criterion_evaluator_sha256 (per criterion_result) |
| Evidence Selector | evidence_selector_sha256 (per criterion_result) |
| Reference Implementation | reference_implementation_sha256 |

Each is an implementation closure (§11). Gate (gate_sha256) and verifier
(verifier_sha256) are also closures.

## 5. Verdict Object

JSON Schema Draft 2020-12, additionalProperties: false.

Required (15):

1.  verdict_version          (semver)
2.  verdict_status           (VERIFIED | CONTRADICTED | INCONCLUSIVE | REFUSE)
3.  claim_id                 (sha256)
4.  spec_ref                 (sha256)
5.  spec_gate_result         (object, §5.5)
6.  criterion_set_ref        (sha256)
7.  evidence_bundle_ref      (sha256)
8.  aggregation_rule_id      (string)
9.  aggregation_rule_version (semver)
10. aggregation_rule_sha256  (sha256)
11. evaluator_version        (semver)
12. evaluator_sha256         (sha256, non-null, INV-V15)
13. criterion_results       (array, §5.6)
14. created_at               (ISO8601)
15. verdict_id               (sha256, §5.2)

Optional:
16. rule_package_sha256      (sha256, attestation only — excluded from verdict_id)

### 5.1 Verdict statuses

| Status | Meaning | When |
|---|---|---|
| VERIFIED | All declared criteria passed under referenced rule | all PASS |
| CONTRADICTED | At least one criterion failed with proof | any FAIL |
| INCONCLUSIVE | Cannot prove, cannot disprove | any UNKNOWN, no FAIL |
| REFUSE | Rule refuses to judge | spec invalid, or empty set |

VERIFIED = "all declared criteria passed under referenced rule". Does NOT
assert criterion set adequacy, nor truth of Specification.

### 5.2 verdict_id — whitelist projection

verdict_id = sha256(
    b"jamp:verdict:v0:" +
    canonical_bytes({
        verdict_version, verdict_status, claim_id, spec_ref,
        spec_gate_result, criterion_set_ref, evidence_bundle_ref,
        aggregation_rule_id, aggregation_rule_version,
        aggregation_rule_sha256, evaluator_version, evaluator_sha256,
        criterion_results: [{
            criterion_ref, result, evaluation_trace, unknown_reason
        } for r in criterion_results],
    })
)

Excluded: verdict_id, created_at, reasoning, rule_package_sha256.

Unknown fields: NOT permitted (additionalProperties: false). Whitelist
defines hash participation for known fields only.

### 5.3 verdict_object_ref — external reference

verdict_object_ref = sha256(
    b"jamp:verdict-object:v0:" + canonical_bytes(json_parse(verdict_bytes))
)

NOT a field of Verdict. Computed by package verifier. Three identities:

| Term | Domain prefix |
|---|---|
| verdict_id | jamp:verdict:v0: |
| verdict_object_ref | jamp:verdict-object:v0: |
| package_sha256 | jamp:evidence-package:v0: |

### 5.4 claim_id

claim_id = sha256(
    b"jamp:claim:v0:" +
    canonical_bytes({"spec_ref": s, "criterion_set_ref": c})
)

Normative hash change from pre-v0.4 (no prefix before). Stage C not
started, no compatibility break.

### 5.5 spec_gate_result

{
    spec_ref:          sha256,
    spec_valid:        bool,
    gate_version:      semver,
    gate_sha256:       closure hash,
    gate_report_sha256: sha256(
        b"jamp:gate-report:v0:" +
        canonical_bytes({spec_ref, gate_sha256, gate_version, spec_valid, diagnostics})
    ),
}

diagnostics sorted by (code, field_key); field_key = (1,"") if null else (0, field).

### 5.6 criterion_results

Ordered, exactly one entry per Criterion, in Criterion Set order. No duplicates.

{
    criterion_ref: sha256,
    result: PASS | FAIL | UNKNOWN,
    evaluation_trace: {
        criterion_evaluator_sha256: sha256,
        evidence_selector_sha256: sha256,
        selector_output: {class, selector, observed},
        predicate_result: true | false | "unknown",
    },
    unknown_reason: null | "evidence_class_absent"
                 | "selector_unresolvable"
                 | "observed_inconclusive",
    reasoning: string | null,
}

unknown_reason REQUIRED: null for PASS/FAIL, non-null for UNKNOWN.
evidence_span is not a separate field; observation in evaluation_trace.selector_output.

## 6. Verdict invariants

INV-V1.  spec_ref == resolved Specification spec_hash.
INV-V2.  criterion_set_ref resolves to frozen Criterion Set.
INV-V3.  evidence_bundle_ref resolves to Raw Evidence bundle.
INV-V4.  aggregation_rule_sha256 matches rule declarative semantics.
INV-V5.  verdict_status == apply(rule, criterion_results, spec_valid).
INV-V6.  verdict_id == sha256(projection) per §5.2.
INV-V7.  spec_gate_result.spec_valid reproduces via replay of historical
         gate closure (INV-V11 precondition).
INV-V8.  criterion_results ordered bijection with Criterion Set.
INV-V9.  For each criterion_result:
           - PASS/FAIL → selector_output.observed non-null, predicate_result
             ∈ {true,false}, consistent with result.
           - UNKNOWN → unknown_reason non-null.
           - evaluation_trace required for all three.
INV-V10. spec_gate_result.spec_ref == verdict.spec_ref.
INV-V11. Historical gate closure resolved by gate_sha256 from content-
         addressed storage, NOT current main. Missing → UNVERIFIABLE_
         IMPLEMENTATION_NOT_FOUND, not INVALID.
INV-V12. For each criterion_result: (1) selector closure resolved by
         evidence_selector_sha256 and replayed; (2) observed compared;
         (3) criterion evaluator closure resolved by
         criterion_evaluator_sha256 and predicate replayed.
         - closure not resolvable → UNVERIFIABLE_IMPLEMENTATION_NOT_FOUND
           (Verdict still valid)
         - closure resolvable, mismatch → Verdict INVALID
         - closure resolvable, mismatch against trace → Verdict INVALID
INV-V13. Historical resolution by *_sha256 fields, not current main.
INV-V14. additionalProperties: false for fixed-schema objects. Keyed maps
         via patternProperties + propertyNames.pattern (§12).
INV-V15. evaluator_sha256 required non-null. null → schema INVALID.

## 7. Frozen Aggregation Rule v0

### 7.1 Behaviour classes (mutually exclusive, precedence order)

| Class | Condition | Result |
|---|---|---|
| A | spec_valid == false | REFUSE |
| B | spec_valid == true ∧ L = [] | REFUSE |
| C | spec_valid == true ∧ L ≠ [] ∧ FAIL ∈ L | CONTRADICTED |
| D | spec_valid == true ∧ L ≠ [] ∧ FAIL ∉ L ∧ UNKNOWN ∈ L | INCONCLUSIVE |
| E | spec_valid == true ∧ L ≠ [] ∧ L ⊆ {PASS} | VERIFIED |

Proof of completeness: spec_valid splits A vs B∪C∪D∪E. Under true: L=[] →
B; L≠[] → B excluded. Under L≠[]: FAIL∈L → C, else UNKNOWN∈L → D, else
L⊆{PASS} → E. Full partition, no overlap. ∎

### 7.2 Declarative spec (5 clauses)

{
    rule_id: "standard-pass-fail-unknown",
    rule_version: "0.1.0",
    preconditions: {
        input_structure_valid: true,
        spec_ref_resolves: true,
        criterion_set_frozen: true,
        criterion_results_bijection: true,
        spec_gate_result_verifiable: true,
    },
    decision_procedure: [
        {if: "spec_valid == false", return: "REFUSE"},
        {if: "true ∧ criterion_count == 0", return: "REFUSE"},
        {if: "true ∧ any(result == FAIL)", return: "CONTRADICTED"},
        {if: "true ∧ any(result == UNKNOWN)", return: "INCONCLUSIVE"},
        {if: "true ∧ all(result == PASS)", return: "VERIFIED"},
    ],
}

Guard clause NOT part of declarative spec. Implementation MAY contain
defensive guard; guard firing → EvaluationError, not Verdict. Guard must
be unreachable (proven in §7.1).

### 7.3 Rule hash — separated

aggregation_rule_sha256 = sha256(
    b"jamp:aggregation-rule:v0:" +
    canonical_bytes({
        rule_id, rule_version, preconditions,
        decision_procedure, decision_procedure_sha256
    })
)

Separate: reference_implementation_sha256 (closure), conformance_test_
suite_sha256 (fixture file). rule_package_sha256 = sha256(canonical of
all three). verdict_id includes aggregation_rule_sha256 + evaluator_sha256,
NOT rule_package_sha256.

## 8. Resolver — basis determination

Inputs: e = evaluator_sha256 (non-null), r = reference_implementation_sha256
(nullable), e_trusted, r_trusted.

| # | Condition | Basis |
|---|---|---|
| 1 | r is null ∧ e_trusted | CONFORMANCE_BASED (attestation required) |
| 2 | r is null ∧ ¬e_trusted | UNTRUSTED_IMPLEMENTATION |
| 3 | e == r ∧ e_trusted | REFERENCE_BASED |
| 4 | e == r ∧ ¬e_trusted | UNTRUSTED_REFERENCE |
| 5 | e ≠ r ∧ ¬e_trusted | UNTRUSTED_IMPLEMENTATION |
| 6 | e ≠ r ∧ e_trusted ∧ ¬r_trusted | CONFORMANCE_BASED (attestation required) |
| 7 | e ≠ r ∧ e_trusted ∧ r_trusted | CONFORMANCE_BASED (attestation required) |

INV-A7.  e == r → REFERENCE_BASED or UNTRUSTED_REFERENCE, NEVER CONFORMANCE_BASED.
INV-A8.  r is null → CONFORMANCE_BASED or UNTRUSTED_IMPLEMENTATION, NEVER REFERENCE_BASED.
INV-A9.  Exactly one of four values. No placeholders.
INV-A10. First match wins; r is null checked before e == r.
INV-A11. UNTRUSTED_REFERENCE only in row 4.
INV-A12. UNTRUSTED_* final; resolution does not continue.

## 9. Verdict Report — 12 states

| State | Meaning |
|---|---|
| VERIFIED_REFERENCE_BASED | e == r, both trusted, replayed |
| VERIFIED_CONFORMANCE_BASED | e ≠ r (or r null), e trusted, attestation passed |
| NONCONFORMANT | attested tests failed, or replay mismatch on trusted closure |
| UNVERIFIABLE_ATTESTATION_ABSENT | CONFORMANCE_BASED without attestation |
| UNVERIFIABLE_IMPLEMENTATION_NOT_FOUND | closure not in storage |
| UNVERIFIABLE_ENVIRONMENT | environment does not match closure |
| UNVERIFIABLE_TRUST_BOOTSTRAP | Trust Bootstrap failed (reason in diagnostics) |
| UNTRUSTED_IMPLEMENTATION | e not in trust store |
| UNTRUSTED_ATTESTER | attester not in trust store (CONFORMANCE_BASED only) |
| UNTRUSTED_REFERENCE | r not in trust store, basis row 4 |
| INVALID_ATTESTATION | attestation malformed / bad signature / unresolvable evidence |
| INVALID | invariant violated after trusted resolve |

Priority order:
0. Trust Bootstrap (fail → UNVERIFIABLE_TRUST_BOOTSTRAP)
1. Trust resolution (UNTRUSTED_* final)
2. Attestation integrity (UNTRUSTED_ATTESTER / INVALID_ATTESTATION final)
3. Independent replay (NONCONFORMANT if mismatch)
4. Conformance classification (VERIFIED_* if passed)

UNTRUSTED_ATTESTER never converts to NONCONFORMANT. UNVERIFIABLE_ENVIRONMENT
never converts to INVALID.

## 10. Trust bootstrap

### 10.1 Root of trust

- Trust store: docs/research/architecture/TRUSTED-IMPLEMENTATIONS-v0.json
- Signed releases: trusted-implementations-release-<version>.json + .sig
- Signature: Ed25519
- Bootstrap: TOFU via independent channel + human confirmation

### 10.2 Release object — boundary and canonicalization

release_payload := {
    release_version, trust_store_sha256, trust_store_previous_sha256,
    ratified_at, ratified_by, ... (all signed fields per
    TRUST-RELEASE-SCHEMA-v0, additionalProperties: false)
}

signature_envelope := { release_payload, signature_ed25519 }

release_object_sha256 = sha256(
    b"jamp:trust-release-object:v0:" + canonical_bytes(release_payload)
)

signature_ed25519 = sign(
    b"jamp:trust-release:v0:" + canonical_bytes(release_payload)
)

release_full = release_payload (NOT envelope). Envelope is separate
authentication layer. Signature change does NOT change release_object_sha256.

Processing order (normative):
1. Schema validation (structural) → RELEASE_PAYLOAD_INVALID if missing
   required fields or additional fields present
2. Signature verification → TRUST_RELEASE_SIGNATURE_INVALID
3. release_object_sha256 binding (INV-T9)

INV-T1. release.trust_store_sha256 == sha256(canonical_bytes(trust_store)).
INV-T2. release.trust_store_previous_sha256 ==
        previous_verified_release.trust_store_sha256.
INV-T11. release_object_sha256 over release_payload (not envelope), under
         jamp:trust-release-object:v0:. JCS canonicalization. Signature
         validity orthogonal.

### 10.3 Anti-rollback checkpoint

Path: ~/.local/state/jamp/trust-checkpoint.json (or $XDG_STATE_HOME).
Signed by verifier-local Ed25519 key.

### 10.3.0 Genesis (first-run)

G1. Bootstrap pubkey from independent anchor (env/config/flag). In-repo
    docs NOT sole source. Mismatch → TRUST_ANCHOR_UNVERIFIABLE.

G2.1 Human acceptance via interactive flag OR trusted channel. NOT
     cryptographic; independent action.

G2.2 Integrity of stored acceptance (MUST persist in Mode A):
     $JAMP_TRUST_ACCEPTED contains {fingerprint_sha256, accepted_release_
     version, accepted_trust_store_sha256, accepted_at, signature_by_
     local_key over ALL fields excluding signature}.
     Mode A (default): persistent. Mode B (--ephemeral-acceptance):
     no persistence, second guarantee NOT established, re-acceptance
     required each run.

G2.3 Local key lifecycle: ~/.local/state/jamp/verifier-key.priv mode 0600.
     Compromise if weaker mode / different owner / rollback declared.
     INV-T8 bounds claim.

G2.3a Rollback declaration ($JAMP_ROLLBACK_DECLARED):
     "1" → declared; unset/"" → not; other → TRUST_CONFIG_INVALID.
     Marker file ~/.local/state/jamp/ROLLBACK_DECLARED.
     On declaration → TRUST_ROLLBACK_DECLARED_BY_OPERATOR.
     Operator removes marker after recovery; NOT auto-cleared.

G3. Release signature verification (INV-T9 binding recorded as
    signature_verified_for.release_object_sha256).

G4. Genesis checkpoint creation. Records last_verified_release_version,
    last_verified_trust_store_sha256, last_verified_at,
    genesis_fingerprint_sha256.

G5. Proceed to regular flow.

INV-T6. Genesis requires (a) human acceptance via G2.1 and (b) integrity
        of acceptance record via G2.2 (Mode A) — two independent guarantees.

### 10.3.1 Regular flow (checkpoint exists)

Step 1. Checkpoint signature verification (first, before any use of
        checkpoint fields). Failure → TRUST_CHECKPOINT_TAMPERED or
        TRUST_CHECKPOINT_UNREADABLE (final).

Step 2. Release signature verification. Records signature_verified_for :=
        {release_object_sha256: sha256 over canonical release_payload
         under jamp:trust-release-object:v0:}.

Step 3. Version comparison (trusted checkpoint + trusted release):

   3a. Idempotent re-verify (latest.version == checkpoint.version):
       hashes match → accept, no update. Mismatch → TRUST_STORE_FORK_DETECTED.

   3b. Advance (latest.version > checkpoint.version) — reverse walk:

       3b.1 Precondition: signature_verified_for.release_object_sha256
            == sha256(latest.release_payload). Mismatch → TRUST_RELEASE_
            SIGNATURE_INVALID.

       3b.2 Reverse chain construction:
            current := latest
            chain := [current]
            while current.trust_store_sha256 != checkpoint.last_verified_
                  trust_store_sha256:
                P := predecessor(current)  # releases with trust_store_
                                           # previous_sha256 == current
                                           # .trust_store_sha256
                if |P| == 0: → TRUST_UNVERIFIABLE_CHAIN_GAP (final)
                if |P| > 1:  → TRUST_STORE_FORK_DETECTED (final)
                prev := P[0]
                verify prev.release_version < current.release_version
                  (strictly monotonic decreasing in reverse)
                verify Ed25519(prev) valid; else → TRUST_RELEASE_SIGNATURE_
                  INVALID (step in diagnostics)
                prepend prev
                current := prev
            finalize: if current.release_version != checkpoint.last_verified_
                      release_version: → TRUST_STORE_FORK_DETECTED
            forward_chain := reverse(chain)

       3b.3 Commit: atomically update checkpoint to vN values, re-sign.

   3c. Rollback (latest.version < checkpoint.version):
       → TRUST_ROLLBACK_DETECTED (final).

Step 4. Three levels distinguished:

       Level 1 — Bootstrap outcome: BOOTSTRAP_OK | BOOTSTRAP_FAILED:<reason>
               reasons: TRUST_CHECKPOINT_TAMPERED | TRUST_CHECKPOINT_
               UNREADABLE | TRUST_RELEASE_SIGNATURE_INVALID | TRUST_STORE_
               FORK_DETECTED | TRUST_ROLLBACK_DETECTED | TRUST_UNVERIFIABLE_
               CHAIN_GAP | TRUST_ANCHOR_UNVERIFIABLE | TRUST_RELEASE_NOT_
               FOUND | TRUST_CONFIG_INVALID | TRUST_ACCEPTANCE_MISMATCH |
               TRUST_ROLLBACK_DECLARED_BY_OPERATOR | TRUST_KEY_COMPROMISED

       Level 2 — Resolver (only if BOOTSTRAP_OK): returns one of 4 values.
               NOT called if BOOTSTRAP_FAILED.

       Level 3 — Verdict Report: BOOTSTRAP_FAILED → UNVERIFIABLE_TRUST_
               BOOTSTRAP with reason. Resolver UNTRUSTED_* → mirrors.
               Otherwise proceeds per §9.

INV-T3. Idempotent re-verify: version == and sha == → accept, no update.
INV-T4. Checkpoint signature verification precedes any use of checkpoint
        fields.
INV-T5. Advance requires: (a) latest passed Step 2 and its release_object_
        sha256 matches (INV-T9); (b) each predecessor independently
        signature-verified; (c) reverse walk bounded by predecessor links
        (INV-T7); (d) deterministic failure classification (Step 3b.2).
INV-T7. Chain reconstruction searches only backwards from latest via
        trust_store_previous_sha256 links. Releases not on reverse path
        from latest to checkpoint never considered. Fork detected only
        by multiple predecessors of a single step.
INV-T9. Signature verification bound to release_object_sha256 (full
        canonical release_payload). Reverse walk recomputes and compares.

### 10.4 Accepted MVP limitation

Checkpoint protects against: random corruption, partial restore, stale
checkpoint without matching private key.

Does NOT protect against: consistent (checkpoint, private_key) pair
restored from backup; active attacker with full FS access.

Automated backup/rollback detection NOT provided. Operator declaration
(G2.3a) + explicit recovery flow (G2.4) is MVP mechanism.

### 10.5 Recovery flow (G2.4) — RECOVERY_DESIGN_RC

STATUS: RECOVERY_DESIGN_RC — design direction ratified, crash consistency
and journal integrity NOT YET PROVEN. Known Issues listed in §17.1.
Implementation of recovery is NOT authorized until Known Issues are
resolved by separate addendum.

Direction (accepted):

- Explicit --recover-from-rollback flag required; no implicit entry.
- R1: rename old material (.compromised.<recovery_id> suffix), idempotent
  per file, journal tracks status.
- R2: fresh G1–G4 with new key. Mode A required.
- R3: clear rollback declaration. Marker removal only after R2 success.
- R4: RECOVERY_COMPLETE emitted only when marker gone AND R3 completed.
- Recovery journal: ~/.local/state/jamp/recovery-journal.json (unsigned
  operational state, NOT trust material).
- INV-T10: recovery journal-based, idempotent per phase.

Known Issues (see §17.1): crash consistency across R1-R3, journal
tampering, partial R2 recovery, R3/R4 postcondition reconciliation.

## 11. Implementation closure and hermetic execution

### 11.1 Closure schema

{
    closure_version, component, component_version,
    source_files: map[path → sha256],
    python: {version, implementation},
    dependencies: map[name → {version, wheel_sha256}],
    platform: {os, arch, libc},
    locale, timezone,
    env: {fixed, unset},
    resources: map[path → sha256],
    network: "disabled",
    filesystem: "read_only_except_tmp",
    environment: {type: oci_image | binaries, ...},
}

closure_sha256 = sha256(b"jamp:closure:v0:" + canonical_bytes(closure))

gate_sha256, evaluator_sha256, criterion_evaluator_sha256, evidence_
selector_sha256, reference_implementation_sha256, verifier_sha256 are
closure_sha256 values.

### 11.2 Hermetic execution

- Python exact version, wheels by wheel_sha256 (not PyPI)
- PYTHONHASHSEED=0, TZ=UTC, LC_ALL=C.UTF-8
- Network disabled, FS read-only except /tmp
- Timeout 300s, stdout/stderr/exit saved as evidence

Environment match:

| Situation | Status |
|---|---|
| Match + replay matches | VERIFIED_* |
| Match + replay mismatch | INVALID |
| Does not match / unavailable | UNVERIFIABLE_ENVIRONMENT |

INV-D3. UNVERIFIABLE_ENVIRONMENT never converts to INVALID.

## 12. Path safety

INV-PATH-1 (syntactic): relative, forward slashes only, no empty segments,
no . or .., no leading/trailing /, no NUL/control chars, matches regex:
^(?!\/)(?!.*\/\/)(?!.*(?:^|\/)\.\.?(?:\/|$))(?!.*\\)[A-Za-z0-9_.\-]+(\/[A-Za-z0-9_.\-]+)*\.[A-Za-z0-9]+$

INV-PATH-2 (semantic): openat2 with RESOLVE_NO_SYMLINKS | RESOLVE_BENEATH
| RESOLVE_NO_XDEV. Atomic kernel resolution relative to held root_fd.
root_fd held for lifetime. Successful open: fstat S_ISREG, read via fd
only. Failed: no fd, no read. NOT post-hoc realpath.

INV-PATH-3: symlink/junction escape or traversal → closure INVALID
(structural).

INV-PATH-4 (fail-closed): ELOOP/EAGAIN/EXDEV/ENOENT/other → ClosureInvalid
(INVALID). ENOSYS/EPERM → UNVERIFIABLE_ENVIRONMENT. No third path.

INV-PATH-5: openat2 retry on EAGAIN FORBIDDEN.

INV-PATH-6 (conformance invariant): successful open → S_ISREG, kernel
guarantees at resolution time; failed open → no content read. Specific
errno diagnostic only.

### 12.1 MVP environment

| Environment | Status |
|---|---|
| Linux ≥ 5.6 with openat2 + resolve flags | safe mode eligible |
| Linux ≥ 5.6 without openat2 | UNVERIFIABLE_ENVIRONMENT |
| Linux < 5.6 | UNVERIFIABLE_ENVIRONMENT |
| macOS, BSD | UNVERIFIABLE_ENVIRONMENT |
| Windows | UNVERIFIABLE_ENVIRONMENT (reparse protection pending) |

No manual-walk fallback.

## 13. Conformance testing

### 13.1 Rule conformance

5 class representatives (A–E), property-based invariance, clause-level
coverage. Guard clause tested as unreachable defensive.

### 13.2 Path safety conformance (T1–T5)

T1: external symlink component → openat2 fails ELOOP (RESOLVE_NO_SYMLINKS).
    No fd, no content. INV-PATH-6 holds via kernel guarantee.

T2: internal symlink component → INVALID (strict).

T3: ../ → INVALID (syntactic, before syscall).

T4: regular file inside root → PASS.

T5 race scenarios (verify INV-PATH-6, not specific errno):

  T5a: intermediate dir replaced by external symlink.
    Either open fails, or open succeeds with safe inode resolved inside
    root_fd before replacement. Unsafe open never permitted. Errno
    diagnostic only.

  T5b: target replaced by other regular file inside root.
    Open succeeds, invariant holds, success valid. Different valid
    closure config at open time.

  T5c: dir renamed outside root.
    Open fails or opens inode safely resolved inside root_fd before
    rename. Unsafe never permitted. Errno diagnostic.

T5 pseudocode:

    if fd is not None:
        assert S_ISREG(fstat(fd).st_mode)
        content = os.read(fd, ...)
        if scenario == "T5b":
            assert sha256(content) in expected_hashes_for_scenario_T5b
        else:
            assert sha256(content) == expected_hash_for_safe_open
        # Safety established exclusively by:
        #   (1) openat2 resolve flags relative to held root_fd
        #   (2) fstat(fd) regular inode
        # Hash verifies content only, NOT path safety. Unsafe file with
        # matching hash does not mask violation — no_unsafe_open_occurred
        # operates independently.
    else:
        assert no_fd_returned()
        assert not file_content_accessed()

    assert no_unsafe_open_occurred
    assert no_content_read_without_valid_fd

Path safety of successful open established only by:
(a) openat2 resolve flags relative to held root_fd,
(b) fstat(fd) S_ISREG.

Content hash confirms expected content only; cannot establish safe
resolution. no_unsafe_open_occurred independent of content hashes.

expected_hash is scenario-dependent:
- T5b: expected_hashes_for_scenario_T5b (set) — membership.
- T5a/T5c: expected_hash_for_safe_open (single) — only if open succeeded;
  if failed, no hash check.

### 13.3 Attestation conformance

Full test_cases (input/expected/actual, not summary). Verifier re-executes
independently, compares result_projection (result + unknown_reason +
selector_output + predicate_result), not just status.

test_run_evidence_ref in content-addressed durable storage, not GitHub
artifact.

Attester verifier_sha256 ∈ trust store for CONFORMANCE_BASED.

Conformance ≠ mathematical equivalence.

## 14. Domain separation

| Prefix | Object |
|---|---|
| jamp:verdict:v0: | verdict_id |
| jamp:verdict-object:v0: | verdict_object_ref |
| jamp:claim:v0: | claim_id |
| jamp:evaluation-refusal:v0: | refusal_id |
| jamp:evaluation-error:v0: | error_id |
| jamp:evidence-package:v0: | package_sha256 |
| jamp:chain-report:v0: | chain_report_sha256 |
| jamp:verdict-report:v0: | verdict_report_sha256 |
| jamp:gate-report:v0: | gate_report_sha256 |
| jamp:closure:v0: | closure_sha256 |
| jamp:conformance-attestation:v0: | attestation_id |
| jamp:aggregation-rule:v0: | aggregation_rule_sha256 |
| jamp:trust-release:v0: | signature domain |
| jamp:trust-release-object:v0: | release_object_sha256 |

Domain separation prevents semantic collision across types. SHA-256
collision resistance independent.

## 15. Evidence Package

Fields (8):

1. package_version        (semver)
2. package_schema_ref     (sha256)
3. chain_report_ref       (sha256)
4. verdict_ref            (sha256 = verdict_id)
5. verdict_object_ref     (sha256)
6. verdict_report_ref     (sha256)
7. package_created_at     (ISO8601)
8. package_sha256         (sha256)

package_sha256 = sha256(
    b"jamp:evidence-package:v0:" +
    canonical_bytes({version, schema_ref, chain_report_ref, verdict_ref,
                     verdict_object_ref, verdict_report_ref})
)

INV-P1..P4: cross-object references match.
INV-P5: verdict_object_ref = sha256 over canonical resolved verdict bytes.

Consumer protocol:
1. Verify package_schema_ref
2. Resolve referenced objects
3. Verify INV-P1..P5
4. Run #479 verifier → compare chain_report_ref
5. Run Verdict Report verification → compare verdict_report_ref
6. Verify verdict_ref == verdict.verdict_id and verdict_object_ref matches
7. Distinguish levels 1/2 from level 3

## 16. Determinism rules

INV-D1. len(invariants_checked) == 10 + 3K for K = len(criterion_results).
        Populated only if Verdict Report status ∈ {VERIFIED_*,
        NONCONFORMANT, INVALID}.

Position-to-invariant mapping:

Base (positions 1–7):

| Pos | INV | What |
|---|---|---|
| 1 | INV-V1 | spec_ref == resolved spec_hash |
| 2 | INV-V2 | criterion_set_ref resolves |
| 3 | INV-V3 | evidence_bundle_ref resolves |
| 4 | INV-V4 | aggregation_rule_sha256 matches |
| 5 | INV-V7 | gate_result reproduces (INV-V11 precondition) |
| 6 | INV-V8 | bijection with Criterion Set |
| 7 | INV-V10 | spec_gate_result.spec_ref == spec_ref |

Per-criterion (positions 8+3i .. 10+3i for i=0..K-1):

| Pos | INV | What |
|---|---|---|
| 8+3i | INV-V12 step 1 | selector closure resolved and replayed |
| 9+3i | INV-V12 step 2 | observed matches |
| 10+3i | INV-V12 step 3 | evaluator closure resolved, predicate replayed |

Final (positions 8+3K .. 10+3K):

| Pos | INV | What |
|---|---|---|
| 8+3K | INV-V5 | verdict_status == apply(rule, ...) |
| 9+3K | INV-V6 | verdict_id == sha256(projection) |
| 10+3K | INV-P5 | verdict_object_ref == sha256 canonical |

### 16.1 Invariants NOT in invariants_checked

| Layer | Invariants |
|---|---|
| Schema validation | INV-V9, INV-V14, INV-V15, INV-D2 |
| Resolver | INV-A7..A12 |
| Trust Bootstrap | INV-T1..T11, TRUST_* failures |
| Path safety | INV-PATH-1..6 |
| Package | INV-P1..P4 |
| Meta | INV-D1, INV-D3, INV-D4 |

INV-D2. claim_id per §5.4.
INV-D3. UNVERIFIABLE_ENVIRONMENT never → INVALID.
INV-D4. invariants_checked populated iff status ∈ {VERIFIED_*,
        NONCONFORMANT, INVALID}.

Fixed array order (JCS does not sort):

| Array | Order |
|---|---|
| criterion_results | Criterion Set order |
| invariants_checked | positions 1..(10+3K) |
| diagnostics | (code, field_key), nulls last |
| test_cases | case_id lex |
| source_files / deps / resources | key lex |

## 17. Explicit limitations (MVP)

1. Anti-rollback checkpoint does not protect against consistent
   (checkpoint, private_key) restore from backup. Accepted.
2. Windows replay → UNVERIFIABLE_ENVIRONMENT.
3. macOS, BSD, Linux < 5.6 → UNVERIFIABLE_ENVIRONMENT.
4. Active attacker with full FS access not defended.
5. Rule v0 no cross-criterion dependencies, priorities, weighted aggregation.
6. Conformance attestation = agreement on frozen suite, not equivalence.
7. NONCONFORMANT = result of specific frozen suite, not universal defect.
8. Byte-for-byte reproducibility requires oci_image environment.
9. Automated backup/rollback detection NOT provided (operator declaration
   + G2.4 recovery design only).

### 17.1 Known Issues — G2.4 Recovery (RECOVERY_DESIGN_RC)

The following counterexamples are reproducible from the current recovery
design. They are known and are NOT treated as resolved. Recovery
implementation is NOT authorized until they are addressed by addendum.

| # | Counterexample | Impact |
|---|---|---|
| K1 | Crash after marker removal but before R3_completed_at write | Journal-only recovery entry may not trigger on next run; marker-only configuration leaves no journal record |
| K2 | Journal unsigned; content controls R1/R2 skip | Tampering with R2_completed_at can skip bootstrap; operational state cannot serve as proof of trusted operation |
| K3 | Partial R2: new key created, acceptance written, checkpoint not yet | Repeat R2 may conflict on key/acceptance; R2 idempotency or verified-state resume not specified |
| K4 | R4 asserts journal exists with R3_completed_at, but R3 renames journal | Contradiction in postconditions; canonical completion state not defined |
| K5 | Target file name match does not prove identity of moved object | R1 idempotency check based on name alone is insufficient; content identity check not specified |

Additionally noted: entry condition of recovery flow does not consider
an incomplete journal when only marker-based declaration was used.

These are design-level issues for recovery, not for the rest of the
architecture. They do not block N1 freeze of Specification contract,
but they block Stage C implementation of recovery.

## 18. Non-goals (out of MVP scope)

- Probabilistic/fuzzy aggregation
- Cross-criterion dependency logic
- Nested verdicts
- Multi-domain rules
- Auto-rotation of bootstrap fingerprint
- Cross-platform byte-for-byte reproducibility (Linux ≥ 5.6)
- Real-time / streaming verdict evaluation
- LLM involvement in normative decision path
- Automated backup/rollback detection

## 19. Ratification record

Ratified: 2026-11-01
Base: main 2644857a5fc3ef55648d80f4d0e3c294a4c60975
Frozen Core: 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a (Δ=0)

Iterations consolidated: v0.1 → v0.4 → patches P1–P5, B1–B7, У1, У2 rev2,
Genesis G1–G5, G2.2 Mode A/B, G2.3 key lifecycle, G2.3a rollback
declaration, Step 3b reverse walk, Step 2→3b release_object_sha256
binding, release_payload boundary, recovery flow G2.4.

RC FREEZE. No further conceptual review of the full document. Changes
only via addendum with concrete counterexample from implementation or
tests.

Status summary:

- Verdict Architecture: RATIFIED (RC)
- Frozen Aggregation Rule v0: RATIFIED (RC)
- Evidence Package: RATIFIED (RC)
- Trust Bootstrap (non-recovery): RATIFIED (RC)
- Recovery Flow G2.4: RECOVERY_DESIGN_RC — design direction accepted,
  crash consistency not proven, 5 Known Issues open (§17.1)
- TRUST-RELEASE-SCHEMA-v0: REQUIRED before implementation, not in this
  document

Implementation: NOT AUTHORIZED.
Implementation requires separate explicit approval.
Recovery implementation additionally requires §17.1 Known Issues resolved.

Future changes: addendum PR with concrete counterexample.
