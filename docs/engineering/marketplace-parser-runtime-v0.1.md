# Marketplace Parser Runtime Contract v0.1

Status: DESIGN-ONLY

## Purpose

Define the runtime boundary for marketplace ingestion without implementing network access, marketplace-specific HTTP calls, or parser execution.

Runtime chain:

`Transport -> Raw Payload -> Extractor -> Canonical Normalizer -> RawObservation`

Supported marketplace identities:

- Ozon
- Wildberries
- Yandex Market

## Components

### Transport

Abstract input boundary:

- accepts a marketplace request descriptor;
- returns an opaque raw payload plus retrieval metadata;
- MUST NOT assign claim truth status;
- runtime implementation is out of scope for v0.1.

A transport failure is a transport failure. It MUST NOT be converted into `UNKNOWN` product facts.

### Extractor

Marketplace-specific transformation:

`RawPayload -> ExtractedField[]`

Each extracted field MUST preserve:

- source marketplace;
- source locator/key;
- raw value;
- retrieval timestamp;
- observation timestamp when available.

Missing or ambiguous source fields produce no invented value.

### Canonical normalizer

Maps extracted fields to existing canonical attributes:

- `material`
- `width_mm`
- `height_mm`
- `doors_count`

Normalization MUST be deterministic.

Examples:

- `"850 мм"` -> `850` for `width_mm`;
- malformed or ambiguous numeric text -> `UNKNOWN`;
- unsupported unit conversion -> `UNKNOWN`;
- absent source field -> `UNKNOWN`.

Normalization does not promote a claim to `VERIFIED`.

### RawObservation output

The parser runtime emits observations only.

Required provenance fields:

- `marketplace`
- `source_locator`
- `observed_at`
- `retrieved_at`
- `raw_value`
- `canonical_attribute`
- `normalized_value`
- `status`

Allowed parser statuses:

- `OBSERVED`
- `UNKNOWN`

`VERIFIED` MUST NOT be emitted by the parser.

## Offline fixture contract

Runtime parser development MUST be testable from committed offline payload fixtures.

Fixtures MUST:

- contain representative raw marketplace payloads;
- identify marketplace and source format;
- be deterministic inputs;
- require no network access;
- preserve enough source context to reproduce extraction and normalization.

No fixture may be treated as evidence of live marketplace availability.

## Fail-closed rules

The parser MUST NOT:

- fabricate missing fields;
- infer product attributes from unrelated fields;
- convert transport errors into product claims;
- emit `VERIFIED`;
- silently discard provenance;
- perform external API calls as part of contract tests.

Unknown, malformed, unsupported, or ambiguous input remains `UNKNOWN`.

## Explicit non-goals

This contract does not implement:

- HTTP clients;
- browser/headless automation;
- marketplace API authentication;
- live marketplace requests;
- retry/rate-limit policy;
- production scheduling;
- EvidencePolicy promotion;
- Qualification Engine execution.

Those concerns belong to subsequent runtime layers.

## Compatibility

This contract consumes the existing MarketplaceSourceAdapter and deterministic normalization contracts and produces observations suitable for AEW/Evidence Ledger integration.

Frozen Core invariant:

`src/jamp/run.py` MUST remain unchanged.

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected delta:

`Δ(src/jamp/run.py) = 0`

No CI configuration or runtime implementation is changed by this document.
