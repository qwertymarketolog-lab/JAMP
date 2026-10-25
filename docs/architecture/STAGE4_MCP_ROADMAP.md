# Stage 4: MCP Tool Registry Roadmap

**Status:** DESIGN / NOT IMPLEMENTED  
**Scope:** Define the safety contract for registering and invoking external MCP tools. This document is a roadmap, not evidence that an MCP registry or enforcement runtime already exists.

## Security rule 1 — Tool Contracts and metadata

Before a model can invoke an MCP tool, JAMP must resolve the tool against an explicit registry entry and validate its contract: tool identity, server identity, input schema, declared capabilities, and relevant annotations such as `destructiveHint: true`.

- Treat server-provided metadata and annotations as claims, not proof of safety or authorization.
- A destructive hint, a missing contract, malformed metadata, an unknown tool, or a contract mismatch must fail closed: do not invoke the tool until the required policy and authorization checks pass.
- Apply least privilege: expose only the tools and arguments required for the approved task; do not let the model grant itself permissions.

## Security rule 2 — Independently verify results

A tool response such as “file saved” is an **OBSERVED** claim, not a verified outcome.

For file operations, JAMP should independently read back the target through a trusted verification path and compare the expected path, content, and cryptographic hash (for example, SHA-256) against the operation's declared postconditions. Record the tool response and the independent check as separate evidence.

- Promote `OBSERVED → VERIFIED` only when the independent check succeeds and the evidence is bound to the same operation and target.
- If read-back is unavailable, the hash/content differs, or provenance is incomplete, retain `UNKNOWN / INCONCLUSIVE`; never synthesize success from the tool's own response.
- Record operation ID, tool/server identity, target, timestamps, expected postconditions, observed result, verification method, and computed hash where applicable.

## Security rule 3 — Human-in-the-Loop for destructive actions

Deletion, overwrite, irreversible changes, external publication, and other policy-classified destructive actions require explicit human confirmation before execution.

- Present the exact tool, target, action, and material consequences for approval.
- Bind approval to the specific operation and arguments; any material change requires a new approval.
- Silence, prior unrelated approval, model confidence, or a tool's own metadata is not consent.
- Without valid approval, refuse the call and preserve the decision and reason in the evidence record.

## Proposed implementation sequence

1. Define a versioned Tool Contract schema and registry entry format.
2. Add a fail-closed policy evaluator for tool identity, schemas, annotations, capabilities, and authorization.
3. Define operation-scoped approval records for destructive actions.
4. Add independent postcondition verifiers, beginning with file read-back and SHA-256 checks.
5. Add adversarial test vectors: unknown tools, forged/missing hints, schema drift, false success messages, mismatched hashes, replayed approval, and changed arguments.
6. Require terminal CI evidence for each gate before promoting the registry from design to runtime.

## Exit criteria

Stage 4 is not VERIFIED until tests demonstrate that unauthorized or ambiguous tool calls are blocked, destructive calls require operation-scoped human approval, and successful outcomes are independently verified with traceable evidence. Documentation alone does not satisfy these criteria.
