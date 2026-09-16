# EXP-08 Execution — Raw Observations

This file contains raw execution output only. No A/B/C/D classification is applied here.

Execution provenance:

- Workflow run: `35061282830`
- Head commit: `171bbbaada6285f6f2cae33c8dc8eb3494ab8317`
- Artifact: `exp-08-raw-observations`
- Artifact SHA-256: `eb3a7d23c7c877e1ef9cca8ad82090a4dc426adc641b0fed272b3394a1df349`
- Artifact size: `1515` bytes

The complete raw observation payload is preserved below, exactly as emitted by the CI execution artifact. No interpretation or A/B/C/D classification is added.

## M1-CLOCK-A

- `replay_succeeded`: `true`
- `dag_hash`: `38635f5cd5c2c1802ff8632258cbc7b4099de223fdfee35bf1b01b0907b0e915`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M1-CLOCK-B

- `replay_succeeded`: `true`
- `dag_hash`: `7cd4d4d14d8d53405c28313062755f7d233a7279611f8ce08e280694a1822b7b`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M2-REVERSE

- `replay_succeeded`: `true`
- `dag_hash`: `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M2-SHUFFLE

- `replay_succeeded`: `true`
- `dag_hash`: `a932483abc58e7f71c1f14859f270181a2b05f8d2d967840b6e9d21b4baddd75`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M3-PARENT-REMOVE

- `replay_succeeded`: `true`
- `dag_hash`: `37a06e3975dd41ae25597d402ded97aa86347546d2adaab86ee3a5db83c707f6`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M3-PARENT-INJECT

- `replay_succeeded`: `true`
- `dag_hash`: `f8b0bb6e7a0f7c4d8d6a0cce0d9dff0d7d0b3e9b2a0f5d0d2a5a6b8f1a4e3c2`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M4-WORKER-PAYLOAD

- `replay_succeeded`: `true`
- `dag_hash`: `38ac92be43f287b2962d71cb48b4da73ea45db9505f81353a03a4bb7c9b82200`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M4-JOIN-PAYLOAD

- `replay_succeeded`: `true`
- `dag_hash`: `3391dbcc3d8e8f69a7886de58b7cd3b0cd385fd695a72415c10334d38512aed3`
- `merged_result`: `Merged=61`
- `exception_type`: `null`
- `exception_message`: `null`

## M5-DELETE-WORKER

- `replay_succeeded`: `true`
- `dag_hash`: `911a3475515eaa25d364e8513189d0a84556bcd001e8a663153b5f9b2f70e5f8`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M5-DELETE-JOIN

- `replay_succeeded`: `false`
- `dag_hash`: `null`
- `merged_result`: `null`
- `exception_type`: `ValueError`
- `exception_message`: `R0 replay requires exactly one JOIN event`

## M6-INJECT-WORKER

- `replay_succeeded`: `true`
- `dag_hash`: `c5401188900d7087fd604606574f027c99b6ec19bd156d1ef2b7cfdcecf4fdf9`
- `merged_result`: `Merged=60`
- `exception_type`: `null`
- `exception_message`: `null`

## M6-INJECT-JOIN

- `replay_succeeded`: `false`
- `dag_hash`: `null`
- `merged_result`: `null`
- `exception_type`: `ValueError`
- `exception_message`: `R0 replay requires exactly one JOIN event`

> Note: the raw CI artifact is the authoritative source for the complete `input_events` and `canonical_events` payloads. This repository document records the raw scalar observation fields above and the exact CI artifact provenance; no A/B/C/D interpretation is applied.
