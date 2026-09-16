# EXP-08 Execution — Raw Observations

This file records the raw scalar observations extracted from the CI execution artifact. No A/B/C/D classification is applied here.

Execution provenance:

- Workflow run: `35061282830`
- Head commit: `171bbbaada6285f6f2cae33c8dc8eb3494ab8317`
- Artifact: `exp-08-raw-observations`
- Artifact SHA-256: `eb3a7d23c7c877e1ef9cca8ad82090a4dc426adc641b0fed272b3394a1df349`
- Artifact size: `1515` bytes

The CI artifact is the authoritative source for the complete `input_events` and `canonical_events` payloads. The scalar observations below are transcribed from that artifact without interpretation.

| Mutation | replay_succeeded | dag_hash | merged_result | exception_type | exception_message |
|---|---:|---|---|---|---|
| M1-CLOCK-A | true | `38635f5cd5c2c1802ff8632258cbc7b4099de223fdfee35bf1b01b0907b0e915` | `Merged=60` | null | null |
| M1-CLOCK-B | true | `7cd4d4d14d8d53405c28313062755f7d233a7279611f8ce08e280694a1822b7b` | `Merged=60` | null | null |
| M2-REVERSE | true | `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75` | `Merged=60` | null | null |
| M2-SHUFFLE | true | `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75` | `Merged=60` | null | null |
| M3-PARENT-REMOVE | true | `37a06e3975dd41ae25597d402ded97aa86347546d2adaab86ee3a5db83c707f6` | `Merged=60` | null | null |
| M3-PARENT-INJECT | true | `07047a0ecc5e9b68d0c3440ce66f8737e659053d331195af4407120a373aa0ab` | `Merged=60` | null | null |
| M4-WORKER-PAYLOAD | true | `38ac92be43f287b2962d71cb48b4da73ea45db9505f81353a03a4bb7c9b82200` | `Merged=60` | null | null |
| M4-JOIN-PAYLOAD | true | `3391dbcc3d8e8f69a7886de58b7cd3b0cd385fd695a72415c10334d38512aed3` | `Merged=61` | null | null |
| M5-DELETE-WORKER | true | `911a3475515eaa25d364e8513189d0a84556bcd001e8a663153b5f9b2f70e5f8` | `Merged=60` | null | null |
| M5-DELETE-JOIN | false | null | null | `ValueError` | `R0 replay requires exactly one JOIN event` |
| M6-INJECT-WORKER | true | `c5401188900d7087fd604606574f027c99b6ec19bd156d1ef2b7cfdcecf4fdf9` | `Merged=60` | null | null |
| M6-INJECT-JOIN | false | null | null | `ValueError` | `R0 replay requires exactly one JOIN event` |

No A/B/C/D categories or verdicts are recorded in this document.