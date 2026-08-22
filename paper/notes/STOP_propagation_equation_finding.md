# STOP — the manuscript's propagation equations are not the implemented algorithm

Raised 2026-08-22 during Fix 8c. Blocking. Execution of the ratified fix
sequence is **halted at item 10**; items 1–9 were not started, so no draft file
has been modified. Nothing has been absorbed into any draft.

---

## 1. The trigger

Fix 8c called for a fresh-script re-derivation of §4.5's worked example, with a
STOP on any digit disagreement. Script: `paper/notes/fix8c_rederive.py`.
Implemented strictly from equations (2) and (4) as printed in
`section4_fcp_algorithm.md`.

| quantity | §4.5 asserts | printed eqs (2)+(4) give |
|---|---|---|
| C\*(A) | 0.7255 | 0.7706 |
| C\*(B) | 0.5271 | 0.6095 |
| C\*(C) | 0.5453 | 0.6316 |
| iterations to ε = 10⁻⁶ | 14 | 19 |
| observed rate | ≈ 0.43 | 0.511 |

Every digit disagrees. The §4.5 numbers are not recoverable from the §4.4
equations by any rounding, tie, or convention choice.

## 2. What the implementation actually computes

`fuzzy-rca-engine/src/test/java/com/foda/rca/propagation/WorkedExampleTest.java`
(which is the unit test §4.5 cites as asserting C\* to 10 decimals) and its
Python port `evaluation/methods/foda_fcp.py::_propagate_iterative` both compute:

```
comp = ∏_{t ∈ callees(s)} (1 − C_prev(t) · w(s,t) · δ)
p    = 1 − comp
C(s) = clamp_[0,1]( 1 − (1 − H(s)) · (1 − p) )
```

Java, verbatim:

```java
double effectiveW = e.getWeight() * delta_d;
complementProduct *= (1.0 - ct * effectiveW);
double p  = 1.0 - complementProduct;
double hs = H.get(s);
double cs = 1.0 - (1.0 - hs) * (1.0 - p);
```

Two structural differences from the paper:

1. **δ is a per-edge attenuator inside the Noisy-OR product**, not a
   convex-combination damping coefficient. Printed (2) has no δ at all.
2. **There is no `(1 − δ)·C_prev(s)` term.** The local evidence `H(s)` is
   re-applied as a constant at every iteration (Java reads `H.get(s)`, not the
   previous iterate).

Re-running the sweep with this form reproduces §4.5 exactly:

```
docstring/source form: C = 1-(1-H)*prod(1-w*C*d)   iters=14  C*=(0.7255, 0.5271, 0.5453)  MATCH=True
```

Fixed point to 10 dp: `0.7254554565, 0.5271243564, 0.5453167505`. Script:
`paper/notes/fix8c_variants.py`.

The Python adapter's own module docstring states the correct form and has all
along:

> P(s) = 1 − ∏_{t ∈ callees(s)} (1 − C(t) · w(s,t) · δ)
> C(s) = 1 − (1 − H(s)) · (1 − P(s))

So the divergence is in the manuscript's transcription, not in the code.

## 3. What this invalidates

**Equation (2)** — omits δ from the edge weight.

**Equation (3)** (the DAG pass) — as printed it contains **no H term whatsoever**:
`C_{k+1}(s) = (1−δ)C_k(s) + δ[1 − ∏(1 − w·C_k(u))]`. Its only fixed point on the
worked example's cycle is the zero vector, and on a DAG every leaf goes to 0.
§4.4's claim that "*both formulations converge to the same fixed point on DAGs*"
is false for the printed equations (it is true for the implementation, where
both paths run the same formula under different sweep orders).

**Equation (4)** — as above.

**Theorem 1, and with it the entire Fix 8a specification.** For the implemented
operator T(C)(s) = 1 − (1−H(s))·∏_t(1 − δ·w(s,t)·C(t)):

```
|∂T(s)/∂C(t)| = (1−H(s))·δ·w(s,t)·∏_{u≠t}(1 − δ w C_u)  ≤  (1−H(s))·δ·w(s,t)
⟹  ‖T(C) − T(C′)‖_∞  ≤  δ · max_s(1 − H(s)) · W · ‖C − C′‖_∞
```

So ρ = δ·max_s(1−H(s))·W. At the practical default W = 1, and even in the worst
case H ≡ 0, **ρ ≤ δ = 0.85 < 1: T is a strict contraction.**

> **The W = 1 boundary case does not exist.** It is an artifact of the
> mis-transcribed equation. The ratified Fix 8a text — "*contraction iff δ>0 AND
> W<1; at W=1 the operator is non-expansive … with the damping-only argument for
> the H=0-full-budget residual (common: 25–37% of cases)*" — is a repair to a
> theorem about an operator the method does not use, and **must not be written
> into the paper**. Writing it would put a false limitation on the record and
> would attach a spurious 25–37 % caveat to a result that has none.

The real boundary case is **δ = 1**, where ρ ≤ 1 and T is only non-expansive.
The Python source already documents exactly this and nothing else:

