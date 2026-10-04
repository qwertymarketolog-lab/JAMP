# JAMP MVP

The product application layer lives under `src/jamp_app/` and is additive to the existing JAMP core.

The Frozen Core remains locked at `src/jamp/run.py`; MVP application work must not modify it.

P0-001 establishes the application boundary. P0-002 adds a dependency-free WSGI API skeleton with a health endpoint; provider, chat, experiment, evidence, verification, and benchmark execution remain subsequent P0 tasks.
