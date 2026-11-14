# JAMP Audit v1 — Hash Scheme

## Immutable experiment inputs

The exact experiment inputs are the committed byte sequences of:
- docs/experiments/jamp_audit_v1/AUDIT_PROMPT.md
- docs/experiments/jamp_audit_v1/INPUT_PACK.md

Algorithm: SHA-256 over exact file bytes, not Git's object hash.

Literal baseline values for this PR:
- AUDIT_PROMPT.md: 4e02860ea088d7f6c5aa4d311b35abfad18c515bd78a2b64999ea5260e405b0e
- INPUT_PACK.md: 4c5aaae052429709ae06536599e22eaec039cff702b9a74cc4d14f770a5cba18

These values are fixed for this experiment revision. Any byte change, including whitespace, Unicode representation, or final newline, invalidates the prior run and requires a new recorded input hash.

## Byte and checkout rules

- Files are UTF-8 and committed with LF line endings.
- .gitattributes marks both inputs -text; Git must not apply text/EOL conversion.
- No Unicode normalization, trimming, whitespace folding, newline insertion, or newline removal occurs before hashing.
- Hash exactly the bytes read from disk and supplied to the model.
- The test suite clones the checked-out repository into a clean temporary directory with core.autocrlf=true, then compares both files byte-for-byte and SHA-256-for-SHA-256.

Reference command from repository root:

    python -c 'import hashlib,pathlib; p=pathlib.Path("docs/experiments/jamp_audit_v1/AUDIT_PROMPT.md"); print(hashlib.sha256(p.read_bytes()).hexdigest()); p=pathlib.Path("docs/experiments/jamp_audit_v1/INPUT_PACK.md"); print(hashlib.sha256(p.read_bytes()).hexdigest())'

## Response body and text hashes

The transport adapter supplies response_body_bytes after HTTP transfer framing is removed and any declared Content-Encoding (for example gzip) has been decoded, but before character decoding. This harness accepts those bytes; it does not perform HTTP or transport decoding.

- response_body_bytes_sha256: SHA-256 of those exact decoded HTTP entity-body bytes.
- response_text_sha256: SHA-256 of the exact response text re-encoded as UTF-8 after strict decoding with the declared response charset (UTF-8 by default).
- No Unicode normalization or text cleanup is performed.
- If strict text decoding fails, preserve the body hash, set the text hash to null, and report UNKNOWN / RESPONSE_TEXT_DECODE_ERROR.
- For valid UTF-8, the two hashes may be identical; this is expected.

The two hashes answer different boundary questions and must never be silently substituted for one another.
