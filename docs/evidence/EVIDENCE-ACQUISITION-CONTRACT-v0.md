# JAMP — Evidence Acquisition Contract v0

**Status:** DESIGN-ONLY / PRE-FREEZE  
**Contract version:** evidence-acquisition-v0  
**Scope:** reusable execution evidence for Research OS probes, including AnyModel R18–R24  
**Execution:** NONE — this specification does not authorize model/API execution  
**Frozen Core:** unchanged; src/jamp/run.py remains out of scope

## 1. Purpose

Define the minimum reusable contract that turns one execution into a replayable, content-addressed evidence bundle.

Pipeline:

    PREFLIGHT
      ↓
    EXECUTION ENVELOPE
      ↓
    FROZEN INPUT
      ↓
    RAW OUTPUT / TRANSPORT
      ↓
    ATOMIC OBSERVATION
      ↓
    DETERMINISTIC CHECKER
      ↓
    EVIDENCE BUNDLE
      ↓
    REPLAY / VERIFY

The contract closes the structural gap represented by historical AnyModel v3 execution_id = null without modifying the Frozen Core or retroactively upgrading historical evidence.

## 2. Normative principles

1. Execution identity MUST exist before the external/model call.
2. Every derived object MUST be bound to the execution identity and content digests.
3. Raw input and raw output MUST be preserved byte-for-byte or by an explicitly frozen canonical representation.
4. Derived verdicts MUST be produced by a versioned deterministic checker.
5. Replay MUST operate from the evidence bundle only; provider/API access is forbidden during replay.
6. Missing required evidence remains INCONCLUSIVE; no field may be synthesized from catalog metadata or prose.
7. A valid digest proves content integrity, not execution causality by itself.
8. Historical v3 artifacts MUST NOT be rewritten to satisfy this contract.
9. This contract MUST NOT alter src/jamp/run.py.
10. Provenance binding fields MUST resolve to the exact frozen specification, criterion set, concrete implementation, and captured environment used by the execution.

## 3. Execution envelope

The execution envelope is created before execution and is immutable after finalization.

Required fields:

| Field | Requirement |
|---|---|
| contract_version | evidence-acquisition-v0 |
| execution_id | globally unique, generated before execution |
| execution_created_at | UTC timestamp generated before execution |
| execution_started_at | UTC timestamp captured immediately before payload execution |
| execution_finished_at | UTC timestamp captured after execution terminates |
| git_sha | exact repository checkout SHA |
| probe_sha | exact probe/runner code identity |
| workflow_sha | workflow-definition identity when executed by CI |
| target_ref | branch/tag/ref used for the execution |
| entrypoint | exact executable entrypoint |
| pid | process identifier when available |
| process_started_at | process start timestamp when available |
| cwd | execution working directory |
| runtime_identity | language/runtime version and implementation |
| environment_digest | digest of allowlisted environment metadata |
| argv_digest | digest of canonicalized non-secret execution arguments |
| input_digest | digest of the frozen input record |
| spec_hash | exact frozen Specification hash used by the execution |
| criterion_set_hash | exact frozen Criterion Set hash used by the execution |
| implementation_ref | concrete implementation identity used by the execution; MUST resolve to the exact implementation version, never `latest`/symbolic `current` |
| environment_ref | concrete reference to the captured environment record used by the execution; MUST resolve to the environment represented by `environment_digest` |
| status | terminal execution state |

### 3.1 Provenance binding semantics

The four Provenance Contract v0 Execution fields bind as follows:

- `spec_hash` MUST equal the frozen Specification's `spec_hash`.
- `criterion_set_hash` MUST equal the frozen Criterion Set's `criterion_set_hash`.
- `implementation_ref` MUST identify the concrete implementation version actually executed. For repository-backed execution, it MUST resolve to the execution's `git_sha` together with the exact `probe_sha` and `entrypoint`; `git_sha` remains the checkout identity and is not replaced by `implementation_ref`.
- `environment_ref` MUST identify the captured environment record whose content is committed by `environment_digest`; it MUST NOT be a symbolic environment label such as `current`, `latest`, or `runner-default`.

