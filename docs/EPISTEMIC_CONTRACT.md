# JAMP Epistemic Contract

**Version:** 1.0.0  
**Status:** AUTHORING BASELINE — vocabulary is observed; some aggregate semantics remain unimplemented or unproven.  
**Baseline:** `main` at `3996ac81738403be0fd70d5fa4654b871dd65068`.

This contract separates (1) provider-level factual checks, (2) claim and aggregate verdicts, and (3) persisted Dashboard labels. Identical words at different levels are not interchangeable. A status is a bounded result for a particular claim, source, value, and observation time—not a claim that the model intentionally lied or that a fact is eternally true.

## 1. Epistemic rules

- **Integrity is not truth.** A matching SHA-256 proves that the bytes being checked match the recorded digest. It does not prove that the source is authoritative, current, complete, or factually correct.
- **Transport success is not verification.** HTTP success is necessary for the current HTTP-backed adapters, but a valid response must also be parsed, matched to the requested entity/field, and compared using the source-specific rule.
- **Unknown is not false.** Missing identifiers, unsupported claim types, unavailable sources, malformed responses, missing values, or out-of-scope questions must not be converted to `CONTRADICTED`.
- **Scope is bounded.** A verdict applies only to the fields and observation represented by its evidence. It does not validate surrounding prose.
- **No universal freshness guarantee.** A response timestamp/trade date must be retained where available. The current adapters do not establish a universal maximum-age policy.
- **No inferred provider hierarchy.** MOEX ISS and CoinGecko are domain-specific adapters. The inspected implementation contains no general cross-provider precedence or conflict-resolution policy.

## 2. Provider E4 statuses (internal adapter results)

Both `src/jamp/provider/moex_verify.py` and `src/jamp/provider/coingecko_verify.py` expose the following E4 vocabulary:

| Status | Meaning | Boundary |
|---|---|---|
| `E4_VERIFIED` | The adapter found the requested supported fact and the observed value met its source-specific comparison rule. | Only the checked entity/field/value and returned evidence are covered. |
| `E4_CONTRADICTED` | The adapter obtained usable source data and the checked claim failed the source-specific comparison, or an existence lookup returned a definitive not-found result where that adapter treats it as contradiction. | Does not establish intent, model deception, or falsity of unrelated text. |
| `E4_OUT_OF_SCOPE` | The requested fact is outside the adapter's supported evidence scope, or the adapter cannot interpret the absence as a contradiction. | Not false; not verified. |
| `E4_INCONCLUSIVE` | The adapter could not safely reach a result because input, transport, response, parsing, or required value was invalid/unavailable. | Not false; not true. |

Important provider-specific distinction:
- MOEX ticker absence returns `E4_OUT_OF_SCOPE`; it is not proof that a company/security does not exist elsewhere.
- CoinGecko prediction claims return `E4_OUT_OF_SCOPE`. A CoinGecko 404 for an existence claim is currently treated as `E4_CONTRADICTED`; a 404 for numeric price/market-cap claims is `E4_OUT_OF_SCOPE`.
- The adapters' `_get_json` capture path records status code, complete response body bytes (base64), and SHA-256. This is source evidence capture, not by itself semantic verification.

## 3. Claim-level signed verdict statuses

The public `JampVerdict.status` parser in `src/jamp/runtime/verdict.py` accepts exactly:

| Status | Human meaning | What the current code proves |
|---|---|---|
| `VERIFIED` | The verdict producer reports that its bounded verification succeeded. | The parser accepts this label. The label alone does not independently prove HTTP status, raw-body hash, source authority, freshness, or numeric tolerance. The provider E4 evidence and execution path must be inspected. |
| `CONTRADICTED` | The verdict producer reports a bounded contradiction. | The parser accepts this label. It does not prove that a model lied or that the whole response is false. |
| `INCONCLUSIVE` | The verdict producer could not establish truth or contradiction. | The parser accepts this label. It is an explicit unknown, not a negative finding. |

The `Claim` dataclass stores a string `status`; it does not itself enforce an enum. The public signed `JampVerdict.from_dict()` boundary does enforce the three-value set above.

**Do not collapse E4 and claim statuses without evidence.** The provider adapters return `E4_*` values. The claim model and signed verdict use a different vocabulary. Any conversion must be explicit and tested at the adapter boundary.

## 4. Aggregate statuses

`aggregate_verdict()` in `src/jamp/runtime/verdict.py` currently returns:

| Status | Exact current aggregation rule |
|---|---|
| `CONTRADICTED` | At least one claim has `CONTRADICTED` or `E4_CONTRADICTED`. This check has precedence over the other rules. |
| `INCONCLUSIVE` | No contradiction matched, and at least one critical claim is not `VERIFIED` or `E4_VERIFIED`. |
| `VERIFIED` | Every claim is `VERIFIED` or `E4_VERIFIED`. |
| `PARTIAL` | All other cases, including an empty claim list and a non-critical unverified claim. |

This is the implemented aggregate vocabulary. It is **not** the Dashboard persisted-status vocabulary below. In particular, `PARTIAL` is a real aggregate result and must not be silently renamed `SUSPICIOUS` or `INCONCLUSIVE`.

## 5. Persisted Dashboard status labels

