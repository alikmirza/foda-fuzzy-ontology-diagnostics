# Fix 8c — closure

**Status: CLOSED, no STOP.** Every check passes against the corrected equations.

**Script:** `paper/notes/fix8c_rederive_corrected.py` — written fresh, implementing
§4.4's corrected (2)–(4) and nothing else. It does not reuse
`paper/notes/fix8c_rederive.py`, which implements the manuscript's former
(mis-transcribed) equations and is retained only as evidence of the disagreement
that raised the STOP on 2026-08-22.

**Run:** `PYTHONWARNINGS=ignore python3 paper/notes/fix8c_rederive_corrected.py`
(exit 0).

## Comparison table

| quantity | expected | computed | verdict |
|---|---|---|---|
| C\* (4 dp) | (0.7255, 0.5271, 0.5453) | (0.7255, 0.5271, 0.5453) | OK |
| C\* (10 dp) | 0.7254554565, 0.5271243564, 0.5453167505 | identical | OK |
| iterations to ε = 10⁻⁶ | 14 | 14 | OK |
| Theorem 1 global bound δ·max(1−H)·W | 0.476 | 0.476 | OK |
| Theorem 2 local bound δ·max(1−H)·ρ(W̃) | 0.476 | 0.476 | OK |
| true ρ(J) at C\* | 0.3614 | 0.3614 | OK |
| geometric-mean identity 0.85·0.7·0.6073 | 0.3614 | 0.3614 | OK |
| ⌈N(10⁻⁶) from ρ(J)⌉ vs observed | 14 | 13.6 → 14 | OK |

The geometric mean of the per-service evidence factors around the cycle is
(0.4 · 0.7 · 0.8)^{1/3} = 0.6073, computed rather than assumed. N(10⁻⁶) from the
0.476 bound is 18.6 → 19, so the bound predicts 19 iterations and the local rate
predicts the 14 actually observed.

## What this closes and what it changes

- **Closes Fix 8c.** The corrected equations reproduce the reference
  implementation's asserted fixed point exactly, which the printed equations did
  not (they gave (0.7706, 0.6095, 0.6316) in 19 iterations).
- **Confirms Theorem 1 as restated.** ρ = δ·max(1−H)·W ≤ δ; the W = 1 boundary
  case does not arise. The withdrawn Fix 8a text is not written into the paper.
- **Changes the worked example's narrative.** Under the corrected operator the
  global and local bounds coincide at 0.476 on this example, because a uniform
  cycle has ρ(W̃) = W. The example no longer demonstrates "local bound much
  tighter than global"; its value is that ρ(J) = 0.3614 predicts the observed 14
  iterations, which the former text could not. §4.5 is written that way.
