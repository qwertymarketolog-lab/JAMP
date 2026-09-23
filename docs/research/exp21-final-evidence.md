# EXP-21 Final Evidence Record

## State

**EXP-21 = INCONCLUSIVE / HOLD**

This record closes the current EXP-21 investigation boundary. No further GC runs are authorized under this experiment without a separately defined experiment contract.

## Frozen Core

- Locked path: `src/jamp/run.py`
- Expected blob: `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`
- Frozen Core was not modified by the EXP-21 evidence work.

## Evidence chain

### 1. OS N=20

Canonical G4 workload:
- Ubuntu: 10 laps
- macOS: 10 laps
- 10/20 observations exceeded 15 ms
- Ubuntu: 6/10
- macOS: 4/10
- Ubuntu p50: 16.667 ms
- Ubuntu p95: 18.053 ms
- macOS p50: 13.275 ms
- macOS p95: 18.930 ms

**Verified interpretation:** tails were observed on both OS families. The evidence does not support an OS-only explanation.

**Question status:** CLOSED for the tested OS-only hypothesis.

### 2. Paired GC intervention N=40

Paired CONTROL vs controlled-GC-intervention evidence was collected on the canonical workload.

Historical indices [2, 15, 22, 35] did not reproduce a unique intervention signature attributable specifically to GC. Observed wall changes aligned substantially with component-level variation, especially the acyclic component, while reachable timings were comparatively stable.

GC counters for the reconciled historical observations were:
- CONTROL: gen0=143, gen1=12, gen2=1
- INTERVENTION: gen0=1, gen1=0, gen2=0

**Verified interpretation:** the intervention changed GC state, but the tested intervention did not reproduce the historical-tail pattern as a specific GC effect.

**Question status:** CLOSED for the tested paired-intervention hypothesis.

### 3. Historical tails [2, 15, 22, 35]

The four historical indices were reconciled against the paired N=40 evidence.

**Verified interpretation:** no reproducible per-lap signature was established that maps these four historical tail positions to a unique GC event/effect.

**Question status:** CLOSED for the tested historical-tail/GC signature hypothesis.

### 4. Temporal GC probe

Exact historical EXP-19 target:
`8c6b6a40f019d727a1ef630975a2691a390affd6`

Experiment:
`EXP-21-TEMPORAL-GC-PROBE-V2`

Terminal CI evidence:
- Workflow: `EXP-21 Temporal GC Probe`
- Run: `35829358254`
- Job: `107078157947`
- Head SHA: `a9683f6cfae749265195faa4a983979e112149f7`
- Conclusion: `success`
- Artifact: `10736411667`
- Artifact SHA-256: `b6179877e9872ee406f6596e054c4157e1d8dc05912de8e57da23626794d5979`
- Artifact file: `artifacts/research/exp21_temporal_gc_probe.json`

Validation established:
- exact target commit
- canonical workload spec
- canonical workload definition hash
- Frozen Core blob
- N=40
- rows 1..40
- historical indices [2,15,22,35]
- terminal artifact validation

Observed temporal-probe characteristics:
- wall p50 ≈ 155.127 ms
- CPU p50 ≈ 155.050 ms
- component p50 ≈ 12.603 ms
- max |wall-CPU| ≈ 0.121 ms
- GC collection occurred in all 40 laps

Historical indices:
- lap 2: wall 148.718 ms, CPU 148.722 ms, acyclic 6.812 ms, reachable 5.186 ms, GC delta [140,12,1]
- lap 15: wall 151.151 ms, CPU 151.154 ms, acyclic 6.961 ms, reachable 5.537 ms, GC delta [139,13,1]
- lap 22: wall 150.064 ms, CPU 150.067 ms, acyclic 6.757 ms, reachable 5.332 ms, GC delta [140,12,1]
- lap 35: wall 152.743 ms, CPU 152.746 ms, acyclic 6.950 ms, reachable 5.633 ms, GC delta [139,13,1]

**Verified interpretation:** GC activity was observed, but the historical indices did not show a unique temporal GC signature.

**Critical limitation:** the temporal probe runtime regime (~155 ms) is materially different from the historical EXP-19 regime (~10–15 ms). Therefore absolute wall-time reconciliation between this probe and the historical tails is not valid without a separately established measurement-boundary/environment reconciliation.

**Question status:** INCONCLUSIVE for historical-scale causal reconciliation.

## Final causal status

### Closed

The current evidence closes these narrower questions:

1. Are the observed tails explained by one OS family only? **No supporting evidence; CLOSED for the tested OS-only hypothesis.**
2. Does controlled GC intervention reproduce the historical tail pattern? **No; CLOSED for the tested intervention.**
3. Do historical tail indices [2,15,22,35] carry a reproducible unique GC signature in the tested evidence? **No; CLOSED for the tested signature.**

### UNKNOWN

The stronger causal proposition remains:

> GC caused the historical EXP-19 latency tails.

**Status: UNKNOWN.**

The evidence neither proves nor disproves that proposition because the temporal probe did not operate in the same absolute measurement regime as the historical EXP-19 observations.

## Stop condition

EXP-21 stops here.

