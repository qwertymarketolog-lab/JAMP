# JAMP Decision Log

Журнал решений и доказательств. Записи не переписываются задним числом.
Исправление или отмена фиксируется новой записью со ссылкой на исходную.

## Правила evidence

Статусы фактов:

-   `VERIFIED` --- подтверждено конкретным проверяемым evidence.
-   `OBSERVED` --- обнаружено при осмотре кода/документа/результата, но
    не подтверждено требуемым тестом или независимым воспроизведением.
-   `INFERRED` --- логический вывод из наблюдений, ещё требующий
    проверки.
-   `UNKNOWN` --- данных недостаточно.
-   `HOLD` --- решение/переход остановлен до получения указанного
    evidence.
-   `HISTORICAL` --- исторический контекст, не являющийся текущим
    состоянием.

`VERIFIED` всегда сопровождается направленным утверждением. Не
использовать голые `PASS`/`FAIL` для результатов безопасности:
указывать, что именно доказано.

## Baseline record --- 2026-11-01

-   Repository: `qwertymarketolog-lab/JAMP`
-   Main SHA: `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   Recursive Git tree SHA: `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   Tree response: `truncated=false`; 94 files under `docs/`.
-   `src/jamp/run.py` blob SHA:
    `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a` --- matches locked blob;
    Frozen Core Δ=0.
-   Exact paths `docs/DECISION_MAP.md`, `docs/DECISION_LOG.md`,
    `docs/NEXT_ACTION.md` absent from this baseline.
-   This record describes the inspected baseline only. Refresh before
    using it as current state after any main update.

### CI evidence observed on baseline SHA

The following GitHub Actions jobs were fetched and showed terminal
`completed / success` on the baseline SHA. Artifact absence is recorded
as absence, not treated as failure or success evidence beyond the job
conclusion.

  ------------------------------------------------------------------------------------------------------
  Workflow                 Run ID Job ID(s)                Conclusion    Artifact ID(s)
  ------------- ----------------- ------------------------ ------------- -------------------------------
  Developer           41334499579 124931320052 (`quality`) success       none returned
  Quality                                                                

  Run Pytest          41334499392 124931319511 (`test`)    success       13094707198
                                                                         (`p17-6-experiment-report`)

  G4 MinIO            41334499591 124931319942             success       13094442937
  Runtime                         (`g4-minio-runtime`)                   (`g4-minio-runtime-evidence`)

  EXP-19              41334499433 124931319494             success for   13095145266; 13095110345;
                                  (`exp19-performance`);   all fetched   13094706973; 13094327921;
                                  124931319591;            jobs          13094173166
                                  124931319691;                          
                                  124931319693;                          
                                  124931319702                           

  P23.0-B             41334499442 124931319357 (`p23-0-b`) success       none returned

  P20.5               41334499522 124931319632             success       none returned
                                  (`diagnostic`)                         

  P20.11              41334499464 124931319606             success       none returned
                                  (`diagnostic`)                         

  SBOM                41334499502 124931319697 (`sbom`)    success       13094253496 (`jamp-sbom`)
  ------------------------------------------------------------------------------------------------------

Scope limitation: this is the set of eight workflows explicitly fetched
for this audit, not a complete independent proof that every required
ruleset/check on the repository is represented. It is not CI evidence
for a future P0 test commit. In the 2026-11-01 18:56 review, the reviewer
could not independently query GitHub API and did not re-check these
Run/Job/Artifact values. They remain recorded from the earlier API
inspection, not newly reconfirmed by this revision.

Known anomaly: `import-historical.yml`, Run `41334498364`, returned
`failure` with `jobs=[]`. Under the project protocol this is the known
orphaned-workflow anomaly and is not used as a P0 result or as a reason
to modify that workflow.

------------------------------------------------------------------------

## JAMP-DEC-001 --- Tenant Isolation / Cross-Organization Access

-   Date: 2026-11-01
-   Status: `HOLD`
-   Evidence baseline: `3917c484e00cc0439695c16362b724d1ddbcc4a2`

### Question

Can organization A read organization B's records (and vice versa)
through:

