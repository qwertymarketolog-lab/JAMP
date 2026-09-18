# Contributing to JAMP

JAMP is a research-facing architecture for machine discovery. Contributions are accepted only when the implementation, its evidence, and its epistemic status remain aligned.

## 1. Evidence-First rule

A claim is not GREEN because code exists or a local test passed. A milestone is GREEN only when the required acceptance gates, target revision, CI telemetry, and reproducible evidence agree.

Every contribution must distinguish:

- **implementation** — what the code does;
- **contract** — what tests and specifications require;
- **evidence** — what was actually observed in a reproducible run;
- **interpretation** — what the evidence permits us to conclude.

Never turn an expected result into an observed result. Never mark a gate VERIFIED from an unexecuted workflow, a guessed SHA, or a copied artifact.

## 2. Gate lifecycle

Use this lifecycle for research milestones:

1. **SPECIFIED** — acceptance contract is written.
2. **IMPLEMENTED** — code and tests exist.
3. **EXECUTED** — the exact acceptance contract was run.
4. **EVIDENCED** — CI/local telemetry and artifacts are retained.
5. **VERIFIED** — evidence matches the target commit and contract.
6. **CLOSED** — the milestone record explicitly records the verified evidence.

A failed, missing, stale, or mismatched artifact keeps the gate OPEN. Do not repair a historical artifact by editing it in place; create a new run/evidence record.

## 3. Baseline and provenance

When a task names a baseline SHA, treat it as immutable. Before publishing a commit:

```bash
export JAMP_BASELINE_SHA=<exact-known-sha>
python tools/check_baseline.py
```

The check is local and network-free. It verifies that Git can resolve the baseline and that it is an ancestor of the current `HEAD`. If no baseline is supplied, the check refuses to invent one.

Do not confuse:

- a Git commit SHA;
- an experiment/state digest;
- an artifact SHA-256;
- a workflow run ID.

They identify different objects and must remain separate in evidence.

## 4. Research isolation

Research modules must not silently depend on `jamp.domain`, network clients, or filesystem state when their contract requires deterministic in-memory operation. Existing isolation tests are part of the architecture, not optional style checks.

New dependencies must be justified. Prefer the Python standard library in the verified core. Developer tooling may be installed in an isolated environment and must not become a runtime dependency of `jamp.research`.

## 5. Tests and gates

Run the narrowest relevant contract first, then the full suite:

```bash
PYTHONPATH=src pytest -q <relevant-test>
PYTHONPATH=src pytest -q
```

For developer tooling:

```bash
pre-commit run --all-files
python tools/check_baseline.py
python tools/generate_sbom.py --output sbom.cdx.json
```

Do not weaken a gate merely to make CI green. If a contract is wrong, change the specification and record why; if the implementation is wrong, fix the implementation and preserve the original evidence.

## 6. Static quality checks

The repository uses `ruff` and `mypy` as developer-quality checks. They are configured for offline execution: no command is permitted to fetch packages or contact a service at lint/type-check time.

If the required tools are not already installed locally, install them into an isolated development environment before working offline. The JAMP core itself must not import either tool.

## 7. Pull requests

A PR should state:

- the milestone/gate affected;
- the exact baseline and target SHA where relevant;
- files/contracts changed;
- tests executed and their result;
- evidence/artifact identifiers;
- whether the result is supported, falsified, or inconclusive;
- any known limitation or unverified assumption.

Keep architectural, causal, provenance, and ordinary maintenance changes distinguishable. Changes to architecture/core/causal semantics require provenance according to the repository's provenance contract.

## 8. Commits

Use focused commits. Do not mix generated evidence with unrelated source changes. Generated SBOM output belongs to CI artifacts unless a milestone explicitly requires committing it.

Before pushing:

```bash
git status --short
pre-commit run --all-files
JAMP_BASELINE_SHA=<exact-known-sha> python tools/check_baseline.py
```

