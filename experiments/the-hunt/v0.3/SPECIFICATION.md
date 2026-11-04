# The Hunt Benchmark v0.3 — Provenance, Signatures & LLM Provider

## 1. Objective
To measure JAMP's ability to detect **sophisticated hallucinations**:
- Slopsquatting (fake packages that *do* exist in PyPI but have malicious/untrustworthy provenance).
- Fake APIs (calling non-existent methods on real libraries).
- Real LLM hallucinations from genuine model generations, not synthetic inputs.

## 2. Dataset Requirements (Real LLM)

### 2.1 Provider configuration
- The generation runner must use a provider-neutral configuration boundary. Provider selection, endpoint, model, temperature, and token limit are explicit run inputs; they must not be inferred or silently substituted.
- **Initial experiment provider:** Groq API, using the existing OpenAI-compatible chat-completions endpoint/configuration where suitable. The exact provider and model must be pinned for each run.
- Other providers (including AnyModel or OpenRouter) may be used only in a separate run after their endpoint, model identifier, authentication method, and response schema have been explicitly validated. Do not assume that the name "AnyModel" identifies a directly callable provider.
- **One run = one provider + one model + one fixed generation configuration.** Never mix providers or models within one cohort or silently fail over to another provider/model. A change requires a distinct run and manifest.
- Default experiment temperature: **0.7**. Any override must be explicitly recorded in the run configuration and manifest. This is an experiment-level request parameter intended to permit non-deterministic generations for hallucination measurement; it is not a model qualification setting.
- The existing production/runtime `src/jamp/provider/groq.py` temperature default is not to be changed for this experiment. The v0.3 runner must pass the experiment temperature explicitly at the request boundary (or use an isolated experiment-only client/wrapper that does so). Do not mutate the shared runtime adapter or its default merely to set the benchmark temperature. If the current adapter cannot accept an explicit per-request temperature, document that limitation and implement the isolated experiment request path rather than silently sending temperature 0.
- Record the provider base URL/endpoint without credentials, provider name, requested model ID, provider-returned model ID, temperature, max completion tokens, and any other generation-affecting parameters.
- API keys and other secrets must be read from environment/repository secrets and must never be written to manifests, logs, prompt artifacts, or uploaded evidence.
- No silent retries that change model, provider, temperature, or other generation parameters. Retries of the same request may occur only under a documented bounded retry policy and must be recorded.

### 2.2 Generation tasks and manifest
- **Tasks:** 100 prompts designed to induce hallucinations (e.g., asking for obscure integrations). The exact prompt dataset is versioned and its SHA-256 digest is recorded.
- A run manifest must include at minimum:
  - `experiment_id`
  - `evaluation_mode`
  - `provider_name`
  - `provider_base_url` (no credentials or secret query parameters)
  - `requested_model_id`
  - `provider_model_id` (as returned by the provider; absent values remain explicitly unavailable)
  - `temperature`
  - `max_completion_tokens`
  - `prompt_dataset_sha256`
  - `generation_timestamp_utc`
  - `successful_requests` and `failed_requests`
  - per-request prompt ID, request status, provider response/request ID when available, and request timestamp
- Failed, missing, malformed, or truncated generations are not successful samples. Preserve their failure status and reason; exclude them from paired scoring or mark them INCONCLUSIVE according to the evaluator contract. Never replace them with synthetic outputs.
- Provider/model availability and account-specific rate limits must be checked before the live run. A successful adapter unit test is not evidence of live API access or sufficient quota.

### 2.3 Ground truth
- For packages: Human-verified or Web-search verified against PyPI, with the source and observation time retained.
- For APIs: Static analysis of the exact downloaded wheel version using Python's `ast` module. No package installation or import is permitted.

## 3. JAMP v0.3 Engine Components

### A. Provenance Analysis
JAMP queries PyPI JSON metadata and calculates a deterministic Trust Score, starting at 100 points.

**First-publication age**
- Derive the first publication timestamp from the earliest available release-file `upload_time` in the PyPI `releases` data.
- Calculate elapsed age against the UTC observation timestamp.
- Age penalty: less than 30 days: **−50**; at least 30 days but less than 365 days: **−20**; at least 365 days: **0**.
- If no usable release timestamp exists, provenance is **INCONCLUSIVE**; do not infer a safe age.

**Repository**
- A GitHub or GitLab repository URL in PyPI `project_urls`: **0** penalty.
- No such repository URL: **−30**.

**Author**
- A non-empty `author` or `author_email` field: **0** penalty.
- Both fields empty or missing: **−20**.

**Score and decision**
- `trust_score = max(0, 100 - age_penalty - repository_penalty - author_penalty)`, where penalties are positive magnitudes as listed above.
- A score **below 50** produces `PROVENANCE_SUSPICIOUS` and blocks the package.
- A score of exactly 50 or higher does not trigger this threshold by itself; other JAMP gates still apply.
- Preserve the raw PyPI response, UTC observation timestamp, derived first-publication timestamp, individual penalties, and final score in the evidence artifact.

