# JAMP Audit v1

## Purpose and evidence boundary

Audit v1 runs the same frozen composite prompt against the three currently enabled
AnyModel candidates and preserves each response, metadata, hashes, and a terminal
manifest. It is an evidence-collection experiment, not a qualification harness and
not a claim that the candidates are equivalent to unavailable model IDs.

The candidate substitutions are availability-driven only:
- `ag/claude-sonnet-4-6` is present in the probed catalog.
- `ag/gemini-3.7-flash-high` was unavailable; `ag/gemini-3.8-flash-high` is a
  nearest available candidate, not an equivalence-proven replacement.
- `am/kimi-k3` was unavailable; `kmc/kimi-for-coding` is a semantically similar
  candidate, not an equivalence-proven replacement.

Catalog probe evidence: Run `43493715340`, Job `132121195588`, Artifact
`14071860361`; catalog SHA-256
`abf48b001f81141111d87cce353b31516320811b7a7db1b8c06b07b502fcae46`.
The unauthenticated `/openapi.json` probe returned 404; unauthenticated
`/v1/models` returned 401 and authenticated `/v1/models` returned 200 with
109 catalog entries. These observations do not establish the chat/completions
response contract. `finish_reason`, `usage`, pricing semantics, and rate limits
remain unverified. No paid request has been made.

## Safety limits

- Registry capacity is `MAX_MODELS=100`; first-run execution is hard-limited to
  `MAX_MODELS_FIRST_RUN=3` in code. There is no user override.
- AnyModel is the only implemented provider. Other provider values fail closed.
- Preflight is GET-only. Execution consumes the exact saved catalog snapshot and
  expected SHA-256; it does not refetch the catalog.
- Execution requires `ANYMODEL_API_KEY` and the explicit `execute` command.
- Workflow dispatch defaults `execute=false`. No model request is sent by tests,
  snapshot verification, or catalog preflight.
- The first-run limit is lifted only after COST_BASELINE contains no more than
  three complete, cross-linked manifest → usage → metadata evidence blocks.
- `COMPLETED` is the only comparable response status. Other statuses are not
  silently normalized into success.

## Commands

Generate snapshots only when intentionally changing the audit spec or input pack:

```bash
python scripts/research/jamp_audit_v1.py --emit-snapshots tests/research/snapshots/
```

Verify committed snapshots:

```bash
python scripts/research/jamp_audit_v1.py --verify-snapshots tests/research/snapshots/
```

GET-only catalog preflight (requires API key and canonical UUIDv4):

```bash
python scripts/research/jamp_audit_v1.py preflight --models all --experiment-id <uuid>
```

Paid execution is deliberately separate and must not be run without a distinct
operator authorization:

```bash
python scripts/research/jamp_audit_v1.py execute --models all --experiment-id <uuid> \
  --catalog-snapshot artifacts/research/jamp_audit_v1/catalog_snapshot.json \
  --expected-catalog-sha <sha256> --inter-request-seconds 0
```

Verify a terminal batch:

```bash
python scripts/research/jamp_audit_v1.py verify \
  --manifest artifacts/research/jamp_audit_v1/manifest.json
```

The same composite prompt is sent to every selected model. The input pack is read
as exact bytes and decoded as UTF-8; hashes are computed over exact UTF-8 bytes.
Repository identity is the 40-character Git commit SHA, not a SHA-256 digest.

## Output contract

A terminal manifest records enabled, available, skipped, executed, completed,
failed, and still-running models. Skips and failures retain explicit reason
records. Every executed model has metadata; every completed model additionally
has a non-empty Markdown response whose exact bytes match `response_sha256`.
Provider-reported token usage is preserved in both the terminal manifest and
per-model metadata; the COST_BASELINE expansion gate checks that cross-reference.
The verifier rejects missing/extra files, duplicates, inconsistent statuses,
malformed hashes, identity drift, and non-terminal batches.

No qualification status is emitted. A response being COMPLETE means only that
the provider returned a non-empty response with a recognized `stop` finish
reason; it does not mean the answer is correct or useful.