A clean result means the checks passed; it does not mean a research milestone is VERIFIED. Verification still requires the prescribed evidence.

## 9. Extensions

Third-party engines and plugins belong above the verified core boundary. They may consume stable public contracts but must not mutate causal history, bypass provenance, or import private research implementation details. Start from `templates/jamp-plugin/` and keep extension-specific dependencies outside the core package.

## 10. CI failure and telemetry recovery playbook

When a test, check, or workflow appears stuck, diagnose the evidence path before changing code.

### 10.1 First classify the failure

Use this order:

1. **Code/contract failure** — a workflow exists, ran against the target SHA, and produced a failing job.
2. **Static-quality failure** — the contract tests pass but Ruff/mypy/pre-commit blocks the developer-quality gate.
3. **Workflow telemetry failure** — the target SHA has no registered workflow run, or the expected check has not been emitted.
4. **Post-merge registration delay** — the merge commit exists but its `workflow_runs`/check-runs are temporarily empty.
5. **Evidence mismatch** — a run belongs to another SHA, branch, or historical attempt.

Do not treat cases 3–5 as application failures.

### 10.2 Always bind CI evidence to the exact SHA

For every gate record:

- target commit SHA;
- workflow/run ID;
- job/check-run ID when available;
- conclusion;
- relevant log evidence.

A green run on an earlier commit does not verify a later commit. A PR-head run does not by itself verify the merge commit. Never substitute a nearby SHA because it is convenient.

### 10.3 If workflow runs are empty

If the GitHub API returns no workflow runs for the exact target SHA:

- do not claim PASS or VERIFIED;
- do not invent a run ID;
- do not rewrite tests merely to provoke CI;
- inspect workflow triggers and the target commit first;
- if the event is a push/merge event, allow for registration delay;
- only change workflow configuration after the trigger failure is evidenced.

A harmless documentation/research commit must not be created solely to manufacture evidence.

### 10.4 If Ruff is the only blocker

Do not weaken Ruff configuration or disable rules just to obtain GREEN.

For common `I001` import-order failures:

1. inspect the exact Ruff output;
2. separate standard-library and local imports;
3. use the repository's formatter/import ordering;
4. rerun the narrow affected tests and Ruff;
5. preserve the contract unchanged.

For `E501`, shorten or structurally reformat the affected line; do not remove assertions or reduce test coverage.

### 10.5 If tests pass but a gate is red

Inspect the failing gate's job log. Distinguish:

- test failure;
- lint/format failure;
- mypy failure;
- baseline/Frozen Core integrity failure;
- SBOM failure;
- workflow/infrastructure failure.

Only the first four may justify source/test changes, and the exact log must support the change. Infrastructure failures require infrastructure/trigger diagnosis, not test mutation.

### 10.6 Full-suite result is not milestone verification

`pytest` passing is necessary evidence when required, but it is not sufficient for VERIFIED. The required five gates and their exact target SHA must agree with the acceptance contract.

### 10.7 Frozen Core emergency rule

Before every research change, verify that `src/jamp` remains outside the change set. The canonical Frozen Core `src/jamp/run.py` blob is:

`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Do not modify, rehash-substitute, or “temporarily” patch Frozen Core to make a research experiment or CI gate pass. A core change requires separate evidence that the research contract cannot be satisfied at the existing boundary.

### 10.8 Recovery rule

After a failure is fixed:

1. create a new commit;
2. run the relevant contract again;
3. wait for CI on that exact commit;
4. record the new run IDs and conclusions;
5. only then advance the gate.

Historical failures remain part of the evidence chain. Never overwrite their meaning by reporting only the final green attempt.

## 11. Extensions

Third-party engines and plugins belong above the verified core boundary. They may consume stable public contracts but must not mutate causal history, bypass provenance, or import private research implementation details. Start from `templates/jamp-plugin/` and keep extension-specific dependencies outside the core package.