> *"Banach convergence is guaranteed for ``δ < 1``; for ``δ == 1`` the iteration
> may not converge, in which case we return the last iterate after ``max_iter``
> rounds."*

This also matters for §5.9: δ = 1.0 is a swept configuration, so the one setting
in the sweep that carries no convergence guarantee is currently undisclosed.

**Theorem 2.** The Jacobian is stated as
`J_st = (1−δ)·𝟙[s=t] + δ·(1−H(s))·∂P/∂C(t)`. The implemented operator has **no
`(1−δ)𝟙[s=t]` diagonal term**; it is
`J_st = (1−H(s))·δ·w(s,t)·∏_{u≠t}(1 − δ w C_u)`, giving
`ρ_loc ≤ δ · max_s(1−H(s)) · ρ(W̃)`.

On the worked example: corrected bound = 0.85·0.8·0.7 = **0.476**; true ρ(J) at
the fixed point = **0.3614**; the manuscript's 0.626 is derived from the wrong
operator. N(10⁻⁶) from ρ(J) = 13.6 → **14 iterations**, which is exactly the
observed count — the corrected theory predicts the observation the current text
cannot.

**The Corollary** — already flagged as MF-5 for deriving a finite bound from a
divergent formula. Under the corrected operator the whole construction is
replaced: N(ε) = log ε / log(δ·max(1−H)·W) = 18.6 for the worked example, with
the local bound giving 13.6.

**§5.9's mechanism sentence** — "*The propagation update is C ← (1 − δ)·C +
δ·NoisyOR, so lower δ means heavier damping and less propagation influence*"
describes the wrong update. The *direction* survives (δ scales edge weights, so
δ → 0 still collapses to local-Mamdani-only ranking, and δ = 0.001 still
approximates it), but the stated mechanism does not.

## 4. What survives

- **All §5 empirical results.** They were produced by the code, not by the
  printed equations. AC@1, SG, SC, EC, ECE, the δ sweep, the refinement — none
  are touched.
- **§5.6.1's saturation mechanism.** The implemented form is still one minus a
  product of complements over active neighbours, so it still saturates on dense
  graphs. The argument is unaffected.
- **§5.9's dominance conclusion**, and MF-1/MF-2/MF-3 as ratified.
- **§3 in full.** No propagation equations there.
- The worked example's *narrative* — 14 iterations, fast convergence, local
  bound much tighter than global — is correct and becomes **more** defensible,
  since the corrected local bound tracks the observed rate closely.

## 5. Resolved in passing (Fix 8d, marker 14)

The confidence formula is now extractable verbatim
(`evaluation/methods/foda_fcp.py:1008–1014`):

```python
head      = ranked[: self.top_k]          # top_k default 3
head_sum  = sum(c for _, c in head)
top1_C    = head[0][1] if head else 0.0
confidence_value = float(np.clip(top1_C / head_sum, 0.0, 1.0)) if head_sum > 0.0 else 0.0
```

i.e. **confidence = top-1 C divided by the sum of C over the reported top-k**,
the relative concentration of confidence mass on the top-1 service — clamped to
[0,1], zero when the head sums to zero. Note the adapter docstring records this
as an adapter-level choice: *"the Java reference reports the absolute
`finalConfidence` of the top-1 RankedCause; we normalize to [0,1] for
cross-method comparability."* That divergence belongs in §5.3's deviation list
as well as §4.6.

**Marker 7 (correlation-graph lag window and threshold) is NOT yet resolved** —
the docstring names the method ("lagged Pearson correlation between services'
dominant-anomaly features") but I have not located the numeric parameters. Needs
a targeted read of the graph-construction function before §4.1's
`[AUTHOR-VERIFY]` can be closed.

## 6. Decisions required before I resume

1. **Which equation is canonical** — the source, or the paper? I have assumed
   the source is authoritative and the paper mis-transcribes it, because the
   source produced every number in §5 and the adapter docstring has always
   matched it. Confirm, because the alternative reading (the paper states the
   intended algorithm and the code implements something else) would be a
   correctness finding about the method rather than a drafting one, and would
   reach much further than §4.
2. **Fix 8a is withdrawn, not amended?** Confirm the ratified Fix 8a text is
   struck rather than edited, and that Theorem 1 is restated for the actual
   operator with δ = 1 as the sole boundary case.
3. **Does δ = 1's lack of a convergence guarantee need disclosure in §5.9**,
   given it is a swept configuration? My reading is yes, one clause.
4. **Independent re-derivation.** Theorem 2 is on the AUTHOR-ONLY list for
   independent re-derivation before submission. That item now covers a theorem
   that does not yet exist in correct form; it should be re-scoped to the
   corrected statement.

Until 1 and 2 are answered I am not editing §4, and items 1–9 of the fix
sequence are held rather than started — several of them (S7's canonical ceiling
phrasing, MF-6's §5.9 sentence) sit adjacent to text this finding may move.
