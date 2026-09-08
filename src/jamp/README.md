# JAMP Next — Verification Prototype

This branch is a separate experimental continuation of JAMP. It does not replace the existing JAMP work on `main`.

## Contract

`GENERATOR -> EVALUATE -> VERIFY -> COMMIT`

- **Generator** proposes candidates.
- **KnowledgeSource** supplies evidence.
- **Verifier** classifies a candidate as `CONFIRMED`, `CONFLICT`, or `UNKNOWN` in the minimal prototype.
- **Registry** stores only committed verified candidates.
- **History** records the event sequence for reproducibility.

The prototype deliberately does **not** make medical decisions, establish clinical truth, or treat traditional recipes as medical treatments. Those domains require authoritative datasets, provenance, domain rules, and expert review.

## Run the synthetic demo

```bash
PYTHONPATH=src python3 -m jamp.demo_food
```

## Test

```bash
PYTHONPATH=src python3 -m pytest -q src/jamp/tests
```
