# §5.7 Reframing Proposal: order-level tiebreak → score-level refinement

**Status:** proposed 2026-08-10, **awaiting author ratification**. Affects D7
only; no other ruling changes.

## 1. What was ratified (D7, unchanged parts)

> §5.7 implements and measures **local-H tiebreaking only** — replace FCP's
> alphabetical tiebreaker with descending local Mamdani confidence H(s) over
> the saturated tie set — ablated on all three systems. Density-aware damping
> and log-pool aggregation move to Future Work as Paper-8 material. If the
> tiebreak fails to improve RE1-TT AC@1, report it honestly as a negative
> result with analysis. §5.7 targets mechanism (a) only; mechanism (b) is
> genuine method silence, not ranking pathology.

**Everything in that ruling stands except the mechanism of the intervention
itself.** Scope (mechanism (a) only), the deferral list, and the
honest-negative fallback are unchanged by this proposal.

## 2. Why the ratified intervention cannot work as written

Two facts, both established after D7 was issued:

**(i) The implementation already does local-H tiebreaking.** `_rank()` in
`evaluation/methods/foda_fcp.py` sorts by `(-C(s), -H(s), name)` — H before
name — and git history shows this ordering since the adapter's first commit,
i.e. it was already active in every published RE1-TT run. (Paper 6 §4.5's
description of a "deterministic alphabetical tiebreaker" is inaccurate and
needs correcting at its Q2 revision.) So the ratified change is a no-op
against the current code.

**(ii) Under the ratified pessimistic convention, order-level tiebreaking is
invisible to AC@1 by construction.** `_ground_truth_rank()` assigns the ground
truth **the worst rank in its score-tie block**. Any reordering *within* a
block — alphabetical, local-H, or anything else — leaves that rank unchanged.
Formally: if k services share the top score, the ground truth's rank is k
regardless of ordering, so AC@1 = 0 whenever k > 1.

The two facts compound: even under naive scoring the change is a no-op
(already implemented), and under the canonical convention no order-level rule
could ever move the metric.

## 3. Proposed replacement

Keep the intent (use local evidence to resolve saturated ambiguity) but move
the intervention from list order to the **score**:

> **Local-H score refinement.** Replace the ranking score C(s) with
> C′(s) = C(s) − ε · (1 − H(s)), with ε chosen smaller than the smallest
> non-zero gap between distinct C values, so that C′ preserves the ordering of
> all services with distinct C and breaks ties among services sharing a C
> value in favour of higher local Mamdani confidence. Because the tie is broken
> **at the score level**, the ground truth's pessimistic rank changes, and the
> effect is visible to AC@1.

This is a **method variant**, not a scoring change: it must be reported as
FODA-FCP + refinement alongside the as-shipped method, never substituted for
it. The ε choice becomes a §5.9 sensitivity item.

## 4. Measured headroom (from `paper/notes/tt_mechanism_split.md`)

Diagnostics re-run on all 125 RE1-TT cases at commit `d485957`:

| Quantity | Value |
|---|---|
| Mechanism (a) saturation failures | 87 |
| …with ground truth **inside** the saturated tie block | **30 of 87** |
| …of those, STRICT rescue (see §4b — this row superseded) | see §4b |
| Resulting AC@1 ceiling on RE1-TT | **see §4b — locked at 0.152** |
| Mechanism (b) silence failures | 31 — headroom **zero** (H = 0.000 for all 64 services; nothing to refine) |
| Residual failures | 6 — headroom zero (ground truth outside the block; propagation-topology errors) |

So the maximum achievable improvement is 0.008 → 0.152 (§4b), and it is bounded
entirely by mechanism (a). Anything above 0.152 would indicate a bug, not a
better method. Measured (as opposed to ceiling) gain is TBD — that is the
experiment §5.7 reports.

## 4b. STRICT ceiling recompute (ruling 2a) — result, 2026-08-10

Rescue now requires the ground truth to be the **strict unique H-maximum** of
its C-tie block; residual H-ties score pessimistically (no rescue).

