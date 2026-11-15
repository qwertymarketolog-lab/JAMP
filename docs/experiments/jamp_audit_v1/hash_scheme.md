# JAMP Audit v1 — Hash Scheme

## Immutable experiment input

The only static experiment input is the committed byte sequence of:
- docs/experiments/jamp_audit_v1/INPUT_PACK.md

Algorithm: SHA-256 over the exact file bytes, not Git's object hash.

Literal baseline value:
- INPUT_PACK.md: d061a22e1ca2d3ff3c2e640f1903d475436527a1e87754f89a122424db5db423

This value is fixed for this experiment snapshot. Any byte change, including whitespace, Unicode representation, or final newline, invalidates the prior run and requires a new recorded input hash.

## Prompt version identity

The audit prompt is embedded in scripts/research/jamp_audit_v1.py; there is no separate AUDIT_PROMPT.md input file.

Record the repository commit SHA for the run and identify the exact prompt-bearing source revision with:

    git rev-parse <commit>:scripts/research/jamp_audit_v1.py

This returns the Git blob object ID for the prompt-bearing source file at that commit. It is a source-version identifier, not a SHA-256 hash of a separate prompt input. Do not hash the entire runner as an experiment input and do not report an AUDIT_PROMPT.md SHA-256.

## Byte and checkout rules

- INPUT_PACK.md is UTF-8 and committed with LF line endings.
- .gitattributes marks INPUT_PACK.md -text; Git must not apply text/EOL conversion.
- No Unicode normalization, trimming, whitespace folding, newline insertion, or newline removal occurs before hashing.
- Hash exactly the bytes read from disk and supplied to the model.
- The test suite clones the checked-out repository into a clean temporary directory with core.autocrlf=true, then compares INPUT_PACK.md byte-for-byte and SHA-256-for-SHA-256.

Reference command from repository root:

    python -c 'import hashlib,pathlib; p=pathlib.Path("docs/experiments/jamp_audit_v1/INPUT_PACK.md"); print(hashlib.sha256(p.read_bytes()).hexdigest())'

## Response body and text hashes

The transport adapter supplies response_body_bytes after HTTP transfer framing is removed and any declared Content-Encoding (for example gzip) has been decoded, but before character decoding. This harness accepts those bytes; it does not perform HTTP or transport decoding.

- response_body_bytes_sha256: SHA-256 of those exact decoded HTTP entity-body bytes.
- response_text_sha256: SHA-256 of the exact response text re-encoded as UTF-8 after strict decoding with the declared response charset (UTF-8 by default).
- No Unicode normalization or text cleanup is performed.
- If strict text decoding fails, preserve the body hash, set the text hash to null, and report UNKNOWN / RESPONSE_TEXT_DECODE_ERROR.
- For valid UTF-8, the two hashes may be identical; this is expected.

The two hashes answer different boundary questions and must never be silently substituted for one another.
