# Execution brief — FODA-FCP method paper, post-STOP fix round

You are executing a ratified fix sequence on a journal manuscript. Everything you
need is in this brief plus the repository; do not assume access to any prior
conversation. A reviewer will re-check every item against this brief afterwards.

**Repo root:** `~/IdeaProjects/foda-fuzzy-ontology-diagnostics/`
**Drafts:** `~/research/papers/draft/section{3,4,5}_*.md`
**Notes:** `<repo>/paper/notes/`
**Tracker:** `<repo>/paper/notes/coldread_v1_fixes.md`
**Source finding:** `<repo>/paper/notes/STOP_propagation_equation_finding.md` — read first.
**Reviewer findings:** `<repo>/paper/notes/coldread_findings_v2_partial.md` — read second.

---

## 0. Standing rules — these bind every step

1. **Tracker equals disk.** After each numbered task, update
   `coldread_v1_fixes.md` so its stated status matches what is actually on disk.
   Never mark an item complete before the edit exists in the file.
2. **File evidence per completion claim.** Every "done" must name the file path
   and what changed in it. "Applied" without a path is not a completion.
3. **Durable files, not chat.** Every verification, re-derivation, extraction and
   decision goes into a file under `paper/notes/`. Nothing important lives only
   in your output.
4. **Verified, not asserted.** Every claim about code or data is checked against
   code or data before it enters a draft. This project has already caught a
   scoring-convention bug, a mislabelled membership channel, a false tiebreak
   description, a false ontology-provenance claim, and — most recently — a
   central equation that did not match its implementation. Assume the next
   routine check will also bite.
5. **STOP and report immediately, before further work, if any of:**
   - a re-derivation disagrees with an expected value in any digit;
   - any number in §5 moves;
   - anything contradicts the locked canonical set in §0.1 below;
   - a source extraction contradicts what a draft currently says;
   - you cannot complete an item without inventing a value.
   Do not absorb a surprise into the draft. Write the finding to
   `paper/notes/` and stop.
6. **No code changes** outside an explicit authorisation. This round edits
   prose, not the harness. Reading source is expected; modifying it is not.
7. **Commits:** plain messages under the author's identity. No AI-attribution
   trailers.

### 0.1 Locked canonical numbers — if any of these move, STOP

| Quantity (FODA-FCP) | RE1-OB (12 svc) | RE1-SS (15 svc) | RE1-TT (64 svc) |
|---|---|---|---|
| AC@1 (headline, δ = 0.85) | 0.400 | 0.160 | 0.008 |
| ECE | 0.119 | 0.051 | 0.243 |
| SG (crisp) | 1.000 | 1.000 | 1.000 |
| SG (H-weighted) | 0.744 | 0.632 | 0.736 |
| SC | 0.266 | 0.158 | 0.086 |
| EC | 0.824 | 0.749 | 0.789 |
| Chance baseline | 0.083 | 0.067 | 0.016 |

Baselines (unchanged across all reruns): DejaVu 0.696/0.848/0.744; MonitorRank
0.632/0.656/0.480; CausalRCA 0.624/0.656/0.472; MicroRCA 0.624/0.648/0.456;
BARO 0.536/0.584/0.392; yRCA 0.328/0.256/0.104.

Silence taxonomy (three terms, do not collapse): **system silence** 31/46/31;
**head silence** 32/46/33; **evidence displacement** = head-silent but not
system-silent, 3 cases total (OB 1, TT 2). "No-Recommendation" 35/48/48 is a
third, weaker condition and is **not** silence.

§5.7: ceiling 0.152 (19/125 = 1 already-correct + 18 strict rescues); measured
0.144 on TT (17 gained, 0 lost); 0/0 on OB and SS.

§5.9 δ→0 limit: 0.400→0.560 (1.4×), 0.160→0.408 (2.6×), 0.008→0.464 (58×);
TT SC 0.086→0.372, TT EC 0.789→0.835; SG invariant at 1.000.

§5.8 link arithmetic: 520 links on OB → 270 mitigation + 85 unmapped excluded =
165 scored, 84 endorsed (49 at 1.0, 35 at 0.5); 84/165 = 0.509 endorsement rate;
0.403 pooled strength-weighted mean; **0.266 the reported per-case mean**. All
three must stay distinguished and never be conflated.

