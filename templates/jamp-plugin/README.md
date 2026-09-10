# JAMP plugin template

This template is for extensions that sit **above** the verified JAMP core.

Rules:

- depend only on public JAMP contracts;
- keep plugin dependencies in the plugin project, not the core;
- never mutate causal history in place;
- preserve provenance when producing derived artifacts;
- do not use runtime metadata as content identity;
- provide deterministic tests and a plugin-specific acceptance contract.

See `docs/architecture/p19-p20.7.md` and `CONTRIBUTING.md` before adapting the template.
