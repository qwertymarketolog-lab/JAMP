# Security Policy

## Scope

This policy covers the public JAMP research repository and its verified core. Research claims, experiment integrity, provenance, and reproducibility are security-relevant when tampering could cause a false verification result.

## Responsible disclosure

Please do **not** disclose an unpatched security vulnerability in a public issue, pull request, commit, or discussion.

Use GitHub's private vulnerability reporting / Security Advisory mechanism for this repository when available. Include:

- affected commit or tag;
- affected file/module;
- minimal reproduction;
- security impact;
- whether the issue can alter provenance, causal ordering, artifact identity, or gate verification;
- any suggested mitigation.

If private vulnerability reporting is unavailable, contact the repository maintainer privately through the contact method listed in the repository profile and do not publish exploit details until a mitigation is available.

## Evidence integrity

Suspected tampering with research evidence should be reported with the exact identifiers available: commit SHA, workflow run ID, artifact name, and SHA-256 digest. Do not replace or rewrite the original evidence record. Preserve the observed state and create a new corrective record.

## Dependency security

The verified core should remain dependency-minimal. New runtime dependencies require review of their provenance and licensing. Developer-only tooling must not become an implicit runtime dependency.

The repository's SBOM workflow is intended to make declared runtime/development dependencies auditable and to detect accidental third-party additions to the core packaging boundary.

## Supported versions

Security fixes should target the current `main` branch unless a release-specific support statement is added to this file. Historical research artifacts are immutable evidence and are not silently rewritten for security maintenance.