---

## Task 1 (R1) — Rewrite Eqs. (2)–(4) to the implemented operator

**File:** `~/research/papers/draft/section4_fcp_algorithm.md`, §4.4.

The printed equations are a mis-transcription. The source is canonical.

**Ground truth — `fuzzy-rca-engine/src/test/java/com/foda/rca/propagation/WorkedExampleTest.java`:**

```java
double effectiveW = e.getWeight() * delta_d;
complementProduct *= (1.0 - ct * effectiveW);
double p  = 1.0 - complementProduct;
double hs = H.get(s);
double cs = 1.0 - (1.0 - hs) * (1.0 - p);
if (cs < 0.0) cs = 0.0;
if (cs > 1.0) cs = 1.0;
```

**Python port — `evaluation/methods/foda_fcp.py::_propagate_iterative`:**

```python
H = {s: hypotheses[s].local_confidence if s in hypotheses else 0.0 for s in services}
C = dict(H)
for _ in range(max_iter):
    C_next = {}
    for s in services:
        callees = out.get(s, [])
        comp = 1.0
        for (t, w) in callees:
            ct = C.get(t, 0.0)
            comp *= 1.0 - ct * w * delta
        p = 1.0 - comp
        C_next[s] = max(0.0, min(1.0, 1.0 - (1.0 - H[s]) * (1.0 - p)))
    if max(abs(C_next[s] - C[s]) for s in services) < epsilon:
        C = C_next; break
    C = C_next
```

**DAG branch — `evaluation/methods/foda_fcp.py::_propagate_damped`:** the same
formula applied once per service in reverse-topological order, with
`if not callees: continue` (so a service with no callees keeps `C(s) = H(s)`).

**Two structural facts the new text must carry:**

- δ is a **per-edge attenuator inside the Noisy-OR product**. It multiplies each
  edge's transmitted confidence. It is **not** a convex mixing weight between
  iterates.
- There is **no `(1 − δ)·C_prev(s)` term**. `H(s)` is re-applied as a constant
  anchor at every iteration (the Java reads `H.get(s)`, not the previous iterate).

**Replacement equations** (typeset in the manuscript's existing style):

```
(2)  P(s) = 1 − ∏_{t ∈ callees(s)} (1 − δ · w(s,t) · C(t))

(3)  DAG pass (exact, one reverse-topological sweep):
     C(s) ← clamp_[0,1]( 1 − (1 − H(s)) · (1 − P(s)) )
     with P(s) from (2) over already-updated callees; a service with no
     callees retains C(s) = H(s).

(4)  Jacobi iteration (cyclic graphs):
     C^(k)(s) = clamp_[0,1]( 1 − (1 − H(s)) · ∏_t (1 − δ · w(s,t) · C^(k−1)(t)) )
              = clamp_[0,1]( 1 − (1 − H(s)) · (1 − P^(k)(s)) ),  P^(k) from C^(k−1)
     C^(0)(v) = H(v);  terminate on ‖C^(k) − C^(k−1)‖_∞ ≤ ε or MAX_ITER.
     Defaults: δ = 0.85, ε = 10⁻⁶, MAX_ITER = 100.
```

**Naming ruling:** keep the released parameter name "damping factor δ" — that is
what the code and the artifact call it — but correct the *semantics* everywhere:
it attenuates each edge's transmitted confidence; it does not blend iterates.

**Also fix in §4.4:** the sentence "*Both formulations converge to the same fixed
point on DAGs*" is true of the implementation (same formula, different sweep
order) and was false of the printed equations. Restate it so it is anchored to
the shared formula rather than to two different-looking updates.

---

## Task 2 (R2/R3) — Theorems 1 and 2 for the actual operator

**File:** `~/research/papers/draft/section4_fcp_algorithm.md`, §4.5.

Delete the existing `[NEW-MATH: the W = 1 boundary case …]` bracket entirely. Do
**not** write the previously-ratified Fix 8a text — it repairs a theorem about an
operator the method does not use, and the W = 1 boundary case it addresses does
not exist. This is withdrawn, not amended.

### Theorem 1 (Global contraction) — restated

Let T be the update (4). For δ ∈ (0,1] and Σ_t w(s,t) ≤ W ≤ 1 for all s:

