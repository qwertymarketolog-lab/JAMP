# G1 PR Association Probe

Temporary deterministic probe for AT-G1-ASSOC-01.

Expected invariants:
- G1 Trusted Lineage is a native pull_request_target check.
- G1 must bind to the PR head SHA.
- Research Loop v0 Gate must be successful for the same SHA.
- Frozen Core remains 0fee0e1c5c1a1548361965ac51eacdeba62bfe8a.

Probe is evidence-only and introduces no runtime behavior.
