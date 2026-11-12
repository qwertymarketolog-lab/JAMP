# Stage 10 — External Workflow Integration Contract v0.1

## Scope
A small, independent n8n/ASCN-style workflow emulator receives untrusted financial text, calls the JAMP HTTP API, verifies the returned verdict, and only then writes parsed data to a local JSON file representing a CRM sink. This is an integration harness, not a claim of full n8n compatibility.

## Responsibilities
- **Emulator:** trigger/input handling, HTTP transport, fail-closed routing, safe JSON parsing, simulated CRM write, and explicit ABORT/SECURITY_ALERT diagnostics.
- **JAMP API:** model execution, E2 generation verification, E3 qualification decision, and HMAC-signed JampVerdict.
- **CRM sink:** test-only JSON file; no real CRM integration or production side effect.

## Admission gates (all required)
1. /v1/execute response has status == EXECUTE.
2. evidence_status == VERIFIED.
3. qualification == QUALIFIED.
4. verdict is an object with status == VERIFIED and trace_id matching the execution response.
5. POST /v1/verify-verdict with the verdict object directly returns valid == true.
6. output.content parses as a JSON object. Only this parsed object can be written to the CRM fixture.

Any missing field, unexpected HTTP status, malformed JSON, exception, or failed gate aborts the flow and prevents the CRM write. Qualification is checked separately from E2 evidence: VERIFIED evidence alone does not grant E3 qualification.

## Signature negative control
After a successful positive path, the harness changes one character in a copy of the signature and sends that tampered verdict to /v1/verify-verdict. The expected result is valid == false, and the harness emits a SECURITY_ALERT for that deliberately isolated negative-control branch. This expected detection does not invalidate the positive run. If the authentic verdict is rejected, the workflow aborts and exits non-zero.

## Evidence limits
A passing run proves the tested HTTP path and the observed API contract for that run/configuration. It does not qualify all models, establish general provider reliability, or connect to a real CRM. src/jamp/run.py is Frozen Core and must remain byte-identical.