```
‖T(C) − T(C′)‖_∞  ≤  ρ · ‖C − C′‖_∞,     ρ = δ · max_s (1 − H(s)) · W  ≤  δ
```

Hence **for every δ < 1, T is a strict contraction on [0,1]^V regardless of W and
of H**, with a unique fixed point C\* to which the Jacobi iteration converges from
any initialization. The only degenerate case is δ = 1 with H ≡ 0 and W = 1, where
ρ = 1 and T is merely non-expansive.

*Proof.* ∂P(s)/∂C(t) = δ·w(s,t)·∏_{u≠t}(1 − δ·w(s,u)·C(u)) ∈ [0, δ·w(s,t)], since
every factor lies in [0,1]. T(s) = 1 − (1−H(s))(1−P(s)) gives
∂T(s)/∂C(t) = (1−H(s))·∂P(s)/∂C(t) ≤ (1−H(s))·δ·w(s,t). Summing over t and
applying the mean-value theorem yields the stated constant. ∎

**Write the W = 1 case as the ordinary case, not an exception.** The full-weight
budget is the practical default and is fully covered.

### Corollary (Iteration bound) — recomputed

N(ε) = ⌈log ε / log ρ⌉. Worst case at δ = 0.85 (H ≡ 0, W = 1): ρ = 0.85,
N(10⁻⁶) = 85. On the worked example below, ρ = 0.476 → 19, and the local bound
0.3614 → 14, matching the observed count.

**Do not re-attribute the old "≈ 30 iterations".** That figure came from a bound
that no longer exists; recompute and state which bound each number comes from.

### Theorem 2 (Local spectral rate) — corrected Jacobian

At the fixed point C\*, with **no `(1−δ)𝟙[s=t]` diagonal term**:

```
J_st = (1 − H(s)) · δ · w(s,t) · ∏_{u≠t} (1 − δ · w(s,u) · C*(u))  ≥ 0
ρ_loc = ρ(J)  ≤  δ · max_s (1 − H(s)) · ρ(W̃),   W̃_st = w(s,t)
```

**Name the four Perron–Frobenius steps explicitly** (this is Fix 8b):

1. **Entrywise non-negativity.** Every factor of J_st lies in [0,1] and
   w(s,t) ≥ 0, so J ≥ 0 entrywise; W̃ ≥ 0 by construction.
2. **Entrywise domination.** J ≤ δ · max_s(1−H(s)) · W̃ entrywise, since the
   trailing product is ≤ 1.
3. **Monotonicity of the spectral radius on non-negative matrices.**
   0 ≤ A ≤ B entrywise ⟹ ρ(A) ≤ ρ(B).
4. **Positive homogeneity.** ρ(cB) = c·ρ(B) for c ≥ 0.

Steps 1–4 compose to the bound. Because ρ(W̃) ≤ W (the spectral radius of a
non-negative matrix is at most its maximum row sum), the local bound is never
worse than the global one, and is strictly tighter whenever ρ(W̃) < W.

### Worked example — corrected

3-cycle A→B→C→A, all w = 0.7, H = (0.6, 0.3, 0.2), δ = 0.85, ε = 10⁻⁶.

| quantity | value |
|---|---|
| C\* | (0.7255, 0.5271, 0.5453) — 10 dp: 0.7254554565, 0.5271243564, 0.5453167505 |
| iterations to ε = 10⁻⁶ | 14 |
| Theorem 1 global bound | δ·max(1−H)·W = 0.85 · 0.8 · 0.7 = **0.476** |
| Theorem 2 local bound | δ·max(1−H)·ρ(W̃) = 0.85 · 0.8 · 0.7 = **0.476** |
| true ρ(J) | **0.3614** |
| N(10⁻⁶) from ρ(J) | 13.6 → **14**, matching the observed count |

**Narrative correction you must make, not skip.** The old text claimed the local
bound is much tighter than the global one on this example. Under the corrected
operator **the two coincide at 0.476**, because ρ(W̃) = W = 0.7 for a uniform
cycle. The remaining gap to the true 0.3614 is the difference between the
worst-case factor max_s(1−H(s)) = 0.8 and the geometric mean of the per-service
factors along the cycle, (0.4·0.7·0.8)^{1/3} = 0.6073 — check:
0.85 · 0.7 · 0.6073 = 0.3614. **Verify this identity numerically before writing
it.** Write the example so that Theorem 2's value is that it *predicts the
observed 14 iterations*, which the old text could not.

