# JAMP CLI + UI + JSON API Contract

Status: architecture contract / design-only
Scope: CLI, UI, and JSON resource boundaries
Implementation status: not implemented
Frozen Core: `src/jamp/run.py` remains untouched

## 1. Purpose

This document defines the minimum interface contract for JAMP Research OS.

The interface is an evidence viewer and execution surface. It does not become an authority over research results.

Core principle:

`AI → Observation → JAMP Evidence → Verification → Conflict → Decision`

The UI and CLI must expose evidence, provenance, conflicts, and state without smoothing uncertainty.

## 2. Architectural boundary

```
UI
 │
 ▼
JAMP CLI / API
 │
 ├── Evidence
 ├── Provenance
 ├── Conflict
 └── Experiment state
 │
 ▼
Frozen Core
src/jamp/run.py
```

The interface must not modify or bypass the Frozen Core.

## 3. Minimal CLI contract

```
jamp experiment list
jamp experiment run <experiment-id>
jamp experiment status <experiment-id>

jamp evidence show <evidence-id>
jamp evidence raw <evidence-id>
jamp evidence verify <evidence-id>

jamp conflict show <experiment-id>

jamp provenance show <evidence-id>

jamp audit show <experiment-id>
```

CLI requirements:

- preserve raw observations;
- never silently coerce missing evidence into success;
- expose verification state separately from observation state;
- expose provenance references;
- expose conflicts rather than resolving them by majority or model authority.

## 4. Minimal UI screens

### Dashboard

Shows:

- experiments and their states;
- observation counts;
- verification counts;
- unknown/inconclusive counts;
- conflict counts;
- available artifacts.

### Experiment

Shows:

- experiment ID and version;
- current state;
- question and relevant hashes;
- model/sensor list;
- observations;
- conflict matrix;
- artifacts;
- provenance;
- audit evidence.

### Observation

Shows:

- observation ID;
- model/sensor;
- status;
- raw response;
- parsed representation;
- normalized answer;
- error, if present;
- provenance references.

### Conflict Matrix

The matrix displays deterministic pairwise relations:

- `AGREEMENT`
- `CONFLICT`
- `UNKNOWN`

A matrix relation is not a judgment about which model is correct.

### Evidence / Provenance

The UI must preserve the evidence chain:

```
RAW
 ↓
PARSED
 ↓
NORMALIZED
 ↓
DERIVED
 ↓
VERIFIED / INCONCLUSIVE
```

## 5. JSON resource contract

Experiment resource:

```json
{
  "experiment_id": "EXP-MULTI-AI-V0",
  "state": "RUNNING",
  "observations": [],
  "conflict_matrix": {},
  "artifacts": [],
  "provenance": []
}
```

Observation resource:

```json
{
  "observation_id": "...",
  "model": "am/gpt-oss-20b",
  "status": "OBSERVED",
  "raw_response": "...",
  "parsed": {},
  "normalized_answer": "...",
  "error": null
}
```

Verification resource:

```json
{
  "status": "VERIFIED",
  "checks": [],
  "evidence_refs": []
}
```

These examples define the minimum shape, not a final implementation schema.

## 6. State contract

Supported research states:

```
OPEN
  ↓
RUNNING
  ├── VERIFIED
  ├── FAILED
  └── INCONCLUSIVE
```

Important distinctions:

- `UNKNOWN` is not `FAILED`;
- `UNKNOWN` is not `PASS`;
- `INCONCLUSIVE` is not `VERIFIED`;
- missing evidence is not synthetic PASS.

State transitions require evidence.

## 7. UI safety rules

The interface must not:

- select a “best” model;
- rank models by authority;
- hide disagreement;
- turn missing evidence into PASS;
- replace raw observations with summaries;
- mix PR CI evidence with post-merge main evidence;
- alter an experiment contract to improve its displayed result.

## 8. Non-goals

This contract does not implement:

- a mobile application;
- a web application;
- authentication;
- a production API server;
- experiment scheduling;
- model billing;
- model selection or ranking.

Those are future implementation decisions.

## 9. Frozen Core invariant

No CLI, UI, or JSON API work described here authorizes a change to:

`src/jamp/run.py`

The current Frozen Core blob remains:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Default invariant:

`Δ(src/jamp/run.py) = 0`

## 10. Design status

This is a contract for future implementation, not evidence that the application exists.

Implementation should begin only after the underlying Evidence, Provenance, Conflict, and experiment interfaces are sufficiently stable.
