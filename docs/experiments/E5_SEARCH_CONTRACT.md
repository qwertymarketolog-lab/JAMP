# E5 Search Contract — v0

## Purpose and boundary

E5 searches for public sources that support or contradict a claim. It does not
establish ground truth, provide investment advice, or replace E4. A search result
that does not resolve the claim is not evidence of truth or falsity.

## Public API

`jamp.provider.e5_search.verify_with_search(claim_text, claim_type, ticker=None,
date_from=None, date_till=None, timeout=10.0, api_key=None)` returns
`(status, evidence)`, where status is one of `E5_VERIFIED`,
`E5_CONTRADICTED`, `E5_OUT_OF_SCOPE`, or `E5_INCONCLUSIVE`.

The whitelist version is `e5-authoritative-domains-v0`. Its immutable v0 domain
list is `data/e5_authoritative_domains_v0.json`; any domain-list change requires
a new version.

## Claim-type rules

- `causal`: a whitelisted snippet must contain a causal marker, the ticker, and
  at least one claim keyword. This is a regex heuristic, not causal inference.
- `change_percent`: a whitelisted snippet must contain the ticker and the same
  explicit percentage as the claim. The v0 implementation does not infer an
  unstated period.
- `existence`: a whitelisted snippet must mention the ticker. This is bounded
  ticker-level evidence, not a universal proof of corporate existence.
- `prediction`: always `E5_OUT_OF_SCOPE` (`future_prediction_not_searchable`).
  A prediction about what an analyst said is not supported in v0.
- `historical_price`: always `E5_OUT_OF_SCOPE`
  (`foreign_price_not_supported_v0`); MOEX data must retain priority upstream.
- Unsupported claim types are out of scope.

## Verdict semantics

- One whitelisted domain supports a claim and none contradict: `E5_VERIFIED`,
  basis `single_source`.
- Two or more distinct whitelisted domains support it and none contradict:
  `E5_VERIFIED`, basis `multi_source_confirmed`.
- At least one source contradicts and none supports: `E5_CONTRADICTED`.
- Support and contradiction coexist: `E5_INCONCLUSIVE`,
  `conflicting_sources`; the conflict is preserved.
- No whitelisted result or a snippet that does not resolve the claim:
  `E5_OUT_OF_SCOPE`.
- Missing key, auth failure, rate limit, server/network error, timeout, or malformed
  response: `E5_INCONCLUSIVE`.

## Tavily request

POST `https://api.tavily.com/search` with advanced search, up to 10 results,
the flattened whitelist in `include_domains`, and both `include_raw_content`
and `include_answer` set to false. The key comes from the explicit parameter
or `TAVILY_API_KEY`. No retry is performed for HTTP 429.

## Evidence and privacy

Evidence records the exact query, claim, provider, whitelist version, HTTP status,
result counts, whitelisted URLs, title, snippet (maximum 500 characters), domain,
source group, publication date when present, verdict basis, conflict flag, reason,
and independence basis. Full page text, API keys, authorization headers, and IP
addresses are not persisted.

## Known limitations

1. Cross-domain reprints (for example, Reuters → RBC) are not detected and may
   appear independent.
2. Subdomains of the same registered domain count as one source.
3. Future predictions and analyst-meta-predictions are out of scope.
4. Exact percentage evidence may be absent from financial snippets.
5. Foreign historical prices are not supported in v0.
6. Causal markers are regex-based and can yield false positives; they do not prove
   causality.
7. Domain allowlisting is a trust filter, not proof that every article is accurate.
8. Search coverage is incomplete: no result does not mean a claim is false.

## Non-goals

No pipeline integration, multi-provider fallback, cache, 429 retry, baseline v0.2,
Marketplace, or modifications to the Frozen Core are part of PR A.