Keep the `[NEW-MATH]` marker on Theorem 2 — it still requires independent
author re-derivation before submission — but re-scope the marker text to the
corrected statement.

---

## Task 3 — Fix 8c closure

Write a **fresh script** (do not reuse `paper/notes/fix8c_rederive.py`, which
implements the old printed equations and is retained only as evidence of the
disagreement). Reference implementation of the variant sweep already exists at
`paper/notes/fix8c_variants.py`.

New script: `paper/notes/fix8c_rederive_corrected.py`. It must, from the
**corrected** equations (2)–(4) alone:

- reproduce C\* = (0.7255, 0.5271, 0.5453) to 4 dp and the 10-dp values above;
- reproduce 14 iterations at ε = 10⁻⁶;
- compute ρ(J) = 0.3614 and both bounds = 0.476;
- verify the geometric-mean identity in Task 2.

**STOP on any digit disagreement.** Record the run output in
`paper/notes/fix8c_closure.md` with the script path and the comparison table.

---

## Task 4 (R4) — Disclosure and errata

1. **`<repo>/DEVIATIONS.md`** — add an entry recording the mis-transcription:
   what the manuscript printed, what the implementation computes, how it was
   found (Fix 8c re-derivation, 2026-08-22), which artifacts were affected
   (Eqs. 2–4, Theorems 1–2, the Corollary, the §4.5 worked example, §5.9's
   mechanism sentence), and the ruling that the source is canonical. Take the
   full timeline from `paper/notes/STOP_propagation_equation_finding.md`.
2. **`<repo>/paper/notes/aict_errata.md`** — create as a placeholder. The
   preliminary AICT 2026 conference version may carry the same equations. The
   author must check the AICT manuscript before this can be filled. Structure
   it as: claim as printed in AICT / corrected form / whether an erratum or a
   camera-ready correction is required / decision pending author check. Mark it
   **AUTHOR-ONLY — pending**. Do not guess what AICT printed.
3. **Paper 6 ledger** (`paper/notes/paper6_q2_corrections.md`) — assess whether
   Paper 6 restates these equations. If it does, add a correction item. If it
   does not, record explicitly that you checked and it does not.

---

## Task 5 (R5) — Language sweep

Grep §4 and §5 for convex-mixing phrasing and correct the semantics. Known hits:

- **§5.9**: "*The propagation update is C ← (1 − δ)·C + δ·NoisyOR, so lower δ
  means heavier damping and less propagation influence*" — wrong update. The
  direction survives (δ scales edge weights, so δ → 0 still collapses to
  local-Mamdani-only ranking and δ = 0.001 still approximates it); the mechanism
  does not. Rewrite.
- **§4 framing note** — check its description of the propagation step.
- **§3.5 table**, "Propagation | **Graded.** Damped Noisy-OR composes [0,1]
  confidences over weighted edges" — verify this is still accurate (it probably
  is) and correct if not.

Search terms: `(1 − δ)`, `(1-δ)`, `convex`, `blend`, `mix`, `damping`, `damped`.

**Add to §5.9 the δ = 1.0 disclosure sentence** (R2): δ = 1.0 is a swept
configuration, and it is the one setting with no convergence guarantee —
Theorem 1 gives only non-expansiveness there, and convergence at δ = 1.0 is
**empirical**. The source already documents this:

> `evaluation/methods/foda_fcp.py::_propagate_iterative` docstring: *"Banach
> convergence is guaranteed for `δ < 1`; for `δ == 1` the iteration may not
> converge, in which case we return the last iterate after `max_iter` rounds."*

One clause, in the sweep's setup paragraph.

**Verify — do not assume — that §5.7's ceiling and impossibility logic is
untouched.** Expected outcome: untouched, because §5.7 rests on the pessimistic
tie convention and on within-block ordering being unable to move AC@1, neither of
which involves the propagation update's form. Confirm by re-reading the argument
and write the confirmation (or the breakage) to
`paper/notes/r5_sweep_verification.md`.

---

## Task 6 (R6) — Marker 14 and marker 7

Both are now resolved from source. Insert the text; do not re-derive.

### Marker 14 — confidence formula → §4.6, and §5.3 deviations

