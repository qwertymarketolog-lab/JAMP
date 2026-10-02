# Pytest Launcher Contract v0.1

**Status:** DESIGN-ONLY / PRE-IMPLEMENTATION  
**Version:** v0.1  
**Scope:** CI test-launcher semantics only.

## 1. Purpose

Define an explicit launcher contract so that the test runner's module-search semantics are part of the reproducibility boundary rather than an undocumented property of the CI image.

This contract records the verified differential between the historical `pytest` console launcher and `python -m pytest`. It does not modify `.github/workflows/test.yml`, the test suite, or the Frozen Core.

## 2. Provenance finding

- `pytest` was the original runner contract introduced with `test.yml` at commit `7e14d5b0265c19e107dbcf9c4f616acccac5ddf7`.
- `python -m pytest` was added later in PR #240 / commit `09128a9a0fb0288eecfb40452893aedf059c1ee1` as an A/B diagnostic comparator.
- The original workflow did not document a reason for selecting the console launcher.
- In the controlled A/B run, both launchers used Python 3.11.16, pytest 9.1.1, the same working directory, and `PYTHONPATH=src`; the console launcher produced collection/import errors while `python -m pytest` reached `1533 passed, 1 deselected, 1 warning`. The containing CI run still concluded `failure` because later report generation failed. This is differential evidence, not a GREEN result.

## 3. Normative launcher rule

For a future implementation change:

1. The canonical CI test invocation SHALL be `python -m pytest`.
2. The Python interpreter used to launch pytest SHALL be the interpreter selected by the workflow's Python setup step.
3. The launcher contract SHALL explicitly declare the intended `PYTHONPATH` value.
4. The console command `pytest` SHALL NOT be treated as semantically equivalent by default.
5. A `pytest` vs `python -m pytest` comparison SHALL be treated as a diagnostic differential whenever both are executed.

## 4. Differential invariant

Given the same:

- Python interpreter/version,
- pytest version,
- working directory,
- repository revision,
- environment variables,
- `PYTHONPATH`,
- pytest arguments,

the two invocations

`pytest <args>`

and

`python -m pytest <args>`

MUST be compared as potentially different launch contexts.

A PASS-equivalence claim requires direct runtime evidence that their relevant import/search-path semantics are equivalent for the tested environment. Matching package versions alone are insufficient.

Observed divergence MUST be recorded as:

`LAUNCHER_DIFFERENTIAL = OBSERVED`

until its cause and scope are verified.

## 5. Fail-closed rules

- Missing launcher/path evidence => UNKNOWN.
- A successful `python -m pytest` invocation does not establish equivalence of `pytest`.
- A failing `pytest` invocation does not by itself prove a pytest defect; launcher/search-path semantics remain a candidate cause until verified.
- No launcher change is justified solely by historical convention; implementation requires a separate change and terminal CI evidence.
- No CI rerun is part of this design-only contract.

## 6. Boundary

This contract MUST NOT:

- modify `.github/workflows/test.yml`;
- modify tests;
- add runtime/provider calls;
- modify AEW contracts or StateMachine behavior;
- modify `src/jamp/run.py`.

Frozen Core: `src/jamp/run.py` blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`; expected `Δ=0`.

## 7. Implementation gate

A later implementation PR may change the launcher only after:

1. target workflow/ref is verified;
2. the exact interpreter and launcher semantics are observable;
3. terminal CI evidence is obtained for the changed workflow;
4. PR CI and post-merge main CI are evaluated separately.

Until then, this document is a design contract only.
