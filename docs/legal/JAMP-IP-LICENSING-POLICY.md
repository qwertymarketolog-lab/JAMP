# JAMP IP & Licensing Policy

## Status

This document records the current repository-level intellectual-property and licensing policy for JAMP.

It is a project policy and provenance record. It is not a substitute for legal advice, a copyright assignment, a contributor agreement, or a trademark registration.

## 1. Copyright

The current project-level copyright notice is:

**Copyright (C) 2026 Viskunov Eduard Leonidovich.**

Copyright in an individual contribution remains with its author unless a separate written agreement provides otherwise.

The repository's Git history, signed releases, tags, and retained evidence provide provenance for the development history. They do not by themselves transfer copyright ownership.

Before accepting substantial third-party contributions, the project should maintain a clear record of the contributor and the applicable contribution terms.

## 2. Software license

Effective for the code distributed from the licensing change recorded in this repository, JAMP code is licensed under:

**GNU Affero General Public License v3.0 only (AGPL-3.0-only).**

The canonical license text is stored in the repository root as LICENSE.

The change from Apache-2.0 to AGPL-3.0-only is a licensing change in the current project line. Historical commits retain the license notices applicable to those commits; replacing LICENSE does not retroactively rewrite historical licensing.

AGPL-3.0-only is intended to preserve the freedom to use, modify, and redistribute JAMP while addressing modified versions that are made available to users over a network. The exact legal obligations are those of the license text in LICENSE.

## 3. Repository components

The default policy is:

| Component | Policy |
|---|---|
| JAMP source code | AGPL-3.0-only |
| Existing third-party code | Its own applicable license; do not relicense it as JAMP code |
| Third-party dependencies | Their own licenses and notices remain applicable |
| Research artifacts | License must be checked per artifact before redistribution |
| Documentation | Copyright remains with its authors unless a file states a separate license |
| Trademarks / names | Separate from the software license |
| Experimental data | Governed by its applicable source, consent, privacy, or dataset terms |

A file-level or directory-level license notice takes precedence over this default where it explicitly states a different applicable license.

## 4. Contributions

At present, JAMP does **not** claim a blanket copyright assignment from contributors.

A contribution is accepted under the repository's published contribution terms and the AGPL-3.0-only licensing model applicable to the project code.

A future dual-license or proprietary-license offering requires sufficient rights from all relevant copyright holders. Before such a model is used for contributed code, the project must adopt and publish an appropriate contributor agreement or other legally sufficient rights mechanism.

No contributor is assumed to have transferred copyright merely by opening an issue, pull request, or discussion.

## 5. Commercial licensing

AGPL licensing does not prevent commercial activity. Commercial services, support, hosting, integration, consulting, and other offerings may be built around JAMP subject to the applicable license and third-party rights.

A separate proprietary commercial license may be offered only for code for which JAMP has the necessary rights.

No promise of future proprietary relicensing is made to contributors until a contributor agreement and ownership model are formally adopted.

## 6. Trademark boundary

The software license does not grant ownership of or unrestricted rights to the JAMP name or marks.

The project intends to treat **JAMP** as a distinct brand asset. Trademark clearance and registration are separate legal work.

Until registration is confirmed, the project may use JAMP™ where appropriate. The registered-mark symbol ® must not be used as a claim of registration before registration exists.

Trademark classes, jurisdictions, and filing strategy must be selected after a clearance search and professional review.

## 7. Patent and invention boundary

Publication of repository material can affect patent rights in some jurisdictions.

If a potentially patentable technical invention is identified, the project should perform an IP/patent review before public disclosure of enabling details or claims where patent protection is being considered.

This policy does not claim that JAMP has patent protection. It records a preservation rule: **do not assume that public Git history preserves patent novelty.**

## 8. Frozen Core

The licensing policy does not modify the Frozen Core.

In particular:

- src/jamp/run.py remains subject to the existing Frozen Core invariant;
- licensing work must not be used as a reason to change runtime behavior;
- product and commercial layers integrate through documented boundaries and adapters;
- evidence, provenance, conflict, and experiment contracts remain explicit.

## 9. Evidence and provenance

Legal and licensing claims must remain distinguishable from technical evidence.

The repository should preserve:

- exact commit SHAs;
- release/tag history;
- contributor identity where legally appropriate;
- applicable license files;
- third-party notices;
- provenance of externally sourced code;
- records of any future contributor agreement;
- trademark filing and registration records outside the code license.

## 10. Planned legal hardening

Before the project accepts material external contributions or launches a commercial dual-licensing offer, review:

1. copyright ownership and any employer/institution claims;
2. contributor agreement / CLA terms;
3. third-party dependency compatibility;
4. trademark clearance and classes;
5. patent strategy before public disclosure;
6. documentation and dataset licensing;
7. jurisdiction-specific requirements.

This review should be performed by qualified legal/IP counsel where the project is relying on enforceable ownership or licensing rights.

## 11. Non-retroactivity

This policy records the current project line. It does not rewrite:

- historical commit licenses;
- licenses attached to third-party material;
- previously granted licenses;
- rights held by contributors who did not transfer them.

The evidence history must remain auditable.

## 12. Decision record

The current project direction is:

**JAMP code → AGPL-3.0-only**  
**JAMP name/marks → separate trademark asset**  
**Contributors → retain copyright unless a separate agreement states otherwise**  
**Future dual licensing → only after a legally sufficient contributor-rights mechanism exists**  
**Frozen Core → unchanged and protected**  
**Patent-sensitive inventions → review before public disclosure**