`evaluation/methods/foda_fcp.py:1008–1014`:

```python
head      = ranked[: self.top_k]          # top_k default 3
head_sum  = sum(c for _, c in head)
top1_C    = head[0][1] if head else 0.0
confidence_value = float(np.clip(top1_C / head_sum, 0.0, 1.0)) if head_sum > 0.0 else 0.0
```

So: **reported confidence = C of the top-1 service divided by the sum of C over
the reported top-k**, clamped to [0,1], zero when the head sums to zero. It is
the relative concentration of confidence mass on the top-1 candidate.

The adapter docstring records this as an adapter-level choice:

> *"Confidence is computed as `top1_C / sum(C over top-K)` — the relative
> concentration of fuzzy contribution mass on the top-1 service. Documented as
> the FODA-FCP adapter's choice (the Java reference reports the absolute
> `finalConfidence` of the top-1 RankedCause; we normalize to `[0, 1]` for
> cross-method comparability with the harness's per-method confidence column)."*

That divergence from the Java reference belongs in **§5.3's documented-deviations
list as well as §4.6**. Remove the `[AUTHOR-VERIFY]` on the §4.6 confidence
formula. Note for §5.10: this is the quantity the ECE analysis measures.

### Marker 7 — correlation-graph parameters → §4.1

`evaluation/methods/foda_fcp.py::_infer_topology`, with constructor defaults
`topology_threshold: float = 0.5`, `lag: int = 1`, `top_k: int = 3`,
`max_iterations: int = 100`:

- Directed edge **u → v** with weight **|lagged_corr(u, v)|**, admitted when
  **|lagged_corr| ≥ threshold = 0.5** and **u leads v by lag = 1 sample** in the
  post-onset window.
- Direction disambiguation: the edge is kept only if `w_uv ≥ w_vu` (`if lag > 0
  and w_uv < w_vu: continue`), so the stronger lead direction wins.
- Self-loops excluded (`if u == v: continue`).
- Per-service representative signal = the **highest-|z| canonical feature** among
  `cpu, mem, latency, error, traffic`; on a no-deviation tie it falls back to the
  first present among `latency, traffic, cpu, mem, error`.
- A service needs more than `lag + 1` post-onset samples to contribute a signal.
- Docstring: *"Mirrors `evaluation.methods.yrca._infer_topology` so the three
  topology-inference adapters (MicroRCA, yRCA, FODA-FCP) share an
  edge-construction convention."* — this substantiates §4.1's existing claim that
  the construction follows the same convention as MicroRCA and yRCA.

Remove the `[AUTHOR-VERIFY]` on §4.1's correlation-graph parameters.

---

## Task 7 — Held items, in this order

Full statements are in `paper/notes/coldread_findings_v2_partial.md`. Summary:

**MF-8 / S2 — §5.5 vs §5.10 contradiction.** §5.5 currently asserts "*the claim
that the two axes are independent*" while §5.10 says they are not independent
within a method. Narrow §5.5 to **across methods** and add a forward pointer to
§5.10. Independence may appear **only** in decomposed form anywhere in the paper:
independent *across* methods, positively coupled *within* an explanation-producing
method.

**S1 — self-contained metric definitions in §5.4.** Replace the literal
placeholder `[COMPRESSED DEFINITIONS — ~1 p, carried from the framework
specification.]` with ~1 page defining SemanticGroundedness, SemanticCoherence,
ExplanationCompleteness and calibration/ECE self-containedly. The framework paper
is unpublished and cannot be leaned on. Use the locked silence taxonomy (§0.1)
and keep SG_fuzzy/SC_fuzzy as reported alongside, never instead of, crisp forms.

**MF-1 / MF-2 / MF-3 — §5.9 dominance rephrasing.**
- MF-1: "*monotonically at every step from δ = 0.85 downward on all three
  systems*" is false. RE1-OB rises to 0.560 at δ = 0.1 then **falls** to 0.552 at
  δ = 0.001 (interior optimum). RE1-TT has a flat step (0.024 at both δ = 0.75
  and 0.65); RE1-SS a plateau (0.408 at δ ≤ 0.2). Replace monotonicity framing
  with **dominance framing**: the δ ≤ 0.2 region dominates the shipped setting on
  every axis on all three systems — verified: OB 0.544/0.396/0.835 vs
  0.400/0.266/0.824; SS 0.408/0.296/0.755 vs 0.160/0.158/0.749; TT
  0.216/0.212/0.824 vs 0.008/0.086/0.789.