| Quantity | LOOSE (previous) | **STRICT (canonical)** |
|---|---|---|
| Saturation failures with gt in block | 30 of 87 | 30 of 87 |
| …rescued | 26 | **18** |
| Lost to H-ties within the block | — | **8** |
| **RE1-TT ceiling AC@1** | superseded | **(1 + 18)/125 = 0.152** (the +1 is the single baseline-correct case, `re1-tt_ts-travel-service_disk_3`; disjoint from the 18) |

Two corrections to the earlier figure. First, the earlier "28" compared the
ground truth's H against the *tie-break winner's* H rather than against the
**maximum H over all other block members**; the correct loose count is 26.
Second, and more important, 8 of those 26 are H-ties in which the ground truth
merely equals the best H — under strict handling they are not rescued, leaving
**18**. The canonical ceiling is therefore **0.008 → 0.152**.

The strictness ruling also removed a false-positive class the loose criterion
admitted: counted over *all* failures rather than saturation only, the loose
criterion "rescued" 57 cases, of which 31 are the silence cases (every service
has H = 0.000, so gt_H ≥ max is vacuously true). Strict handling scores all 31
as unrescued, exactly as intended — mechanism (b) headroom stays zero.

## 4c. ε feasibility problem (new finding — needs a ruling)

The standing instruction defines ε globally per system as smaller than the
minimum non-zero C-gap. Measured on RE1-TT: **min non-zero gap = 1.0 × 10⁻¹²**
(median 2.0 × 10⁻¹²), and 31 of 125 cases have no distinct C values at all.

A global ε below 10⁻¹² sits at the numerical-noise floor of the propagation
itself, so the refinement's behaviour would depend on float rounding — not
defensible in a paper. **Recommended alternative (mathematically identical,
numerically exact):** define the refinement as the ε → 0 limit, i.e. rank
lexicographically by (−C(s), −H(s)) and apply pessimistic scoring to the
**(C, H)-tie block** rather than the C-tie block. This is exactly what the
strict recompute measures (18 rescues), needs no ε constant, and cannot be
destabilised by rounding. §5.9's ε-ablation would then become an ablation over
*whether* H participates in the ordering key, plus the reported sensitivity of
the result to H-tie handling (the 8 lost cases).

## 5. What changes in the manuscript if ratified

- §5.7's title and framing: "local-H score refinement" rather than
  "tiebreaking"; one sentence explaining why order-level tiebreaking is
  metric-invisible under pessimistic scoring (a genuinely interesting
  methodological point for an empirical-SE venue).
- §4.6 states the implemented ranking rule as-is (already drafted that way)
  and notes that ties are resolved in order, not in score.
- Paper 6 §4.5's "alphabetical tiebreaker" sentence goes on the Q2
  correction list.
- §5.9's ablation (ratified): (i) H in the ordering key vs not; (ii) sensitivity to H-tie handling (the 8 boundary cases). No ε constant appears in the paper.

## 6. Risks / honest caveats

1. **It modifies the method.** A reviewer could read the refinement as tuning
   against the benchmark. Mitigation: report both variants; state that the
   refinement uses only quantities the method already computes (H is the
   Mamdani output), introduces no new data, and is motivated by the mechanism
   analysis rather than by a score sweep.
2. **The ceiling is far below the baselines** (0.152 vs DejaVu 0.744): even
   fully realised, the refinement does not make FCP competitive on TT ranking.
   The honest framing stays "explanation-optimised method with a
   characterised, partially-addressable ranking limitation at scale."
3. **If measured gain ≪ ceiling**, that is itself a finding (the H ordering
   inside blocks is weakly informative) and gets reported per the D7
   honest-negative clause.

## 7. Decision requested

- [x] **RATIFIED 2026-08-10** — §5.7 becomes local-H score refinement (ε → 0
      lexicographic form), mechanism (a) only, ceiling **0.152**, both variants
      reported, as-shipped numbers remain the headline.
- [ ] **Reject** — §5.7 instead reports the *negative* result directly: no
      ranking-side intervention can improve canonical AC@1 (order-level is
      metric-invisible; the method is unchanged), with the mechanism split as
      the explanation and all refinement work deferred to Paper-8.
- [ ] Other.
