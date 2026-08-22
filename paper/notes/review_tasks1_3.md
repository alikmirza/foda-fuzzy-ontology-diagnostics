# Reviewer sign-off — Part 1, Tasks 1–3

Reviewed 2026-08-22 against `evaluation/methods/foda_fcp.py`,
`WorkedExampleTest.java`, and an independent re-derivation. **Verdict: PASS.**
Four corrections below, all local; none requires rework.

## Verified correct

- **§4.4 matches the implementation.** δ inside the product, no `(1−δ)·C_prev(s)`,
  `H(s)` as per-iteration anchor, clamp explicit, no-callees case retaining
  `C(s) = H(s)` — matches `if not callees: continue`.
- **Theorem 1's proof is sound.** ∂P(s)/∂C(t) = δ·w(s,t)·∏_{u≠t}(1−δ·w(s,u)·C(u))
  is the correct derivative; the bound by δ·w(s,t) follows since every factor is
  in [0,1]; the row sum δ·(1−H(s))·W and the sup-norm max are right. Noting the
  clamp is a non-expansive projection was not in the spec and is a good addition.
- **Theorem 2's four Perron–Frobenius steps are each valid and correctly ordered.**
  The absence of a diagonal term is right.
- **Every worked-example number reproduces:** C\* to 10 dp, 14 iterations,
  bounds 0.476, ρ(J) = 0.3614, and the geometric-mean identity
  0.85 · 0.7 · 0.6073 = 0.3614.
- **The DAG/Jacobi reconciliation is better than the original** — anchoring both
  branches to one shared formula differing only in sweep order is the honest
  statement, and it repairs a claim that was false of the printed equations.
- **The worked-example narrative correction was handled honestly** rather than
  papered over.

## Corrections

### C1 — Theorem 1's degenerate case is stated too narrowly (substantive)

Current: *"The sole degenerate case is δ = 1 combined with **H ≡ 0** and W = 1."*

ρ = δ·max_s(1−H(s))·W equals 1 when max_s(1−H(s)) = 1, i.e. when
**min_s H(s) = 0** — *at least one* service carries no local evidence, not all of
them. That is the ordinary situation, not a corner: system silence alone is
25–37 % of cases, and outside silence most cases still contain some service the
rule base does not fire on.

So at δ = 1.0 the operator is non-expansive in **essentially every run of the
§5.9 sweep**, not in a rare configuration. Replace "H ≡ 0" with "min_s H(s) = 0"
and say it is typical rather than exceptional. This strengthens the δ = 1
disclosure requirement in §5.9 rather than weakening it — worth one extra clause
there.

### C2 — the Corollary's N = 85 is off by one under its own ceiling

log(10⁻⁶)/log(0.85) = 85.008, so ⌈·⌉ = **86**. Check: 0.85⁸⁵ = 1.0007 × 10⁻⁶,
still above ε. Either write 86 or drop the ceiling and write "≈ 85". The other
two are correct: 18.61 → 19 and 13.58 → 14.

### C3 — Theorem 2's tightness condition reads backwards

Current: *"strictly tighter whenever ρ(W̃) < W — that is, whenever the weight is
distributed unevenly across the graph rather than concentrated along a single
cycle."*

For an irreducible non-negative matrix, ρ equals the maximum row sum **iff all
row sums are equal**. The uniform cycle has equal row sums, which is exactly why
the two bounds coincide there. So the condition is **unequal row sums**, and
"concentrated along a single cycle" names the case where the bounds *agree*, not
where they differ. Suggested: *"strictly tighter whenever the row sums are
unequal — a uniform cycle, where every service carries the same outgoing weight,
is precisely the case in which they coincide."*

### C4 — §4.5 forward-references a §5.9 sentence that does not exist yet

Current: *"convergence there is observed rather than guaranteed, and **§5.9 says
so**."* §5.9 line 193 still carries the convex-mixing sentence and no δ = 1
disclosure — Task 5 has not run. Not an error, but the claim is false until
Task 5 lands it. Same class as MF-6; track it so it does not survive to
submission.

## Tracker correction

`coldread_v1_fixes.md` line 82 lists **marker 7 (correlation-graph parameters) as
PENDING, needing "a targeted read of the graph-construction function."** It does
not — the full extraction is already in `CLAUDE_CODE_EXECUTION_PROMPT.md` Task 6
(R6): `_infer_topology`, `topology_threshold = 0.5`, `lag = 1`, edge u→v weighted
|lagged_corr(u,v)| admitted at ≥ threshold with u leading v (`w_uv ≥ w_vu`),
self-loops excluded, per-service signal = highest-|z| among
cpu/mem/latency/error/traffic with a documented no-deviation fallback, and the
docstring confirming the shared convention with MicroRCA and yRCA. Mark it
resolved and paste the text.

## Clearance

Tasks 1–3 are signed off subject to C1–C3 being applied. Proceed to Task 4.