- MF-2: the explanation-axis basin is **two-sided**, roughly δ ∈ [0.5, 0.85], not
  only above the shipped setting. Stepping down from δ = 0.85, TT SC goes
  0.086 → 0.074 (0.75) → 0.086 (0.65) → **0.084** (0.5) → 0.106 (0.4) → … → 0.372;
  TT EC goes 0.789 → 0.768 → 0.763 → **0.784** (0.5) → 0.800 → … → 0.835. Both dip
  **below** the shipped value at δ = 0.5. So "coherence rises with the same
  damping that raises accuracy" and "completeness rises or holds" are both false
  without the basin qualification. Same correction in §4's framing note, which
  says the propagation costs accuracy and coherence over the whole range downward.
- MF-3: the minima are not both at δ ≈ 0.7–0.75. SC's minimum is 0.074 at
  δ = 0.75; **EC's is 0.763 at δ = 0.65**. Widen to ≈ 0.65–0.75 or state the two
  separately.
- Data source: `paper/notes/delta_tradeoff_2026-08-11.md`.

**MF-6 — two dangling forward references.** §5.4 says "*§5.9 shows it is the
endpoint of the same propagation behaviour*" (evidence displacement) and refers to
"*the system-silent cases in the damping sweep of §5.9*". §5.9 currently mentions
neither. Add to §5.9: one sentence on evidence displacement, exemplar
`re1-ob_cartservice_mem_2` (the only service with rule support, H = 0.290, is the
ground truth; the reported top-3 all have H = 0), plus the silence mention the
second pointer needs. Evidence displacement is permitted at most one further
sentence in §1's problem framing and nowhere else.

**MF-7 — §5.5 cites "§6′.1", which will not exist.** §6 is NO-GO for v1. Remove
or redirect.

**S4 — §3.5 gains one forward clause** pointing to §5.9.

**S7 — one canonical phrasing of the ceiling derivation** throughout: 19/125 =
0.152 = 1 already-correct + 18 strict rescues; measured 0.144 = 18/125 = 1 + 17
gained; one ceiling case unrealised (`ts-auth-service_cpu_2`). Use the same
wording everywhere it appears.

**SF-1 — scope the ceiling sentence.** "*Any measured value above 0.152 would
indicate an implementation error rather than a better method*" is unscoped, and
the released sweep contains `ac1_refined` = 0.192 (δ = 0.95) and 0.208 (δ = 1.00).
Rewrite as: at δ = 0.85; higher-δ refined values in Appendix II exceed it because
the failure decomposition differs there.

**SF-2 — RESOLVED, apply directly.** I parsed `ontology/DiagnosticKB.owl`:
22 propagation individuals, **0 self-pairs** (no individual has
propagationSource == propagationTarget), strengths 12 × 1.0 + 10 × 0.5, 8 distinct
prototypes. So self-propagation is **not** represented. §3.4's "*The remaining 42
of 64 ordered prototype pairs carry no individual*" uses the wrong denominator:
with self-pairs excluded there are 8 × 7 = **56** ordered pairs and the remainder
is **34**. Change 42/64 → **34/56** and state that self-propagation is not
represented. Re-verify the parse before editing.

**SF-3 — resolve the 4 unaccounted cases.** §5.7 says the ground truth lies inside
the saturated block in 30 cases, is the strict unique maximum in 18, and merely
ties in a further 8. 18 + 8 = 26, leaving 4 unexplained. Expected: ground truth
in block, not the H-maximum, not H-tied — i.e. some other service in the block has
strictly higher local confidence. **Verify against the diagnostics, do not
assume.** No existing CSV under `results/` carries this breakdown, so regenerate
it from the harness instrumentation described in §5.6, write the per-case evidence
to `paper/notes/sf3_block_decomposition.md`, then add the missing category to
§5.7's sentence. If the count does not come to 4, **STOP** — that would move a §5
number.

**SF-4 — no-Recommendation count.** The measured OB value is **35**, against
Paper 6's published 31; Paper 6 correction #6 is **PENDING investigation**. If the
number surfaces in §5, it must be 35 and the discrepancy must be left visibly
open — never presented as resolved. If it does not surface, record explicitly in
the tracker that correction #6 has no anchor in this manuscript's text.

