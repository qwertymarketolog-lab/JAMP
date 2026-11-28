# JAMP-INNOVATION Registry

**Registry status:** INITIAL BASELINE — ownership and TRL assessments pending  
**Last updated:** 2026-11-27  
**Parent branch:** `jamp-innovation`

This registry tracks innovation modules. A branch existing in Git does not make it active. Per D-03, each module remains `INACTIVE` until its own `INNOVATION_CARD.md` is present, reviewed for completeness, and an accountable owner has explicitly accepted responsibility.

## Status vocabulary

- `INACTIVE` — branch exists, but activation prerequisites are not met.
- `PROPOSED` — card and owner recorded; scope awaits review.
- `ACTIVE` — owner accepted and card reviewed; bounded work may proceed.
- `BLOCKED` — a named dependency prevents progress.
- `HOLD` — evidence or safety uncertainty prevents a decision.
- `COMPLETE` — module's stated acceptance criteria have been assessed.
- `REJECTED` — hypothesis or approach rejected with rationale preserved.

TRL is `UNKNOWN` until a framework-specific assessment is supported by evidence. Do not infer it.

## Module registry

| Code | Direction | Branch | Accountable owner | TRL | Status | Last review (UTC) | Notes |
|---|---|---|---|---|---|---|---|
| JI-00 | Governance | `ji-00-governance` | UNASSIGNED | N/A | PROPOSED | 2026-11-27 | Shared templates and evidence rules; governance owner not yet accepted |
| JI-01 | JAMP SUIT | `ji-01-jamp-suit` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-02 | JAMP MATERIALS | `ji-02-jamp-materials` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-03 | JAMP EXOSKELETON | `ji-03-jamp-exoskeleton` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-04 | JAMP AI | `ji-04-jamp-ai` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-05 | JAMP ENERGY | `ji-05-jamp-energy` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-06 | JAMP LIFE | `ji-06-jamp-life` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-07 | JAMP ROBOTICS | `ji-07-jamp-robotics` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |
| JI-08 | JAMP FUTURE | `ji-08-jamp-future` | UNASSIGNED | UNKNOWN | INACTIVE | NOT_REVIEWED | Card not yet present |

## Governance rules

1. Each module has one accountable code owner. No owner means no active development.
2. Module work is proposed to `jamp-innovation` through a pull request from its `ji-0X-*` branch; review is mandatory.
3. Keep module work inside its agreed scope and directory structure.
4. Record decisions, assumptions, measurements, source artifacts, and limitations in the module's `evidence/` directory.
5. A PoC is required before integration is considered.
6. The main JAMP branch has a separate gate: substantiated TRL ≥ 6, reviewed evidence, no regressions, and separate written authorization. This registry does not grant that authorization.
7. JAMP-2 and its Frozen Core remain outside the write scope of this initiative. Any explicitly authorized read-only inspection must be recorded with exact repository, ref/version, path, and retrieval date in the relevant module's evidence log.

## Change control

Update this registry through reviewed pull requests. Preserve historical review dates and decisions; do not silently rewrite an earlier assessment. Use `UNKNOWN` or `NOT_REVIEWED` where evidence is absent.
