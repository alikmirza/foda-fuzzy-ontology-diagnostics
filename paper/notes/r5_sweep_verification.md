# R5 language sweep — verification that §5.7 is untouched

**Outcome: untouched, as expected. Verified by re-reading the argument, not assumed.**

Task 5 required confirming that the propagation-equation correction does not
disturb §5.7's ceiling and impossibility logic.

## The two loads §5.7 carries, and what each rests on

**1. The impossibility claim** — "under pessimistic tie handling, AC@1 is
invariant to how a tied block is ordered; if k services share the top score the
ground truth takes rank k, so AC@1 = 0 whenever k > 1."

Rests on: the scoring convention (`_ground_truth_rank` assigning the worst rank
within a score-tie block) and on the definition of a tie. It makes no reference to
how the tied scores were *produced*. Whether C came from a convex mixture or from
a δ-attenuated Noisy-OR product is irrelevant to the claim — the argument would
hold if C were assigned arbitrarily. **Unaffected.**

**2. The ceiling derivation** — 30 in-block, 18 strict / 8 tied / 4 below, ceiling
19/125 = 0.152, measured 0.144.

Rests on: per-case values of C (to determine block membership) and H (to determine
the maximum within a block). Both are produced by the code, which did not change —
the correction was to the manuscript's transcription of the code. The numbers were
independently re-derived from the harness on 2026-08-22
(`results/tt_mechanism_instrumentation.csv`) and reproduce exactly:
87/31/6 mechanism split, 30 in-block, 18 strict, 8 tied, 4 below, ceiling 0.1520.
**Unaffected.**

## One point where the correction touches §5.7, harmlessly

§5.7's lexicographic refinement is the ε → 0 limit of C′ = C − ε(1 − H). That
formulation refers to the *scores*, not to the update that produced them, so it is
also insensitive to the propagation form. The δ-dependence noted in §5.7's
requalification paragraph — that `ac1_refined` departs from `ac1_shipped` only for
δ ≥ 0.65 — is an empirical observation from the sweep, and the sweep was
regenerated from the code after the correction with all values matching.

## Conclusion

No edit to §5.7 was required by R5. The section's two claims rest on the scoring
convention and on code-produced values, neither of which the transcription error
touched. The one edit §5.7 did receive in this round (SF-3's missing category) came
from a different finding.