**Remaining marker fills:** adapter table (marker 18) from `DEVIATIONS.md`
per-method sections; Tables 1a–c (markers 20–22) typeset from the committed CSVs
with bootstrap CIs from `paper/artifacts/bootstrap_ac1_cis.md`; TT wall-clock
(marker 16) from harness logs; competency questions (marker 2) and
CASCADING_FAILURE surrogate (marker 3), both repo-resolvable. Marker 8 (SLO
sources) stays **AUTHOR-ONLY** — the provenance of those thresholds is not in the
repository; do not invent it.

---

## Task 8 — Draft §1, §2, §7

Only after Tasks 1–7 are complete and the tracker reflects them.

### §1 — the contribution list is exactly these four, no additions, no omissions

1. The method with **grounded-by-construction explanations**.
2. The **predict-verify methodology**: mechanism decomposition → ceiling →
   intervention → measurement.
3. The **δ dose–response falsifying our own propagation layer**, with the δ→0
   result phrased **as a finding**, never as a co-primary configuration.
4. **Full artifact release** with commit-pinned provenance.

A fifth contribution, a missing one, or one whose wording drifts (e.g. (iii)
stated as a configuration rather than a finding) is a defect.

**Also required in §1:**
- The **AICT disclosure sentence**: a preliminary 6-page version is under review
  at IEEE AICT 2026 and this paper extends it — summarised from
  `~/research/papers/outline/aict_delta.md`. **Not cited** (Option C); upgrade to
  a proceedings citation only if accepted before submission.
- **No operator-relevance claims** in the title or abstract — §6 is NO-GO for v1,
  employer permission unconfirmed. Ship abstract **variant B (without §6)**.
- δ = 0.85 is the headline configuration everywhere including the abstract. The
  δ→0 result may appear in the abstract and §1 **as a finding** only.
- Independence, if mentioned, only in decomposed form (across-methods vs
  within-method).
- Evidence displacement: at most one sentence.
- Do not promise anything the TT AC@1 = 0.008 result will not support. TT is
  always presented as: *"0.008, below the 1/64 ≈ 0.016 chance baseline (95 % CI
  [0.000, 0.024])"* — CI shown because it straddles chance; the claim rides the
  point estimate.

### §2 — related work

Position against the six baselines (DejaVu, MonitorRank, CausalRCA, MicroRCA,
BARO, yRCA) and the explainable-RCA literature. The "empty middle" observation
from §5.5 — methods either commit to ontology grounding fully or not at all —
belongs here as motivation. Do not lean on the unpublished framework paper.

### §7 — conclusions and future work

Must actually admit what §5 discovered rather than burying it: TT below chance,
system silence as a rule-coverage gap, the propagation layer dominated on this
benchmark family, the provenance timing of the propagation table, and the
mis-transcription finding's consequence that the formal analysis was corrected
late. Future-work items in order: (1) principled held-out δ selection; (2)
rule-base coverage for the silence mechanism; (3) density-aware damping and
log-pool aggregation; (4) propagation-table extension and a
"not-endorsed vs contradicted" distinction; (5) fuzzy-OWL formalization;
(6) a dedicated `CascadingFailure` prototype.

---

## Deliverables

1. Edited `section3`, `section4`, `section5` drafts, plus new `section1`,
   `section2`, `section7` files in `~/research/papers/draft/`.
2. An assembled manuscript file, with the abstract, in the same directory.
3. `coldread_v1_fixes.md` updated so tracker state equals disk state, with a
   file-path evidence column for every completed item. Remove the BLOCKED header
   at the top only when the items it names are genuinely done.
4. New notes: `fix8c_rederive_corrected.py`, `fix8c_closure.md`,
   `r5_sweep_verification.md`, `sf3_block_decomposition.md`, `aict_errata.md`.
5. `DEVIATIONS.md` updated.
6. A short completion report naming, per task, the files changed and what
   changed in them.

Housekeeping: `paper/notes/_to_delete/coldread_v1_fixes.md.bak` is a stray backup
from the tracker edit and can be removed.

**A reviewer will now re-check every one of these against the MF/SF findings and
the R1–R6 rulings. Items marked complete without file evidence will be treated as
not done.**
