# Paper 6 — Q2 revision correction ledger

Corrections to `Paper6_v11_final.docx` discovered while building the method
paper. All are traceable to commit `d485957` of this repository.

**Numbering note:** #1 and #2 were identified earlier in the same work stream
and are recorded here for the first time; #3 was ruled in on 2026-08-10.

**SUBMISSION-ORDER CONSTRAINT (S6).** Corrections #1, #4 and #7 are substantive
reversals of published Paper 6 numbers, and #5 withdraws a provenance claim both
papers rely on. Paper 6 must therefore be revised *after* the method paper is
submitted and must cite it; the two manuscripts must not be in review
concurrently, or the review system will hold two papers asserting incompatible
things about the same data.

## #1 — ECE values reflect the naive tie convention

Paper 6's reported FODA-FCP ECE values (0.167 RE1-OB, 0.123 RE1-SS, 0.219
RE1-TT) were computed with a correctness label derived from naive top-1
equality. Under the canonical pessimistic convention (worst rank in tie block,
see `DEVIATIONS.md § AC@1 tie-handling convention`) the values are **0.119 /
0.051 / 0.243**. Several baselines also move (e.g. MonitorRank RE1-TT
0.174 → 0.182, CausalRCA RE1-SS 0.300 → 0.266, yRCA RE1-TT 0.245 → 0.279).
AC@1 values are unaffected — Paper 6's 0.400 / 0.160 / 0.008 were already
pessimistic and are bit-reproducible.

**Action:** update all ECE cells in Tables 1a–c and any ECE discussed in §4.4
/ §4.5; add a one-sentence convention statement to §4.1.

## #2 — Blanket "ground-truth H = 0.88–0.95 on failures" is not universal

Paper 6 §4.5 states that ground-truth services retain high local membership
(H = 0.88–0.95) across the failed RE1-TT cases. The failure set is
heterogeneous: of 124 failures, 87 (saturation) and 6 (residual) have
ground-truth H median 0.950, but **31 (silence) have H = 0.000** — no Mamdani
rule fires on any of the 64 services. The claim holds for 93/124, not all.

**Action:** qualify the sentence in §4.5 ("on the 93 cases where local
inference fires…") and, if space permits, report the mechanism split; full
data in `paper/notes/tt_mechanism_split.md`.

## #3 — §4.5 "deterministic alphabetical tiebreaker" is factually wrong

Paper 6 §4.5 describes FCP's ranking as breaking ties with a "deterministic
alphabetical tiebreaker." The implementation has **always** ranked by
`(−C(s), −H(s), service_name)` — local Mamdani confidence H is consulted
*before* the name — and git history confirms this ordering since the adapter's
first commit, i.e. it was active in every run reported in Paper 6.

**Action:** correct the sentence to describe the actual `(−C, −H, name)`
ordering. Note that the correction does not change any reported number: under
pessimistic scoring the ground truth takes the worst rank in its score-tie
block, so within-block ordering is invisible to AC@1 either way (this
invariance is proved in the method paper's §5.7).

## #4 — δ = 0.85 is treated as a neutral method property; it is not

Paper 6 reports FODA-FCP at the shipped damping factor without noting that the
setting is consequential. The method paper's dose–response sweep shows AC@1
improving 1.4× / 2.6× / 58× (RE1-OB / RE1-SS / RE1-TT) as damping is increased
toward the local-only limit, with coherence and completeness improving in the
same direction. Paper 6's characterisation of FCP — including the below-chance
RE1-TT centrepiece — is therefore a statement about one point on a steep curve,
not about the method as such.

**Action:** add a sweep-aware caveat wherever FCP's ranking numbers are
discussed (§4.2, §4.4, §4.5), citing the method paper's §5.9. The below-chance
finding stands as reported for the evaluated configuration; what needs
qualifying is the implication that it characterises the fuzzy-ontology approach
rather than that configuration's propagation setting.

## #5 — SC provenance: the propagation table was authored during evaluation

Paper 6 reports SemanticCoherence against DiagnosticKB's 22-individual
propagation table and presents that table as curated domain knowledge. Git
history shows the table was added on 2026-05-12 (`85cbb8d`), four days after the
RCAEval evaluation module and about 2.5 hours after the first full
7-method × 125-case metric run, in the same commit as the coherence metric
itself. The eight fault prototypes are unaffected — they date from 2026-05-04.

**Action:** add the same disclosure the method paper carries (§3.6, §5.8),
including the two safeguards (no benchmark vocabulary in the ontology; no
transitive closure) and the direction-of-result argument (measured SC is low and
declining, so concurrent authorship did not tune it upward). Applies wherever
Paper 6 discusses SC as an independent check.

## #6 — no-Recommendation count: 31 published, 35 measured

Paper 6 §4.5 states that FCP's RE1-OB completeness of 0.824 reflects "31 of 125
cases (12 delay, 12 packet-loss, 7 disk)" in which the Mamdani rule engine fires
no Recommendation. The measured count at current head is **35**, and the fault
split does not match either.

**Status: PENDING INVESTIGATION.** It is not yet established whether the
published figure was measured under a different definition (for instance
counting only cases where EC fell to exactly 1/3, rather than all cases lacking a
Recommendation atom) or is simply stale. Until that is settled the discrepancy
must be left visibly open and never presented as resolved.

**No anchor in the method paper.** The method paper's §5.5 discusses the same
behaviour qualitatively — "on the cases where its rule engine fires no
recommendation, the mitigation category is unmet" — without quoting a count, so
no contested number was imported there to create one. If a count is ever added to
that sentence it must be 35, with the discrepancy flagged.

**Action at revision:** re-measure under Paper 6's own definition, then either
correct the figure to 35 with its fault split or record why the two definitions
differ.

## #7 — Eq. (13) is a different mis-transcription of the same operator

Checked 2026-08-22 as part of the journal paper's Task 4.3, which asked whether
Paper 6 restates the propagation equations. **It does.** §4.5 prints:

> C(s) = 1 − ∏_{n ∈ neighbors(s)} (1 − H(n) · edge_weight(n, s))   (13)

The implemented operator is

> C(s) = clamp_[0,1]( 1 − (1 − H(s)) · ∏_t (1 − δ · w(s,t) · C(t)) )

Paper 6's form differs in three ways, none of them the journal draft's error
(Paper 6 has **no** `(1 − δ)` convex-mixing term anywhere — that mistake is the
journal draft's alone):

1. **δ is absent.** The damping factor does not appear, so the equation as
   printed describes the δ = 1 case only.
2. **It uses the neighbour's local H(n) where the code uses the neighbour's
   propagated C(n).** As printed it is a single pass out of local evidence, not
   an iterated fixed point.
3. **The anchor factor (1 − H(s)) is missing**, so the service's own local
   evidence does not enter its own confidence.

**Does this move any Paper 6 number?** No. Every reported value came from the
code, and the saturation argument the equation is introduced to support survives
intact — the implemented form is still one minus a product of complements over
active neighbours, so it still saturates as neighbour count and per-neighbour
strength grow. What fails is the equation as a description of the algorithm, and
the sentence immediately after it, which reasons about "per-neighbor H" as the
quantity entering the product when in the implementation it is the propagated
C attenuated by δ.

**Action at revision:** replace Eq. (13) with the implemented form, and adjust
the following sentence so the density argument is made in terms of δ·w·C rather
than H·edge_weight. Cite the journal paper's §4.4 for the full statement. Note
in passing that the ≈ 3 versus ≈ 10–20 active-neighbour contrast, which carries
the argument, is unaffected.

(The no-Recommendation discrepancy in the same passage is correction #6, above.)
