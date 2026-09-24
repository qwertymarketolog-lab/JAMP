# JAMP-1C Profile v0

Status: Design-Only Lock / reference implementation

JAMP-1C is a consumer/domain profile for applying JAMP evidence-first contracts to 1C configuration metadata, BSL modules, queries, and extension patches.

## 1. Scope and invariants

JAMP-1C MUST NOT modify src/jamp. Frozen Core invariant: Δ(src/jamp) = 0.

AI output is treated as an observation/hypothesis source, not as authority. Recommendations are never promoted to facts merely because an AI operator produced them.

## 2. Configuration snapshot identity

A configuration snapshot MUST be fixed before analysis starts.

source_ref canonical form: 1c://conf-sha256:<sha256>/<MetadataObject>
The configuration digest is part of source identity; the same metadata object in different snapshots is a different source.

## 3. Atomic identity preimage

The locked v0 preimage has exactly seven components:
v0 || source_ref || atom_type || operator_id || operator_version || C(content) || C(structural_identity)
The SHA-256 digest of the UTF-8 encoded preimage is the JAMP-1C atom id. The delimiter is the literal two-character sequence ||.

## 4. Atom type and payload kind

atom_type is the epistemic lifecycle type and MUST be observation, hypothesis, or evidence.
Payload content separately identifies its domain kind, such as bsl_query or extension_patch.

## 5. Structural identity vs source location

Only extension_name, module_type, and method_name participate in C(structural_identity).
span_start and span_end are context only and MUST NOT participate in the identity preimage.
Unknown identity keys are ignored by the closed allowlist and cannot become identity implicitly.

## 6. BSL/query canonicalization

Canonicalization MUST be tokenizer-based, never regex-only.
The reference tokenizer recognizes code, line_comment, block_comment, and string_literal_dq states.
Comments are removed only in comment states. Comment delimiters inside double-quoted strings are preserved.
Whitespace outside strings becomes one space. Keyword normalization is performed only on identifier/keyword tokens; string contents are never uppercased.
Malformed or unterminated lexical constructs MUST fail closed.

## 7. Canonical JSON

Canonical JSON uses sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False. Serialization failures are fatal.

## 8. Runtime telemetry separation

Execution time, DB lock duration, tempdb volume, session/user identifiers, and runtime counters MUST NOT enter the identity preimage. They belong to a separate execution/evidence envelope.

## 9. Fail-closed behavior

Registration MUST fail for missing required fields, malformed source_ref, unterminated strings/comments, non-canonical JSON, or forbidden semantic fields. There is no raw-text fallback.

## 10. Core integration

The reference implementation lives outside src/jamp. It may consume the standard JAMP AtomicObservation contract as an outer transport/evidence envelope, while preserving JAMP-1C domain identity as the domain identity.

## 11. Non-goals

v0 does not assert change safety, execute 1C code, benchmark production databases, infer causality from AI output, modify a 1C configuration, or modify the Frozen Core.

## 12. Verification target

Tests MUST establish comment/string handling, token-level keyword normalization, whitespace normalization, span invariance, closed-allowlist invariance, telemetry invariance, fail-closed malformed input, deterministic seven-component hashing, and Frozen Core non-mutation.