The `GET /v1/verdicts` filter in `src/jamp/api/app.py` currently allowlists:

- `CLEAN`
- `SUSPICIOUS`
- `HALLUCINATION_CAUGHT`
- `INCONCLUSIVE`
- `INTEGRITY_VIOLATED`

**Observed limitation:** this route's allowlist proves only that these strings are accepted as persisted-status filters. The inspected code does not establish a complete, authoritative mapping from `aggregate_verdict()` results to these labels. Therefore the following are safe product definitions/target semantics, not a claim that the runtime currently derives them:

| Label | Intended user-facing meaning | Required trigger semantics | Current implementation status |
|---|---|---|---|
| `CLEAN` | All required critical claims in the checked packet are verified. | Every required critical claim has an accepted verified result; no integrity failure. | Mapping not established by the inspected aggregate/API code. |
| `SUSPICIOUS` | The packet contains unresolved claims, but no established critical contradiction. | At least one unresolved claim; no critical contradiction; no integrity failure. | Mapping not established. |
| `HALLUCINATION_CAUGHT` | At least one critical claim is contradicted by bounded source evidence. | At least one critical `CONTRADICTED` result with its source evidence; not merely missing data. | Mapping not established. |
| `INTEGRITY_VIOLATED` | Evidence integrity validation failed. | A reproducible digest/signature/chain-integrity check fails. | Filter label exists; end-to-end mapping to this persisted label is not established. |
| `INCONCLUSIVE` | No claim in scope could be independently resolved. | All in-scope claims are unresolved/out-of-scope, with no contradiction or integrity failure. | Mapping not established; aggregate `INCONCLUSIVE` has a narrower critical-claim rule. |

Until a separate implementation and test establishes this mapping, clients must not interpret a persisted label as proof that the corresponding trigger ran. Unknown or unsupported persisted values must render neutrally in the UI.

## 6. Tolerance policy — source-specific, not universal

The proposed universal `1%` tolerance is **not the current implementation**.

| Source | Claim type | Current default | Code location |
|---|---|---:|---|
| MOEX ISS | Price | 5% (`price_tolerance=0.05`, relative delta) | `src/jamp/provider/moex_verify.py::_verify_claim_with_moex` |
| CoinGecko | Price | 10% (`threshold_pct=10.0`) | `src/jamp/provider/coingecko_verify.py::_DEFAULT_THRESHOLDS` |
| CoinGecko | Market capitalization | 20% (`threshold_pct=20.0`) | Same |
| CoinGecko | Existence | No numeric tolerance | Same adapter |

MOEX compares `abs(claimed - observed) / observed` with `price_tolerance`. CoinGecko compares the relative delta in percent with `threshold_pct`. These parameters are source-specific and currently supplied through function defaults/arguments; this contract does not claim that `JAMP_FINANCIAL_TOLERANCE` is a supported environment setting.

A tolerance comparison does not solve quote freshness, currency conversion, market session, board selection, or source conflict. Those need explicit evidence and policy before being treated as verified.

## 7. Source hierarchy and conflicts

- MOEX ISS is used for supported MOEX security/ticker and share-price claims.
- CoinGecko is used for supported crypto existence, USD price, and USD market-cap claims.
- Neither adapter is a universal source for the other's domain.
- No global priority rule is present in the inspected code. If multiple sources disagree, preserve both observations and report `AMBIGUOUS`/HOLD until a domain-specific conflict policy exists. Do not choose a winner by convenience.
- A fallback provider or model response is not automatically a primary source.

## 8. Integrity and evidence fields

When raw HTTP capture is enabled, the adapters record source, URL, HTTP status, body completeness, base64-encoded raw body, and SHA-256 of the captured body. The hash must be recomputed from the decoded bytes when validating the evidence bundle.

A digest match means byte integrity relative to the recorded digest. It does not prove who operated the endpoint, whether the endpoint is authoritative, or whether the data is current. HMAC signatures in JAMP establish authenticity only relative to the shared secret; they are not public-key signatures.

A missing or incomplete raw body is an evidence-integrity/availability problem. It must not be represented as a successful verification. Whether it becomes a persisted `INTEGRITY_VIOLATED` label depends on the currently unimplemented persisted-status mapping above.

## 9. Machine-readable companion and conformance boundary

`config/status_definitions.json` contains the status vocabulary, definitions, source-specific defaults, implementation notes, and an embedded JSON Schema for the document structure. `tests/test_epistemic_contract.py` checks:
- the companion document against its embedded JSON Schema;
- claim and aggregate vocabularies against the actual runtime behavior;
- E4 constants against both provider adapters;
- persisted Dashboard filter values against the actual API allowlist;
- actual aggregation precedence and source-specific tolerance defaults.

These tests prove vocabulary/contract synchronization and the specific behaviors they exercise. They do not prove live provider truth, source freshness, or the missing persisted-status mapping.

## 10. Change control

Any change to status names, semantics, aggregation precedence, source defaults, or source coverage must update this document, the JSON companion, and the contract tests in the same change. A new status must not default to a positive/green interpretation. Unknown states fail closed and remain neutral.

Frozen Core invariant: `src/jamp/run.py` is outside this contract change and must remain at blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` (`Δ=0`).
