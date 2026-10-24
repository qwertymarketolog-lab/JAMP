# Financial Data Extraction Audit (Stage 3)

This experiment sends a deliberately messy quarterly-report excerpt to the running JAMP API, parses the model's JSON response, and compares the extracted values with a fixed reference file.

## Files

- `sample_report.txt` — source text containing mixed numeric formats and a prior-year comparison.
- `expected_data.json` — reference values used for exact comparison.
- `run_experiment.py` — client for `POST /v1/execute` and console report.

## Run

1. Start the JAMP API in an environment with the project's runtime dependencies and a configured provider. The API must be reachable at `http://127.0.0.1:8000` by default.
2. If the API listens elsewhere, set `JAMP_API_URL` to its base URL (without `/v1/execute`). Optionally set `JAMP_API_TIMEOUT` in seconds; default is `90`.
3. From the repository root, run:

   ```bash
   python experiments/financial_audit/run_experiment.py
   ```

The script reads the local report and reference JSON, calls `/v1/execute` with intent `search_and_extraction`, and prints `[DATA MATCH]`, `[MODEL VERIFIED]`, and `trace_id`. A non-zero exit code indicates a request/refusal, invalid response, data mismatch, or identity status that is not `VERIFIED`.

## Reading the result

- `[DATA MATCH] YES` means the extracted quarter and all four numeric values match the reference values. It does **not** prove that the values are true outside this synthetic fixture; the reference file is the experiment's ground truth.
- `[MODEL VERIFIED] YES` is printed only when the API response exposes `evidence_status: VERIFIED`. `CONTRADICTED` is a negative result; missing or inconclusive evidence is `UNKNOWN`, never a pass.
- `trace_id` links the result to JAMP's audit trace.

## Important API contract limitation

On the current `main` API implementation, successful `/v1/execute` responses include `status`, `selected_model`, `trace_id`, and `output`; they do not expose `evidence_status` at the top level or inside `output`. E2 verification is persisted in the audit trace, but this client deliberately does not infer that status from `selected_model`, provider success, or a trace ID. Therefore, with the current response contract, `[MODEL VERIFIED]` will report `UNKNOWN` until the API exposes the evidence status or a supported read path for the trace is used. Do not interpret that `UNKNOWN` as a failed E2 verification; it means this response does not provide the evidence needed by this script.

## Business value and limits

The experiment separates two questions that must not be conflated:

1. **Extraction accuracy:** did the returned values match the known reference data?
2. **Model identity:** did independent E2 evidence verify the model identity for this generation?

A normal wrapper can return plausible-looking numbers without an auditable identity signal. JAMP's E2 gate is designed to refuse OpenRouter executions when identity evidence is missing, contradictory, or inconclusive. That is useful for financial workflows where the requested model and provenance matter.

E2 does **not** guarantee that a model is intelligent, that its extraction is correct, or that a provider cannot behave dishonestly beyond what the independent generation endpoint reports. It verifies the model identity represented by that endpoint against JAMP's requested model identity. The experiment must measure extraction errors separately and must not claim that JAMP has caught hallucinations unless a comparison run demonstrates that result.