-   `GET /v1/jamp-verdict/{trace_id}`
-   `GET /v1/provenance/{trace_id}`
-   `GET /v1/universal-verdict/{trace_id}`

### Verified source observations

At the stated baseline, source inspection established:

1.  `src/jamp/api/auth.py` defines `OrganizationContext` and
    `require_api_key()` validates the bearer API key and resolves an
    organization context.
2.  The three GET handlers in `src/jamp/api/app.py` are protected by
    `require_api_key`, but their persistence read calls use
    `trace_id` without passing `organization_id`.
3.  `src/jamp/runtime/persistence.py` implements `AuditPersistence` over
    JSONL and its relevant read methods look up by trace ID without an
    organization argument.

These are verified code-structure observations for the specified SHA.
They do **not** prove that an attacker can retrieve another
organization's record in a real application configuration.

### Unknown / inferred

-   Actual cross-organization disclosure using two valid organizations
    and their API keys: `UNKNOWN`.
-   Possible cross-organization exposure is an `INFERRED` risk from the
    structural omission; it is not yet a reproduced vulnerability.
-   Storage topology and record-creation path must be established from
    the actual app configuration. Do not assume separate per-org JSONL
    files or a shared file without inspecting the tested runtime
    configuration.
-   Additional local-clone review reported that `AuditPersistence`
    contains zero occurrences of `organization` / `org_id`, uses one
    configured `audit_storage_path` (`app.py:165`), and its write methods
    `write_trace(trace_payload)`, `write_verdict(trace_id, …)`, and
    `write_universal_verdict(trace_id, payload)` accept no organization
    argument. This is recorded as `OBSERVED` from the reviewer's local
    clone, not as independently re-fetched GitHub evidence in this
    document update. The reported observation means ownership is not
    represented as an organization attribute in this persistence model.
-   For the runtime access test, operational record provenance is the
    API key used to create the record through the real application
    route. This is a test association based on the authenticated create
    request; it must not be misrepresented as a persisted owner/org
    field. If no real authenticated create route exists for a record type, a direct
    persistence write does not establish create-key provenance by itself.
    Use it only if the exact production call path demonstrably carries the
    authenticated request context from the real auth path into that write;
    otherwise that record type is `INCONCLUSIVE / HOLD` for runtime
    ownership-boundary conclusions.

### Decision

Do not label this a confirmed vulnerability until the P0 integration
test reproduces disclosure. Do not declare isolation enforced until the
same test demonstrates both directions are denied while positive
controls succeed.

No code change is authorized by this record.

### P0 integration-test specification

#### Required real stack

The P0 runtime test contains **18 controls total**: six positive, six
cross-key negative, and six missing-record controls (two keys × three
read routes). The architecture observation `OWNERSHIP_NOT_MODELED` is
reported separately and is not counted as a runtime control.

-   Instantiate the real `create_app()`.
-   Use the real `AuditPersistence` implementation and actual JSONL
    read/write path used by the application.
-   Use two real organization records and two valid API keys accepted by
    the actual `require_api_key()` path.
-   Create Verdict, Provenance/trace, and UniversalVerdict records for
    both organizations through the real application write route where
    available. The operational provenance for each test record is the
    key authenticated on that real create request. If no real create
    route exists for a record type, use the exact production write path
    and document whether authenticated organization context reaches it.
-   This operational provenance does not create or imply a persisted
    `org_id` field. The absence of such a field/write parameter is a
    separate architecture finding: `OBSERVED: OWNERSHIP_NOT_MODELED`.
-   Preserve and inspect the actual storage topology (shared JSONL
    store, per-org stores, or other configured arrangement). Do not
    manufacture separate stores solely to make isolation appear to work.
-   No mocked persistence, mocked auth dependency, or test-only
    organization filter.
-   Do not classify the test as `INCONCLUSIVE` solely because the
    persistence schema has no owner/org attribute. If the real create
    request under key A can be identified and its trace ID is then
    requested under key B, the response directly tests whether the
    application enforces the expected key boundary. Use `INCONCLUSIVE /
    HOLD` only when the real auth/create/read path or record provenance
    cannot be established.

#### Positive controls