These fields are references/bindings, not new verdict semantics. They make the Evidence Acquisition execution envelope conformable with Provenance Contract v0 without redefining Provenance Contract v0.

For a CI execution, `workflow_sha` remains the workflow-definition identity and MUST NOT be substituted for `git_sha`, `implementation_ref`, or `spec_hash`.

## 3.2 Environment boundary

Environment capture MUST be allowlisted and MUST exclude secrets.

Minimum useful runtime identity:
- OS/platform identifier;
- runtime implementation and version;
- executable identity;
- architecture;
- dependency-lock or dependency-set digest where available;
- hostname/runner identity only when policy permits;
- process identity fields.

Secrets, API keys, authorization headers, cookies, and full environment dumps MUST NOT enter the evidence bundle.

## 3.3 Git binding

For repository-backed execution, git_sha MUST identify the exact checked-out source used by the entrypoint.
The workflow definition SHA and checkout SHA remain separate facts.
A synthetic merge SHA MUST NOT substitute for the actual checkout SHA.

## 4. Frozen input record

Each probe execution MUST persist the exact input consumed by the executable component.

Required fields:
- contract_version;
- execution_id;
- probe_id;
- model_id where applicable;
- canonical task/input payload;
- payload encoding/canonicalization version;
- input_digest;
- creation timestamp;
- relevant contract/checker version.

The frozen input is immutable.
For R18–R24, this record MUST satisfy r18-r24-frozen-input-v0.

## 5. Raw transport/output record

The raw output record preserves what the external system returned before interpretation.

Required fields:
- execution_id;
- request/input digest;
- provider endpoint identifier;
- HTTP/status or equivalent transport status;
- response headers only from an explicit allowlist;
- exact raw response or content-addressed raw-response object;
- raw_response_digest;
- elapsed transport time;
- response timestamp;
- terminal transport state.

Authorization material MUST NOT be stored.
A transport error is evidence of transport state, not automatically evidence of model non-compliance.

## 6. Atomic observation binding

The contract reuses the existing JAMP AtomicObservation identity layer; it does not replace or modify the Frozen Core.

Every atomic observation MUST reference:
- execution_id;
- frozen-input digest;
- raw-output digest, when applicable;
- probe_id;
- operator_id;
- operator_version;
- observation content;
- existing AtomicObservation identity.

The observation identity MUST be deterministically reproducible from its canonical preimage.
No semantic verdict may be smuggled into a supposedly neutral observation envelope.

The observation layer records what was observed. The checker layer determines what the frozen predicate means.

## 7. Deterministic checker contract

Every checker used for qualification MUST declare:
- checker_id;
- checker_version;
- checker source/content digest;
- input schema version;
- deterministic canonicalization rules;
- required input digests;
- output schema;
- acceptance predicate;
- rejection predicate;
- inconclusive predicate;
- self-test/reference fixtures.

A checker MUST fail closed when a required input is missing, malformed, or hash-inconsistent.
For R23/R24, the checker result MUST be independently generated from the model response and frozen task/input. The model response MUST NEVER serve as the checker oracle.

## 8. Evidence bundle

One execution produces one immutable evidence bundle.

Minimum manifest:

    bundle_version
    execution_id
    execution_envelope_digest
    frozen_input_digest
    raw_output_digest
    atomic_observation_ids[]
    checker_id
    checker_version
    checker_digest
    checker_input_digest
    checker_output_digest
    final_status
    created_at

Recommended physical layout:

    bundle/
      manifest.json
      execution.json
      input/
        frozen-input.json
      raw/
        response.bin
        transport.json
      observations/
        <observation-id>.json
      checker/
        contract.json
        input.json
        output.json
      hashes.json