State transition:

`RUNNING → INCONCLUSIVE / HOLD`

Reason:
- the defined evidence chain has been exercised;
- no reproducible GC-specific historical-tail signature was established;
- the remaining UNKNOWN requires a different experimental boundary rather than another repetition of the same GC probes.

Any future attempt to reconcile the historical ~10–15 ms regime with the temporal probe's ~155 ms regime must be opened as a **new experiment with a new contract**, not appended to EXP-21.

## Non-actions

- No Frozen Core modification.
- No G4 threshold relaxation.
- No synthetic PASS.
- No causal claim from absence of a signature.
- No new GC run under EXP-21.
- PR #158 remains separate PR-CI evidence; it is not post-merge main evidence.

## PR #164 Lifecycle Reconciliation

This section records the read-only reconciliation of PR #164 across two observed GitHub test-merge states.

### Historical test-merge state 1

**GitHub evidence (2026-09-23):**
- PR: #164
- PR state: `open`
- `merged`: `false`
- `merged_at`: `null`
- Base: `main`
- Base SHA: `98992070b59450a760da63544164af94a6520914`
- Head SHA: `42ebdd89b463565a2d99388e8463404687f39532`
- `merge_commit_sha`: `b1a3fa14439eb4a5e56106ff2c5d467fb9115d7f`
- `refs/pull/164/head` → `42ebdd89b463565a2d99388e8463404687f39532`
- `refs/pull/164/merge` → `b1a3fa14439eb4a5e56106ff2c5d467fb9115d7f`
- `refs/heads/main` → `98992070b59450a760da63544164af94a6520914`

**Interpretation:** `b1a3fa14…` was the GitHub PR test/simulated merge commit for head `42ebdd89…`. It was not evidence of an actual merge.

### Current test-merge state 2

After the evidence-record commit, PR HEAD advanced to:

- Head SHA: `4dd1e4c9f5bd3a3695ebceb7eceaefae4f467129`
- PR state: `open`
- `merged`: `false`
- `merged_at`: `null`
- Base SHA: `98992070b59450a760da63544164af94a6520914`
- Current `merge_commit_sha`: `decd8a8d285815222ed3f33e19f6bf0a7f4e4a5a`
- `refs/pull/164/head` → `4dd1e4c9f5bd3a3695ebceb7eceaef4f467129`
- `refs/pull/164/merge` → `decd8a8d285815222ed3f33e19f6bf0a7f4e4a5a`
- `refs/heads/main` → `98992070b59450a760da63544164af94a6520914`

The current test-merge commit message is:

`Merge 4dd1e4c9f5bd3a3695ebceb7eceaef4f467129 into 98992070b59450a760da63544164af94a6520914`

**Interpretation:** `decd8a8d…` is verified as the second GitHub PR test/simulated merge commit, generated for the new HEAD `4dd1e4c9…`. It is not a merge of PR #164 into `main`.

### Terminal PR CI for current HEAD

For HEAD `4dd1e4c9…`, the required PR workflows reached terminal success:

- P23.0-B Cold Replay Diagnostic: run `35830117269`, conclusion `success`
- Developer Quality: run `35830117237`, conclusion `success`

Together with the five previously completed PR workflows, current PR CI is **7/7 terminal success** for HEAD `4dd1e4c9…`.

**CI scope:** this is PR-level CI. It is not post-merge main CI.

**Lifecycle status:** **VERIFIED TEST-MERGE / NOT-MERGED**.

**Event provenance:** the exact server-side event that caused creation/update of either test-merge ref remains **UNKNOWN** with the currently exposed GitHub connector event surface.

**Non-actions:** no merge, ref update, rerun, or other GitHub mutation was performed as part of this reconciliation.

**Frozen Core:** `src/jamp/run.py` remains at locked blob `0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`.

### Final reconciliation — current PR state

Read-only GitHub reconciliation immediately before this evidence update:

- PR: #164
- PR state: `open`
- `merged`: `false`
- `merged_at`: `null`
- Base: `main`
- Base SHA / current `main`: `98992070b59450a760da63544164af94a6520914`
- Current PR HEAD: `134f20935190b713822d378d7224ebd022e5f972`
- Current `refs/pull/164/head` → `134f20935190b713822d378d7224ebd022e5f972`
- Current `refs/pull/164/merge` → `2226adece9ea312cc95e8c96f8da61965ab1c3c5`
- PR metadata `merge_commit_sha` → `2226adece9ea312cc95e8c96f8da61965ab1c3c5`
- Current test-merge relationship: `134f2093… + main 98992070… → 2226adece…`

**Verified interpretation:** `2226adece…` is the current GitHub PR test/simulated merge ref for HEAD `134f2093…`. It is not evidence of an actual merge of PR #164 into `main`.

**Reconciliation:**

`HEAD 134f20935190b713822d378d7224ebd022e5f972 → test-merge 2226adece9ea312cc95e8c96f8da61965ab1c3c5 → main 98992070b59450a760da63544164af94a6520914`

**Non-actions:** this update changes only this documentation file. No merge, main ref update, Frozen Core modification, CI rerun, or threshold change is performed by this action.
