# Wildberries Belarus Parser Profile v0.1

Status: DESIGN-ONLY / EVIDENCE-GATED

## Purpose

Define a Belarus-specific source profile for the future Wildberries parser without
claiming that public catalog parsing or any undocumented endpoint is currently
available.

This profile is an extension of the marketplace parser contract and does not
implement transport, scraping, authentication, extraction, normalization, or
qualification.

## Current evidence

Wildberries publishes Belarus-specific seller documentation and states that WB
API can be used by sellers from Belarus to exchange data with their store.
Authentication/token requirements apply to that API.

The existence of a Belarus-specific seller API is NOT evidence that an
unauthenticated public product/catalog endpoint is available for JAMP parsing.

Therefore:

- `wildberries_by` is a source profile identifier;
- live transport remains UNKNOWN;
- public catalog endpoint remains UNKNOWN;
- raw payload shape remains UNKNOWN until captured from an allowed source;
- no fixture may be synthesized from undocumented assumptions.

## Source profile

| Field | Contract |
|---|---|
| marketplace | `wildberries` |
| region | `BY` |
| profile_id | `wildberries_by` |
| transport | UNKNOWN until evidenced |
| authentication | source-dependent; never embedded in fixtures |
| currency/locale | source-observed; never inferred |
| product identifier | preserve source identifier exactly |
| source locator | mandatory |
| retrieved_at | mandatory for captured evidence |
| observed_at | parser output only when present in source |

## Parser boundary

The intended boundary remains:

`transport -> raw payload -> extractor -> canonical normalizer -> RawObservation`

For Belarus, the extractor MUST NOT assume:

- `nm_id` is the only identifier;
- Russian-language attribute names;
- transliteration of values;
- Belarusian/Russian locale equivalence;
- currency conversion;
- a particular undocumented JSON nesting.

Any unsupported or ambiguous shape MUST produce `UNKNOWN`, not a fabricated
canonical value.

## Canonical mapping

The following mappings are requirements to test, not pre-existing facts about
the source:

- source product identifier -> `product_id`;
- material-like attribute -> `material`;
- width-like attribute -> `width_mm`;
- height-like attribute -> `height_mm`;
- door-count attribute -> `doors_count`.

Normalization of units, language, or spelling MUST be explicit and deterministic.
If deterministic normalization cannot be justified from source evidence, the
result remains `UNKNOWN`.

## Fixture gate

Before adding a Belarus fixture to PR #268, capture an exact raw payload from
an allowed source and record:

- source locator;
- retrieval timestamp;
- raw payload hash;
- source/profile identifier;
- exact identifier fields;
- exact attribute nesting and value types.

The fixture MUST remain offline and MUST NOT be presented as live evidence.

## Test-vector gate

Before extending PR #269, define Belarus vectors only from the captured fixture.
Positive vectors require observed source values. Fail-closed vectors MUST cover
missing, malformed, ambiguous, and unsupported-unit cases.

Allowed parser statuses:

- `OBSERVED`
- `UNKNOWN`

`VERIFIED` is prohibited at the parser boundary.

## Non-goals

This change does not:

- call Wildberries;
- scrape public pages;
- add credentials;
- add an HTTP client;
- add browser/headless execution;
- modify CI;
- implement a runtime parser;
- change EvidencePolicy or QualificationEngine.

## Frozen Core

`src/jamp/run.py` MUST remain unchanged.

Frozen Core blob:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Expected:

`Δ(src/jamp/run.py) = 0`
