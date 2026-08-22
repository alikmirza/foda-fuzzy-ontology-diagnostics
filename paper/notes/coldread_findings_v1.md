# Cold-read findings — bundle v1 (§3–§5), 2026-08-11

Read as an EMSE reviewer would: sections in order, whole-document consistency,
claims checked against each other. Five mechanical defects were fixed in place
(F1–F5 below). Eight substantive issues are listed for author ruling, ranked by
what would cost the paper most in review.

---

## Fixed in place (mechanical, no ruling needed)

| # | Defect | Fix |
|---|---|---|
| F1 | **§5.9 was printed between §5.7 and §5.8** — sections out of order in the assembled document | order restored to 5.7 → 5.8 → 5.9 → 5.10 |
| F2 | §5 header still said 5.4/5.7/5.9/5.10 were pending inputs | header rewritten to v0.2, all ten drafted |
| F3 | End-of-section status table still marked four subsections "pending" | table refreshed |
| F4 | §4.7 had a broken sentence — a fragment beginning "one Recommendation atom…" left dangling by an earlier edit | sentence repaired |
| F5 | **Appendix I contradicted §5.6.2**: it said the 31 silence cases were "loss/delay-dominated", while §5.6.2 reports the measured spread (mem 8, delay 7, disk 7, CPU 5, loss 4) | appendix corrected, supersession noted |

F5 is the one that mattered: a reviewer reading the appendix against the body
would have found the paper contradicting itself on a measured distribution.

---

## Substantive issues, ranked

### S1 — BLOCKING. §5.4 depends on an unpublished companion for its definitions

§5.4 compresses SG/SC/EC/ECE to a placeholder "carried from the framework
specification." That specification is the framework paper, which is **not
published** — it is being reframed for a later Q2 submission and will *cite this
paper*. The method paper therefore cannot lean on it for load-bearing metric
definitions: a reviewer cannot check what SG measures, and a circular
dependency between two unpublished manuscripts is exactly the structure that
drew the original circularity criticism.

**Recommendation:** define the four metrics fully and self-containedly in §5.4
(~1 page). They are compact — atom-level grounding score, per-link ontology
agreement, three-category coverage, binned ECE — and the paper needs them to
stand alone in any case.

### S2 — HIGH. §5.5 and §5.10 contradict each other on independence

§5.5 says SG = 1.000 surviving the AC@1 collapse is "the empirical content of
the claim that the two axes are independent." §5.10 then shows that *within*
FODA-FCP the axes are positively coupled (ρ ≈ +0.6 on two systems) and that the
independence reading was a pooling artifact. As written, the two sections state
opposite things about the same data.

**Recommendation:** amend §5.5's sentence to the across-methods claim only
("knowing a method's AC@1 tells you nothing about its explanation quality"),
and add a forward pointer to §5.10 for the within-method result.

### S3 — HIGH. The headline configuration is one the paper shows to be dominated

§5.9 reports δ = 0.85 everywhere while demonstrating that δ ≤ 0.2 dominates on
every axis and every system, including a 58× ranking improvement on RE1-TT. The
no-held-out-selection rationale is stated and is principled, but a reviewer will
still ask why the evaluated configuration is one the authors have shown to be
bad, and whether the paper should not simply report both as co-primary.

This is the single largest reviewer-risk item in the manuscript. The current
answer is defensible; it is not obviously the best one. Options: (a) keep as
ruled and accept the question; (b) report as-shipped and δ → 0 as two named
configurations throughout §5.5's tables, with the sweep as the justification for
reporting both; (c) re-baseline with explicit disclosure. Author's call — the
ruling stands unless revisited.

### S4 — MEDIUM. §3.5 and §4's framing note are now in tension

§3.5's table lists propagation under "Graded" as part of where fuzziness lives,
written before the sweep. §4's framing note now classifies propagation as a
*design hypothesis subsequently falsified*. A reader moving from §3 to §4 meets
the same component described first as a designed strength and then as a refuted
one, with no signal that the second supersedes the first.

**Recommendation:** one clause in §3.5 pointing forward ("its empirical
contribution is tested in §5.9").

### S5 — MEDIUM. The abstract-level story is not yet stated anywhere

Reading §3–§5 end to end, the paper's headline claim has quietly moved. It is
no longer "FODA-FCP is an explainable RCA method with a ranking limitation at
scale." The evidence now supports something sharper: *ontology-grounded fuzzy
inference produces stable, checkable explanations and competitive local
attribution; the propagation layer built on top of it is what fails, and we
measured how.* §1 and the abstract are undrafted, so nothing is wrong yet — but
the drafted sections should be written knowing that this is the story.

### S6 — MEDIUM. Two Paper 6 conclusions are now overturned by this paper

The corrections ledger holds four items, of which two are substantive
reversals: the ECE values (naive-convention) and the axis-independence claim
(pooling artifact). If Paper 6 is resubmitted citing this paper, that is a
coherent sequencing; if it is submitted concurrently, two manuscripts will be in
the review system asserting incompatible things about the same data.

**Recommendation:** treat the corrections ledger as a submission-order
constraint, not just a revision to-do.

### S7 — LOW. §5.7's ceiling arithmetic is stated three times with slightly different framing

"18 of 19 admissible cases", "0.144 against the 0.152 bound", and "17 gained + 1
baseline-correct" all appear. All are correct and mutually consistent, but a
reader has to reconcile them. One canonical phrasing, used consistently, would
read better.

### S8 — LOW. Section-number references should be verified after any reordering

§5.1's roadmap paragraph maps RQs to subsections; the F1 reordering did not
change the mapping, but every cross-reference (§5.6 → §5.7, §5.7 → §5.9, §5.4 →
§5.6.2/§5.9) should be re-checked once the section numbers are final in LaTeX.

---

## What holds up well (unprompted assessment)

- The **honest-reporting discipline is the manuscript's strongest feature** and
  is unusual in this literature: pre-registered predictions with stated failure
  conditions, one of which fired and is reported as such; a pre-commitment that
  did not fire, reported anyway; an explicit refusal to search for a better
  fuzzy metric on forking-paths grounds; a null result presented as a successful
  prediction with an argument for why.
- The **mechanism decomposition (§5.6) → bounded intervention (§5.7) →
  dose–response (§5.9) chain** is genuinely strong empirical-SE work. The
  ceiling-before-measurement move is the kind of thing EMSE reviewers reward.
- The **δ dose–response** is the most publishable single result in the paper and
  is currently buried in §5.9. Consider whether it deserves promotion in §1's
  contribution list.
- The **algebraic identity in §5.4** (SG_fuzzy ≡ firing indicator under uniform
  grounding) turns an awkward null into a clean analytical statement.

## Marker triage, revisited

Of the 12 markers I triaged blocking, S1 subsumes one (the compressed
definitions), the three unfilled table markers remain blocking, and the four
NEW-MATH/AUTHOR-VERIFY items in §4.5–4.6 remain the genuine scientific blockers:
the W = 1 boundary condition, the spectral bound derivation, the confidence
formula, and the correlation-graph parameters. Those four cannot go to a
reviewer unresolved.