Each organization's own key must retrieve its own record:

  Key   Record               Expected
  ----- -------------------- -------------------------------------------
  A     Verdict A            successful response containing A's record
  B     Verdict B            successful response containing B's record
  A     Provenance A         successful response containing A's record
  B     Provenance B         successful response containing B's record
  A     UniversalVerdict A   successful response containing A's record
  B     UniversalVerdict B   successful response containing B's record

#### Negative controls --- cross-organization

  Key   Record               Expected
  ----- -------------------- --------------------------------
  A     Verdict B            refusal; no B data in response
  B     Verdict A            refusal; no A data in response
  A     Provenance B         refusal; no B data in response
  B     Provenance A         refusal; no A data in response
  A     UniversalVerdict B   refusal; no B data in response
  B     UniversalVerdict A   refusal; no A data in response

The exact refusal status/code must be compared with the route's
documented API contract. Do not silently assume 403 versus 404.
Regardless of status, the response body must not expose the foreign
record's trace ID, organization identifier, payload, evidence, or other
record-specific fields.

#### Missing-record negative control

-   For each of the three routes, key A and key B each request a
    non-existent trace ID (six controls total).
-   Check each of the three routes independently. The local reviewer
    reports that `/v1/jamp-verdict/{trace_id}` returns 404 when its read
    result is `None`. The corresponding missing-record behavior for
    `/v1/provenance/{trace_id}` and
    `/v1/universal-verdict/{trace_id}` remains `UNKNOWN` until their
    handlers or actual responses are checked. Do not generalize the
    first route's 404 behavior to the other two.

#### Result classification

-   `OBSERVED: OWNERSHIP_NOT_MODELED` --- source/model inspection shows
    no organization/owner attribute for records and/or write methods do
    not accept organization context. This is an architecture finding,
    not a runtime security-test result and not a `VERIFIED` verdict.
-   `VERIFIED: ISOLATION_ENFORCED` --- all six positive controls
    succeed; all six cross-key requests are refused without foreign
    data; all six missing-record controls (two keys × three routes)
    match each route's actual contract;
    records were created through real authenticated create routes, or
    equivalent production call paths demonstrably propagated that
    authenticated request context into the write.
-   `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED` --- at least one
    cross-key request returns protected data for a record created
    through the real route under the other key. Preserve exact request,
    response, trace IDs, authenticated create provenance, storage
    evidence, and terminal test log. The absence of a persisted org
    attribute does not invalidate this reproduction when the real
    create-key provenance is established.
-   `INCONCLUSIVE / HOLD` --- real authentication, create/write/read
    path, record provenance, storage topology, or runtime environment
    cannot be established well enough to interpret the controls. Lack
    of a persisted org field alone is not sufficient for this outcome
    if real create-key provenance and cross-key reads are testable.

A test harness error is not evidence that isolation works or that
disclosure exists.

#### CI evidence required for closure

For the P0 test commit, preserve:

-   exact commit SHA;
-   workflow name and workflow run ID;
-   job ID and terminal conclusion;
-   artifact ID/name containing raw test output and relevant sanitized
    runtime/storage evidence, if emitted;
-   explicit test counts and each of the 6 positive, 6 cross-org
    negative, and 6 missing-record controls (two keys × three routes);
-   Frozen Core blob check on the tested SHA.

PR CI is not post-merge CI. If merged, post-merge `main` CI must be
checked separately.

### Consequence / next action

Remain `HOLD`; perform read-only inspection of the actual application
write path and storage configuration before implementing the P0 test. No
remediation patch is authorized.

------------------------------------------------------------------------

## JAMP-DEC-001 --- Tenant Isolation — Review Update 1