### B. Signature Verification
- Extract candidate module, class, and function calls from the generated code's AST.
- Download the exact package wheel (`.whl`) from the PyPI release metadata; do not install the package and do not execute package code.
- Inspect the wheel as an archive and read relevant `.py` source files directly. Reject archive paths that escape the extraction/read boundary; do not extract files to an executable environment.
- Parse source text with `ast.parse` and statically inspect module, class, and function definitions to determine whether the referenced API symbol is declared.
- If the referenced symbol is absent from the statically inspectable source, block it as `INVALID_SIGNATURE`. If the wheel, module mapping, or source cannot be resolved conclusively (including extension-only or dynamically generated APIs), return `INCONCLUSIVE`, not a false `INVALID_SIGNATURE` or PASS.
- No `import`, `importlib`, package installation, or `inspect` call against the downloaded package is permitted.

**Security and interpretation limits:** AST parsing does not execute the parsed source, but static presence is not proof that a call will work at runtime. It may not resolve dynamic attributes, generated APIs, compiled extensions, or environment-dependent behavior. These cases must remain `INCONCLUSIVE` unless separately verified by an independently designed safe method.

## 4. Implementation Details (Security & Determinism)
1. **Download statistics are excluded from v0.3 scoring.** The standard PyPI JSON API does not provide download counts. The age signal is derived only from the earliest available release-file `upload_time` in `releases`; no substitute or inferred download metric may be used.
2. **Trust Score is deterministic.** Apply the age, repository, and author penalties defined in Section 3A to a starting score of 100, clamp the result at zero, and block only when the resulting score is below 50. Missing first-publication evidence is `INCONCLUSIVE`, not a zero-age or low-risk assumption.
3. **Signature checks are static-only.** Read `.py` source from the exact PyPI wheel without installation or import, parse it with `ast.parse`, and inspect declarations. Never execute untrusted package code in the GitHub Actions runner. Missing or non-statically-resolvable symbols are handled as specified in Section 3B.
4. **Generation provenance is immutable per run.** The provider, model, endpoint, temperature, token limit, prompt dataset digest, and other generation-affecting parameters are fixed in the run manifest. A different configuration creates a different run. Secrets are never persisted.
5. **Experiment temperature is isolated from runtime defaults.** v0.3 uses an explicit request-level temperature of 0.7. The production Groq adapter default in `src/jamp/provider/groq.py` remains untouched; if it cannot accept a per-request override, the experiment runner uses a separate isolated request client/wrapper.

## 5. Baseline vs JAMP
- **Baseline:** AST syntax check + simple PyPI existence check (v0.2 logic).
- **JAMP:** AST + PyPI existence + Provenance Trust Score + static Signature Verification.

## 6. Definition of Done
- [ ] Real LLM outputs generated and saved with a complete, validated run manifest.
- [ ] Exactly one provider and one model used within each run; provider/model identity is confirmed from response evidence where available.
- [ ] Experiment temperature 0.7 is explicitly sent at request level without changing `src/jamp/provider/groq.py` runtime defaults.
- [ ] Provider secrets are absent from all artifacts and logs.
- [ ] Provenance checks implemented (first-publication age, repository, author).
- [ ] Deterministic Trust Score and `PROVENANCE_SUSPICIOUS` threshold implemented.
- [ ] Static signature checks implemented using wheel source and `ast.parse`, without installation or execution.
- [ ] Paired evaluation (Baseline vs JAMP) with McNemar test.
- [ ] Evidence artifact with raw PyPI metadata, scoring inputs, generation manifest, and signature validation logs.

## 7. Temporal Contract — Generation Environment and API Snapshots

The evaluator must keep two independent API observations:

- `API VALID NOW`: static API inspection against the latest wheel resolved at evaluation time.
- `API VALID THEN`: static API inspection against the exact wheel whose SHA-256 was recorded from PyPI release metadata observed before the corresponding model request.

For every request, the runner captures the Python interpreter/platform and installed-distribution inventory before generation. It then observes the target distribution's PyPI release metadata immediately before the model request, pins the selected version, wheel filename, and published SHA-256, and downloads the wheel immediately after the response. The downloaded bytes are accepted only if their SHA-256 matches the pre-request metadata. The wheel is retained in the evidence bundle and referenced by a canonical snapshot manifest hash.

Temporal provenance is explicit:

- `GENERATION_ENVIRONMENT`: the package version is independently established as installed in the captured generation environment. This status must not be inferred from a PyPI lookup.
- `PRE_GENERATION_REGISTRY_SNAPSHOT`: the exact PyPI wheel release and digest were observed before the request; this supports a historical registry/API declaration check, but does not claim the package was installed in the generation environment.
- `POST_GENERATION_RESOLUTION`: package/version resolution occurred only after the response; this is not accepted as proof of API VALID THEN.
- `UNRESOLVED`: metadata, wheel, timestamp, or digest evidence is missing or invalid.

The current runner captures the requested target distribution `package_name` for each sample. Additional imported modules that cannot be mapped to a distribution using authoritative evidence are outside this snapshot's qualified scope and must remain INCONCLUSIVE; do not guess a PyPI distribution name from an import name.

The evaluator verifies the snapshot digest and each wheel digest before static inspection. It never silently falls back from a missing or invalid temporal wheel to the latest PyPI wheel for the THEN result. The live latest-wheel check is retained only as the separate NOW axis. A post-generation-only record, missing wheel, hash mismatch, or missing snapshot yields `INCONCLUSIVE` / `TEMPORAL_EVIDENCE_MISSING` for THEN.

The snapshot's timestamp is the registry-observation boundary immediately before each model request. The wheel download occurs after the response, but the pre-request SHA-256 pins the exact immutable artifact; if the artifact cannot be retrieved byte-for-byte, the temporal result is unresolved. Static API presence is not runtime behavior or function-signature compatibility.
