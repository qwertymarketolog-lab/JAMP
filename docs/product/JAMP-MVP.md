# JAMP MVP

The product application layer lives under `src/jamp_app/` and is additive to the existing JAMP core.

The Frozen Core remains locked at `src/jamp/run.py`; MVP application work must not modify it.

P0-001 establishes the application boundary only. Provider, API, chat, experiment, evidence, verification, and benchmark execution are subsequent P0 tasks.
