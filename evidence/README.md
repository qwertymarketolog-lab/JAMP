# JAMP-INNOVATION Evidence Protocol

## Purpose

This directory convention applies to every innovation module. Evidence must make it possible for another reviewer to identify what was observed, how it was obtained, under which conditions, and what the observation does and does not support.

A claim without sufficient evidence remains `UNKNOWN` or `INCONCLUSIVE`. Confidence, plausibility, repetition, and presentation quality do not substitute for evidence.

## Evidence classes

- **RAW** — original measurement, instrument output, test log, provider response, or unmodified source artifact.
- **DERIVED** — calculation, transformation, analysis, chart, or interpretation produced from identified inputs.
- **EXTERNAL** — published standard, paper, datasheet, regulation, or other externally hosted source.
- **SIMULATED** — output of a simulation or model, with model/version, assumptions, parameters, and limitations recorded.

Keep raw inputs separate from parsed or derived outputs. Never overwrite raw evidence with a cleaned, normalized, or summarized version. Store a derived artifact separately and link it to every input it depends on.

## Required evidence record

For each evidence item, create a stable ID (for example `JI-04-E-001`) and record:

1. **Claim:** the exact, bounded statement the item is intended to support.
2. **Class:** RAW, DERIVED, EXTERNAL, or SIMULATED.
3. **Origin:** creator/organization, instrument or system, publication, repository, and source location as applicable.
4. **Acquisition:** date/time in UTC, retrieval or test procedure, operator, and relevant environment.
5. **Configuration:** hardware, software, firmware, model/version, calibration state, settings, units, and parameter values relevant to reproduction.
6. **Integrity:** filename, byte size, media type, and SHA-256 where useful; preserve the original artifact.
7. **Lineage:** parent evidence IDs and exact transformation/code/command used for derived evidence.
8. **Result:** observed values with units, uncertainty, sample count, exclusions, and anomalies.
9. **Limitations:** missing data, confounders, scope limits, assumptions, and what the item cannot establish.
10. **Review:** reviewer, review date, checks performed, and disposition.

Suggested record file: `evidence/JI-XX-E-###.md`. Store accompanying raw files under a clearly named subdirectory. Do not place credentials, personal data, or restricted material in the repository.

## Source and measurement rules

- Prefer primary sources and traceable instrument outputs. Record exact document title, author/publisher, version or edition, publication date, page/section, URL, and access date for external material.
- For standards and regulations, identify jurisdiction and edition/date. A citation alone does not establish compliance.
- For physical measurements, record instrument identity, calibration status, setup, environmental conditions, method, units, uncertainty, and safety controls.
- For calculations, preserve equations, units, input values, source IDs, assumptions, and enough precision to reproduce the result.
- For simulations, preserve model source/version, solver, boundary conditions, parameter values, validation status, and sensitivity/uncertainty analysis. Label all outputs as simulated.
- For AI outputs, preserve model/provider/version, prompt or input, parameters, timestamp, raw response, and independent validation. An AI-generated statement is not its own corroboration.
- For negative results, record the test's detection limits and coverage. Failure to observe an event is not proof that the event is impossible or absent.

## Integrity and interpretation

- A hash supports byte-level integrity comparison only. It does not prove authenticity, provenance, correctness, or truth.
- A URL can change or disappear. Preserve permitted source snapshots or bibliographic metadata and record the retrieval date.
- Distinguish observation from inference, correlation from causation, and a test result from a general safety or performance claim.
- Do not silently repair, normalize, or replace source records. Record corrections as new derived evidence with lineage.
- Conflicting sources remain visible. Record the conflict; do not select the convenient result without justification.
- Missing, inaccessible, stale, ambiguous, or non-terminal evidence is not PASS.

## GitHub Actions / CI evidence

When a claim depends on CI, record the complete terminal chain:

`repository + workflow identity + commit SHA → Run ID → Job ID → terminal conclusion → artifact ID`

Also record artifact name, download time, checksum if available, and the exact files/results inspected. A green badge, queued run, job summary without terminal status, or uninspected artifact is insufficient. Distinguish PR-head CI from post-merge CI. If a required run/job/artifact is unavailable, mark the check `UNKNOWN` / `HOLD`, not PASS.

## Review dispositions

Use only:

- `SUPPORTED_WITHIN_SCOPE` — evidence supports the explicitly bounded claim.
- `CONTRADICTED` — evidence conflicts with the claim under the recorded conditions.
- `INCONCLUSIVE` — evidence exists but cannot resolve the claim.
- `UNKNOWN` — evidence is absent or not yet obtained.
- `NOT_REVIEWED` — no independent review has occurred.

A reviewer must not approve their own evidence as independent validation. Record review scope and limitations.

## JAMP-2 read-only boundary

JAMP-2 is read-only for this initiative. Do not modify its repository, branches, issues, workflows, settings, or Frozen Core. If a separately authorized inspection reads any Frozen Core content, record:

- repository and exact path;
- immutable commit SHA and tag/version, if applicable;
- blob SHA for the exact file;
- retrieval date/time (UTC);
- purpose and exact read scope;
- resulting evidence ID and limitations.

Do not copy source code into this initiative unless separately authorized and legally appropriate. A file hash alone is not proof of semantic equivalence or correctness.

## Safety and release boundary

A simulation, bench PoC, or isolated component test does not establish human-use safety, environmental qualification, certification, or operational readiness. High-consequence systems require hazard analysis, qualified domain review, controlled testing, and applicable standards before claims are promoted.

This protocol does not authorize integration, deployment, human testing, or merge into the main JAMP branch.
