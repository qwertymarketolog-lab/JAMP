# EXP-NEEDLE-01 — Edge Adapter Contract v0

## Status

- State: OPEN
- Scope: contract-only
- Real Needle runtime: NOT CONNECTED
- Frozen Core: LOCKED
- Required invariant: `Δ(src/jamp/run.py) = 0`

## Objective

Define the boundary between a local AI sensor (Needle-class runtime) and JAMP evidence handling without changing the Frozen Core.

The adapter accepts model observations or action proposals and converts them into evidence-bearing records. The adapter does not establish truth, causality, authorization, or verification by model confidence.

## Roles

### AI sensor

The AI sensor may:

- extract structured observations;
- propose a tool invocation;
- produce an embedding for retrieval.

The AI sensor is an observation source, not an authority.

### JAMP

JAMP is responsible for:

- schema validation;
- canonicalization;
- provenance binding;
- hashing;
- conflict preservation;
- constraint checks;
- deterministic arbitration;
- execution authorization;
- final verification state.

## Observation contract

A normalized observation MUST contain:

- `observation_id`
- `source`
- `model_id`
- `model_version`
- `input_hash`
- `output_hash`
- `payload`
- `timestamp`

The payload MUST represent observed/extracted data, not an unverified causal conclusion.

Example:

```json
{
  "observation_id": "obs-...",
  "source": "needle",
  "model_id": "needle-3",
  "model_version": "UNSPECIFIED",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "payload": {
    "temperature_c": 73.2,
    "fan": "on",
    "network": "unstable"
  },
  "timestamp": "..."
}
```

## Action proposal contract

An action proposal MUST contain:

- `proposal_id`
- `tool`
- `arguments`
- `source_observation_ids`
- `input_hash`
- `output_hash`

A proposal is never an authorization to execute.

The execution path is:

```
proposal
  -> evidence/provenance checks
  -> constraint checks
  -> deterministic arbitration
  -> ACCEPTED or REJECTED/INCONCLUSIVE
  -> execution only after acceptance
  -> resulting observation
```

## Fail-closed requirements

The adapter MUST NOT silently accept:

- invalid structured output;
- schema mismatch;
- missing provenance fields;
- unknown tools;
- constraint violations;
- unresolved observation conflicts;
- missing required evidence.

Required states are:

- `REJECTED` when a contract/input requirement is violated;
- `CONFLICT` when incompatible observations must be preserved;
- `INCONCLUSIVE` when evidence is insufficient to decide;
- `UNKNOWN` when the requested fact is not established.

No synthetic PASS is permitted.

## Embeddings

Embeddings are out of scope for v0 verification.

If introduced later, embeddings MAY support retrieval or similarity search but MUST NOT by themselves establish identity, truth, authorization, or causality.

## Provenance

Every accepted observation MUST retain enough metadata to reproduce its evidence identity:

```
source
model_id
model_version
input_hash
output_hash
timestamp
```

The adapter MUST NOT rewrite provenance after acceptance.

## Frozen Core boundary

This contract MUST NOT require modifications to:

```
src/jamp/run.py
```

The locked blob remains:

```
0fee0e1c5c1a1548361965ac51eacdeba62bfe8a
```

Any future Core change requires an explicit Core Unlock decision and separate evidence.

## EXP-NEEDLE-01 acceptance criteria

1. Contract exists independently of the production runtime.
2. No Needle runtime dependency is introduced.
3. No tool is executed by the contract.
4. Observation and action-proposal boundaries are explicit.
5. Provenance fields are mandatory.
6. Fail-closed states are explicit.
7. Embeddings remain non-authoritative.
8. `src/jamp/run.py` is byte-for-byte unchanged.
9. The change is limited to the EXP-NEEDLE-01 contract surface.
10. CI evidence, when available, is evaluated separately from contract correctness.

## Non-goals

- benchmarking Needle;
- claiming Needle accuracy;
- claiming causal inference;
- modifying JAMP Core;
- adding production dependencies;
- executing edge actions;
- declaring runtime performance;
- declaring CI PASS without terminal evidence.