-   Date: 2026-11-01 18:56 UTC
-   Previous record: JAMP-DEC-001, baseline `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   Status: `HOLD` (unchanged)
-   Evidence source: reviewer-provided local-clone observations; not independently re-fetched from GitHub during this document revision.

### Additional observations supplied in review

-   `src/jamp/runtime/persistence.py`: reviewer reports zero occurrences of `organization` / `org_id` in `AuditPersistence`.
-   Reported write signatures: `write_trace(trace_payload)`, `write_verdict(trace_id, …)`, `write_universal_verdict(trace_id, payload)`; none accepts organization context.
-   `src/jamp/api/app.py:165`: reviewer reports one configured `audit_storage_path`.
-   Three GET paths reconfirmed by reviewer: `/v1/jamp-verdict/{id}`, `/v1/provenance/{id}`, `/v1/universal-verdict/{id}` (reported approximate handler locations ~1058, ~1129, ~1174).
-   Missing-trace behavior: reviewer reports `/v1/jamp-verdict/{id}` returns 404 when read returns `None`; other two route contracts remain unchecked.

### Decision clarification

`OBSERVED: OWNERSHIP_NOT_MODELED` is recorded as a distinct architecture finding: the reported persistence model and write API do not represent organization ownership. It does not, by itself, prove runtime disclosure.

For the P0 runtime controls, define a test record's operational provenance as the API key authenticated on the real application create request. This is not a persisted ownership attribute. A record created through a real route under key A and then returned to key B is `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED`, provided both keys are genuinely authenticated as different organizations and the exact create/read path is preserved. If that provenance or real path cannot be established, classify the test `INCONCLUSIVE / HOLD`.

The four distinct classifications are therefore:

1. `OBSERVED: OWNERSHIP_NOT_MODELED` — architecture observation only.
2. `VERIFIED: ISOLATION_ENFORCED` — all positive and cross-key negative controls pass under the real stack.
3. `VERIFIED: CROSS_ORG_DISCLOSURE_REPRODUCED` — at least one cross-key read returns the other key's real-route-created record.
4. `INCONCLUSIVE / HOLD` — test setup or provenance prevents a valid conclusion.

This clarification does not change the current `HOLD`, authorize remediation, or promote the local observations to CI-verified facts.

------------------------------------------------------------------------

## JAMP-DEC-002 --- MOEX Pagination

-   Date: 2026-11-01
-   Status: `OBSERVED`
-   Local-clone review references supplied 2026-11-01 (not independently
    re-fetched from GitHub in this revision):
    - `src/jamp/provider/moex_history.py`, `history.cursor` loop near
      line 294.
    - `tests/test_moex_history.py`: `test_pagination_fetches_all_pages`
      (reported near line 143),
      `test_stalled_returns_inconclusive` (near line 165), and
      `test_incomplete_history_fetch` (near line 178).
-   Tests were not run as part of this review. Status remains `OBSERVED`.
-   Required to promote: verify exact SHA/source in GitHub and run the
    relevant tests with terminal output/CI evidence.
-   Until that evidence is recorded, do not claim current-main
    pagination correctness or real long-range network correctness.

## JAMP-DEC-003 --- `verify-chain` fail-closed without secret

-   Date: 2026-11-01
-   Status: `OBSERVED`
-   Local-clone review references supplied 2026-11-01 (not independently
    re-fetched from GitHub in this revision):
    - `src/jamp/runtime/independent_verifier.py:218`, `verify_chain`.
    - `tests/test_independent_verifier.py:253`,
      `test_missing_secret_returns_refuse`; reviewer reports assertions
      for `verdict == REFUSE` and `reproducible is False`.
-   Test was not run as part of this review. Status remains `OBSERVED`.
-   Required to promote: verify exact SHA/source in GitHub and run the
    relevant test with terminal output/CI evidence.
-   Do not infer that all verification paths or all secret
    configurations have been tested.

## JAMP-DEC-004 --- `/v1/execute` versus `/execute`

-   Date: 2026-11-01
-   Status: `OBSERVED`
-   Local-clone review references supplied 2026-11-01 (not independently
    re-fetched from GitHub in this revision):
    - `src/jamp/api/router.py:21–56`: `_not_implemented` / router
      stubs returning HTTP 501.
    - `src/jamp/api/app.py`: separate `/v1/execute` endpoint.
    - No tests specifically covering the 501 routes were found by the
      reviewer; `test_sse_gateway_v1.py` reportedly imports
      `_sse_not_implemented`, which is not equivalent to route coverage.
-   Status remains `OBSERVED`; tests/route registration were not run or
    independently verified in this review.
-   Required to promote: verify exact SHA/source and route registration;
    add or run route-level tests only under separate authorization.
-   Do not conflate the runtime API endpoint with the router stub.

## JAMP-DEC-005 --- Frozen Core

-   Date: 2026-11-01
-   Status: `VERIFIED`
-   Baseline SHA: `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   File: `src/jamp/run.py`
-   Observed blob SHA: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
-   Locked blob SHA: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
-   Result: exact match; Frozen Core Δ=0.
-   Consequence: any future modification requires explicit Core Unlock
    and a separate evidence-backed decision. This record is not
    authorization to modify the file.