The manifest MUST commit to every referenced object by digest.
The bundle MUST be self-contained for offline verification.

## 9. Integrity and provenance chain

Minimum chain:

    git_sha
      ↓
    probe_sha / workflow_sha
      ↓
    execution_id
      ↓
    input_digest
      ↓
    raw_response_digest
      ↓
    atomic_observation_id
      ↓
    checker_digest
      ↓
    checker_output_digest
      ↓
    bundle_digest

Each arrow represents an explicit recorded reference or deterministic derivation.
Hash equality proves content equality. It MUST NOT be described as proof of real-world execution unless the execution envelope itself is independently authenticated by the execution environment.

Public-key signing is deliberately out of scope for v0. v0 establishes the canonical evidence structure and hash bindings first; signing can be added as a new contract version without changing bundle semantics.

## 10. Replay contract

Replay is an offline verification operation.

Given only the evidence bundle, replay MUST:
1. verify the manifest;
2. verify every referenced digest;
3. verify execution/input/output relationships;
4. verify AtomicObservation identities;
5. load the declared checker version;
6. execute the checker against the frozen checker input;
7. compare regenerated checker output with stored checker output;
8. emit REPLAY_VERIFIED only when all required comparisons match.

Replay MUST NOT:
- call the model/provider;
- perform network retrieval unless a future contract explicitly freezes retrieved inputs inside the bundle;
- replace missing evidence with current catalog data;
- mutate the bundle;
- silently upgrade checker versions.

A checker-version mismatch is REPLAY_INCONCLUSIVE, not PASS.

## 11. State machine

    DESIGNED
      ↓
    PREFLIGHT_VERIFIED
      ↓
    EXECUTING
      ↓
    CAPTURED
      ↓
    CHECKED
      ↓
    BUNDLED
      ↓
    REPLAY_VERIFIED

Failure or missing evidence transitions to an explicit terminal state:
- FAILED — a required deterministic assertion failed;
- INCONCLUSIVE — required evidence/checker input is missing or unresolved;
- INTEGRITY_FAILURE — a stored digest/reference does not verify.

No state transition may be inferred from absence of errors.

## 12. Qualification boundary

An evidence bundle MAY support qualification only when:
- execution identity is present;
- frozen input is complete;
- raw output is bound;
- required atomic observations are valid;
- applicable deterministic checkers are terminal;
- bundle integrity verifies;
- replay verifies where replay is required by the qualification contract.

A bundle with valid hashes but unresolved execution authentication remains content-integrity verified / execution-authentication unresolved.

This preserves the distinction between OBSERVED → VERIFIED → INFERRED → UNKNOWN.

## 13. Relationship to existing contracts

This contract is additive.

It complements:
- Execution Preflight Contract;
- AnyModel R18–R24 Frozen Input Contract v0;
- EXP-22 AtomicObservation identity;
- existing provenance contracts;
- existing reliability-audit schemas.

It does not redefine their existing semantics.

In particular:
- preflight proves execution prerequisites before launch;
- this contract binds the resulting execution evidence;
- Provenance Contract v0 requires frozen Specification, Criterion Set, concrete implementation, and environment references; this contract carries those bindings in the execution envelope;
- R18–R24 defines the semantic inputs required by those checks;
- AtomicObservation provides deterministic observation identity;
- replay verifies the stored deterministic derivation without contacting the provider.

## 14. Non-goals

v0 does not:
- execute models;
- rerun the historical 87-model AnyModel audit;
- modify historical v3 evidence;
- modify the audit runner;
- modify GitHub workflows;
- implement signing;
- modify thresholds;
- create a qualification gate;
- modify src/jamp/run.py.

## 15. Freeze rule

This document is DESIGN-ONLY / PRE-FREEZE.
No implementation may claim conformance until a separate implementation contract/test suite exists.
Any normative change to field semantics, canonicalization, hash construction, replay behavior, or state transitions requires a new contract version.
