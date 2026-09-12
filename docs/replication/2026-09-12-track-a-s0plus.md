# Track A S0+ verification — 2026-09-12

## Anchor
`d1b3a8c7e0cb6a16fb2eafacc5509382cecbcc39`

## Environment
Python: 3.13.5
OS:     Debian GNU/Linux 13 (trixie), Linux 6.18.35
Install: none

Execution note: the terminal environment could not resolve `github.com`, so a normal `git clone`/`git checkout` could not be completed. The frozen `track_a/common.py` source was retrieved directly from the GitHub anchor and the `State`/`closure()` implementation was executed in an isolated temporary file. No repository source file was modified.

## Command
`python3 /tmp/probe_s0plus.py`

## Raw output
```text
AFTER_INIT 6
  init[0] = ((p^2)=(2*(q^2)))
  init[1] = prime?(2)
  init[2] = integer?(p)
  init[3] = integer?(q)
  init[4] = (2>1)
  init[5] = gcd(p,q,1)
AFTER_FIRST_CLOSURE 9
  post[0] = ((p^2)=(2*(q^2)))
  post[1] = prime?(2)
  post[2] = integer?(p)
  post[3] = integer?(q)
  post[4] = (2>1)
  post[5] = gcd(p,q,1)
  post[6] = (2|p)
  post[7] = (p=(2*k_6))
  post[8] = integer?(k_6)
```

## Result
AFTER_INIT            = 6
AFTER_FIRST_CLOSURE  = 9
Classification (from pre-registration): B

## Conclusion
S0+ = 9 is reproduced from the frozen Track A source; the prior static reading that predicted 10 was incomplete.

The observed first-closure additions are exactly:
1. `derive_divisibility` → `2|p`
2. `divisibility_witness` → `p=2*k_6`
3. `integer_witness` → `integer(k_6)`

No `2|p²` object is produced by `derive_divisibility` in this anchor; it constructs `div(d, sqe.a[0])`, which for the anchor is `2|p`. Consequently `prime_square_lemma` is not the source of the first-closure increment in this case.

## Not done
- no substitution step executed
- no `run()` executed
- no hash recomputation
- no modification to repository code