## JAMP-DEC-006 --- PR #324 / P31

-   Date: 2026-11-01
-   Status: `HISTORICAL`
-   Use: historical reference only.
-   Consequence: do not use its branch state or attached evidence as
    proof of current `main`, current CI, or current runtime behavior.

## JAMP-DEC-007 --- CI Evidence on baseline SHA

-   Date: 2026-11-01
-   Status: `OBSERVED` (limited, enumerated scope)
-   Baseline: `3917c484e00cc0439695c16362b724d1ddbcc4a2`
-   Evidence: eight named workflows and their terminal jobs are
    enumerated in the Baseline record above.
-   Limitation: the fetched sample is not a complete ruleset inventory
    and does not prove every required check is represented. It does not
    replace CI for the future P0 test commit.
-   Consequence: update this decision only after the required
    checks/rulesets and exact terminal evidence are enumerated for the
    relevant SHA.

## Append-only updates

Add subsequent records below. Never edit the historical findings above.

### Update template

``` markdown
## JAMP-DEC-NNN — <decision title> — Update <n>

- Date:
- Previous record:
- New status:
- Exact SHA:
- Evidence:
  - file / test / workflow:
  - run ID:
  - job ID:
  - conclusion:
  - artifact:
- Finding:
- Decision:
- Consequence:
```

## JAMP-DEC-001 — P0 control count — Update 2

- Date: 2026-11-01 19:01 UTC
- Previous record: JAMP-DEC-001 — Update 1
- New status: `OPEN` — control-count decision approved; document set not yet approved for publication
- Exact SHA: `3917c484e00cc0439695c16362b724d1ddbcc4a2` (document baseline only; no new repository verification)
- Evidence: explicit user decision in the review conversation: `18`.
- Finding: the P0 runtime test scope is fixed at 18 controls: six positive (A→A and B→B across three record types), six cross-key negative (A→B and B→A across three read routes), and six missing-record controls (two keys × three routes). `OBSERVED: OWNERSHIP_NOT_MODELED` is a separate architecture observation and is not counted as a runtime control.
- Provenance constraint: a record's operational provenance is the key authenticated on its real create request. A direct persistence write is acceptable for runtime ownership-boundary conclusions only if the exact production call path demonstrably propagates authenticated request context into the write; otherwise the affected record type is `INCONCLUSIVE / HOLD`.
- Decision: retain 18 controls. Do not reduce the test to 14.
- Consequence: update the P0 Definition of Done consistently in all three draft documents. This approval is limited to the control count and does not authorize GitHub publication, code changes, test execution, remediation, or merge.

## JAMP-DEC-001 --- Documentation publication authorization --- Update 3

- Date: 2026-11-01 19:02 UTC
- Previous record: JAMP-DEC-001 --- P0 control count --- Update 2.
- Status: `PUBLICATION_AUTHORIZED` (documentation-only scope).
- Exact SHA: `3917c484e00cc0439695c16362b724d1ddbcc4a2` (refreshed `main`
  immediately before publication).
- Evidence: explicit user authorization to publish the three decision
  documents in the repository.
- Finding: the approved local document set records 18 P0 runtime controls,
  keeps `OBSERVED: OWNERSHIP_NOT_MODELED` separate from runtime outcomes,
  and preserves the provenance constraint.
- Decision: publish only `docs/DECISION_MAP.md`, `docs/DECISION_LOG.md`,
  and `docs/NEXT_ACTION.md` on a dedicated branch and submit a PR.
- Consequence: no runtime, tests, workflows, thresholds, policies, or
  Frozen Core changes; PR merge remains separately unauthorized.
