---
applyTo: "src/jamp/run.py"
---

# Frozen Core — Read Only

This path is protected. The only permitted default operation is reading and verifying it.

Required blob SHA:
`0fee0e1c5c1a1548361965ac51eacdeba62bfe8a`

Rules:
1. Do not modify, reformat, regenerate, rename, delete, move, or replace this file.
2. Before committing/pushing and during PR review, verify the Git blob SHA is exactly the required SHA above. The invariant is **Δ = 0**.
3. If the SHA differs, or the requested task requires a change to this file, STOP immediately. Do not try to restore it automatically or continue with dependent implementation.
4. Report **HOLD — CORE UNLOCK REQUIRED**, include the observed SHA and the task dependency, and request explicit human authorization labelled **Core Unlock**.
5. Core Unlock must identify the exact intended change or bounded scope. A general request to implement a feature, fix CI, or work on JAMP is not authorization.
6. No agent may approve its own Core Unlock.

No exception is implied by failing tests, CI failures, refactoring goals, compatibility concerns, or pressure to obtain a green workflow.
