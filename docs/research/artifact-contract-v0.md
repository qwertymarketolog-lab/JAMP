# Artifact Contract v0 — specification

**Status:** specification only
**Scope:** Q3b.1
**Basis:** EXP-02, verified at `0fcc8dfe42f8f120926e24d3d2f96d068b3e5c74`

## Purpose

Define a neutral artifact shape for carrying a JAMP Run result together
with domain-specific payload, without requiring the artifact contract to
understand domain internals.

This document is a specification only. It does not implement or validate
a production exporter.

## Contract layers

The fields have three distinct sources of typing:

```text
Run contract
  → steps
  → iterations
  → stop_reason.kind/detail

Artifact contract
  → artifact_version
  → adapter
  → adapter_contract (optional)

Domain payload
  → final_state
  → provenance
  → opaque
```

Run-contract versioning and artifact-contract versioning are independent.
A future Run contract may be `v0.4` while this artifact specification
remains `v0`, or a future artifact version may change while the Run
contract remains unchanged.

## Metadata

### Artifact metadata — typed

```text
artifact_version: string
adapter:          opaque string identifier
adapter_contract: opaque string identifier, optional
```

Semantics:

- `artifact_version` identifies the version of this Artifact Contract.
- `adapter` identifies the domain/adapter using an opaque identifier.
- `adapter_contract`, when present, identifies the adapter interface or
  adapter contract version implemented by that adapter.
- `adapter` and `adapter_contract` are distinct fields and must not be
  conflated.

### RunResult — typed by the Run contract

```text
steps: int
iterations: int
stop_reason:
  kind: string
  detail: string
```

`stop_reason.kind` and `stop_reason.detail` are inherited from the Run
contract. The Artifact Contract does not redefine their semantics.

The artifact therefore carries Run-level typed information without
requiring knowledge of the domain state representation.

## Payload

The following fields are deliberately opaque to the Artifact Contract:

```text
final_state: any JSON-representable value
provenance:  any JSON-representable value
```

The contract asserts only that these values are JSON-representable.
It does not require a particular object, tuple, graph, expression, or
state representation.

Domain-specific interpretation belongs to the adapter/domain layer.

## Conceptual shape

```json
{
  "artifact_version": "v0",
  "adapter": "<opaque-domain-identifier>",
  "adapter_contract": "<opaque-adapter-contract-identifier>",
  "run_result": {
    "steps": 0,
    "iterations": 0,
    "stop_reason": {
      "kind": "<Run stop kind>",
      "detail": "<Run stop detail>"
    }
  },
  "final_state": "<opaque JSON payload>",
  "provenance": "<opaque JSON payload>"
}
```

`adapter_contract` is optional. An implementation may omit it when no
separate adapter contract identifier is available.

## Constraints

1. No field may assume domain-specific internal structure.
2. Run-level fields retain the semantics of the Run contract.
3. Artifact metadata is versioned independently from the Run contract.
4. `adapter` is an opaque identifier and is not interpreted by the
   Artifact Contract.
5. `adapter_contract` is optional and distinct from `adapter`.
6. `final_state` and `provenance` are opaque JSON-representable payloads.
7. The schema does not require semantic equivalence of provenance between
   domains.
8. The specification does not require a particular serialization library
   or implementation technique.

## Evidence basis

EXP-02 demonstrated a neutral artifact representation for two domains:

- Track A;
- 8-puzzle.

The 8-puzzle execution was anchored to:

```text
0fcc8dfe42f8f120926e24d3d2f96d068b3e5c74
```

with a clean working tree and two passing transfer/provenance tests.

This evidence motivates the specification but does not constitute a
validation of the specification as a production contract.

## Not claimed

- Third-domain neutrality.
- Production exporter transfer (Q3b).
- Semantic equivalence of provenance across domains.
- That this schema is minimal.
- That this schema is canonical.
- That this schema is stable across Run contract versions.
- That this specification is already a public or frozen API.
- That the specification proves universal domain independence of JAMP.

## Status and next step

**Q3b.1: SPECIFIED — not experimentally validated.**

No production exporter implementation is introduced by this document.
Any implementation or transfer test is a separate Q3b decision.
