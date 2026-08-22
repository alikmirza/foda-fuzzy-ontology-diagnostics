# COLD READ v2 — assembled manuscript

Reviewed 2026-08-22 against `draft/manuscript_assembled.md`, the ratified spine,
the locked canonical set, and the R1–R6 rulings. This is the review commissioned
at the start of the session, now run on text that exists.

**Overall: the manuscript is sound and the fresh prose is good.** §6′.2 and §7 are
the strongest writing in the paper — the dose–response discussion earns its place
and the "less comfortable" list in §7 is the kind of honesty that survives review.
Findings below are about coverage and residue, not about argument.

---

## Ratified-spine check — PASS

| item | status |
|---|---|
| §1 contribution list = the four ratified items, exactly | **PASS** — no additions, no omissions |
| (iii) phrased as a finding, not a configuration | **PASS** |
| AICT disclosure present, not cited | **PASS** |
| Abstract variant B, no §6 | **PASS** |
| No operator-relevance claim in title or abstract | **PASS** |
| TT canonical phrasing | **PASS** — verbatim in abstract, §1 and §7 |
| Independence decomposed only | **PASS** — absent from §1/§6′/§7; decomposed in §5.5 |
| δ = 0.85 headline everywhere | **PASS** |
| Abstract's "at δ ≤ 0.2 all improve on all three systems" | **VERIFIED** against the sweep: OB 0.544/0.396/0.835, SS 0.408/0.296/0.755, TT 0.216/0.212/0.824, each beating the shipped values on every axis |
| NF-1 / NF-2 / NF-3 applied | **PASS** — §2.2's "They do not lack structure. They lack *shared* structure" is the right formulation |

---

## Must-fix

### MF-A. §2 is under-cited by roughly a factor of three, and the paper makes a novelty claim it cannot currently support

The manuscript cites **14 distinct references in total; 11 of them in §2**, which
runs 708 words. For an EMSE full paper that is far below expectation — related
work at this venue typically runs 1,500–2,500 words over 40–60 references.

The exposure is not length, it is the novelty claim. §2.3 closes: *"We are not
aware of prior work in microservice RCA that both grounds explanations in a shared
ontology and reports where that grounding fails."* A claim of that form obliges
the paper to demonstrate it surveyed the space. Eleven citations do not.

Concretely absent:

- **Microservice RCA beyond the six baselines.** The evaluated panel is not the
  field. Trace-based and multimodal approaches, graph-neural and hierarchical
  localisation, and the recent wave of diagnosis systems combining metrics, logs
  and traces are unrepresented. A reviewer who works in this area will name five
  systems in the first paragraph of their report.
- **LLM-based RCA.** The most active line of work in this space over the last two
  years, and the paper is silent on it. This is the single most likely "reject and
  resubmit" trigger: a 2026 RCA paper that does not position against LLM-based
  diagnosis reads as out of date regardless of its merits.
- **Ontology-based fault diagnosis outside microservices.** §2.3 asserts this has
  "a long history" and then cites one ontology-*engineering* methodology paper
  [REF:NoyMcGuinness] — no actual instance of the history it invokes.
- **Fuzzy diagnosis** beyond the original Mamdani reference.
- **Evaluation and benchmarking of RCA**, where only RCAEval appears; the
  measurement-validity literature this paper is in dialogue with is not cited.

This does not require restructuring, and it interacts with the page-budget
question below: coverage is not negotiable at a Q1 venue, length is. If something
has to give, §2 grows and the trim comes from elsewhere.

### MF-B. The paper is motivated, and one of its metrics defined, in terms of operators — and never says it did not evaluate with any

§1 opens on a site reliability engineer paged at 02:00. §5.4 defines
ExplanationCompleteness as measuring *"whether an explanation supplies what an
operator needs to act."* §3.1 describes an "operator-facing" explanation layer.

The §6 operator study is NO-GO for v1, so there is no operator data anywhere in
the paper. §7 lists five uncomfortable findings and **this is not among them**,
nor does any limitation state it.

That is the gap a reviewer will walk straight into: the paper's central quality
construct is defined by reference to operator needs and validated by none. The
ruling that kept operator claims out of the title and abstract was the right
call; it does not extend to staying silent about the absence. Add it as the sixth
item in §7's list, in the same register as the others — the explanation quality
this paper measures is *structural* (is the claim grounded, coherent, complete
against a defined schema), and whether that structure helps a human under time
pressure is untested here and is the study the method still owes.

Doing so also protects the §1 vignette, which currently sets an expectation the
paper never returns to.

### MF-C. The internal "Drafting status" table is still in the assembled manuscript

Between §5.10 and §6′ (line 712) the assembled file carries the subsection-by-
subsection drafting-status table. It is a working artifact and must not reach a
reviewer. Remove from the assembly step, not just from the file, so it does not
reappear on the next rebuild.

### MF-D. Marker 14 has been resolved three times and still is not in the text

§4.6 still carries `[AUTHOR-VERIFY: confirm the exact confidence formula to quote
from the reference implementation]`. The formula was extracted verbatim in the
STOP note, restated in the execution brief Task 6, and confirmed again in the
Tasks 4–7 review. It is:

```
head      = ranked[: top_k]           # top_k default 3
head_sum  = sum(c for _, c in head)
confidence = clip(head[0][1] / head_sum, 0, 1) if head_sum > 0 else 0.0
```

Reported confidence = top-1 C over the sum of C across the reported top-k,
clamped, zero on an empty head. The Java reference instead reports the absolute
`finalConfidence`; the normalisation is an adapter-level choice and belongs in
§5.3's deviation list as well. Write both and drop the marker.

---

## Should-fix

### SF-A. §7's silence count is stated without its system

*"In 31 of 124 failing cases no rule fires anywhere in the system."* That is
RE1-TT specifically (system silence is 31/46/31 across the three). Context makes
it inferable, but the sentence is quotable and will be quoted. Name the system.

### SF-B. §7 asserts an independent re-derivation "is under way" — the deadline is Monday

The Kosov blind validation (Option B) has a two-week deadline from 2026-08-11,
i.e. **2026-08-25**. §7 and §5.8 both state it as in progress. If it does not land,
the sentence is false at submission. Make it conditional now, or resolve the item
and write whichever variant applies — `kosov_validation_protocol.md` has both
pre-drafted.

### SF-C. §6′.1 makes a difficulty claim with no evidence behind it

*"Nothing in the design space we surveyed does this, and nothing in our results
suggests it would be hard."* The first half is supported; the second is
speculation about implementation difficulty that no result in the paper speaks
to. In a Discussion a forward-looking suggestion is fine, but drop the
evidentiary framing — say partial grounding is worth attempting and why, without
implying the results bear on its cost.

---

## Author decision, not a defect

§7 discloses that the drafted propagation equations were not the implemented
ones. Some reviewers will read that as exemplary; others will wonder why a
manuscript's internal correction history is in its conclusion. It is defensible
here **because it is load-bearing for the errata story** — Paper 6 prints a
different but also incorrect Eq. (13), and the AICT version may carry the
manuscript's version. Keep it if the AICT check confirms an erratum is owed;
reconsider if AICT turns out to be clean, in which case the disclosure belongs in
`DEVIATIONS.md` and the artifact rather than in §7.

---

## Marker inventory at cold read

10 remain: 5 `[AUTHOR-VERIFY]` (including marker 8, author-only, which cannot be
invented), 1 `[NEW-MATH]` on Theorem 2 awaiting independent re-derivation,
1 `[NOTE-TO-AUTHOR]`, 3 `[TODO]` (Algorithm 1 typesetting, Figure 4 canonical
explanation, marker 16 TT wall-clock). None is a blocker for the current phase;
all are gate items in `submission_gate.md`.

## Page budget

Claude Code's 41–43 page estimate is more careful than my 34–37 and I defer to
it — I had not counted front matter, references or figure area. Neither estimate
should drive a cut: the reliable number comes from compiling in the actual
template at P2-5. Note that MF-A pushes length up, so the trimming conversation
should happen once, after the template compile, with §2's expansion already in.

---

## PF-1 (process, raised 2026-08-22) — the manuscript itself is not under version control

Prompted by the author's question about why we commit paper text. The answer is
that we largely **do not**, and that is the finding.

- `~/research/papers/` — which holds `section3`, `section4`, `section5`, the new
  `section1`, `section2`, `section6prime`, `section7`, and
  `manuscript_assembled.md` — **is not a git repository.** `git rev-parse` there
  returns nothing.
- The repository tracks 40 files under `paper/`, all of them *notes about* the
  paper (`paper/notes/*`) and figure artifacts (`paper/artifacts/*`). The only
  files matching "section" are planning notes: `section5_plan.md`,
  `section5_reuse_new_summary.md`, `section5_7_reframing_proposal.md`.
- So the reasoning trail is fully versioned and the manuscript is not.

This is the same failure mode that lost the δ-sweep CSVs, and worse: a lost CSV
can be regenerated by a script, whereas the manuscript cannot be regenerated at
all. It also undercuts ratified contribution (iv). "Every reported number pinned
to its generating commit" is only half true while the text doing the reporting is
unversioned — a replicator can pin a number to `2d359bc` but cannot recover which
version of §5.9 quoted it.

It has already bitten this session twice: the handoff brief asserting a fix round
that had not happened, and `PROJECT_STATE.md` re-enshrining a withdrawn
specification. Both were detectable only by reading current file contents, with no
history to diff against.

**Recommended:** move the drafts under the repository — `paper/draft/` alongside
`paper/notes/` — and commit them, rather than initialising a second repository at
`~/research/papers/`. One history covering ontology, engine, adapters, results,
notes and manuscript is what the artifact-release contribution actually promises,
and it makes "which text quoted which number at which commit" answerable.

The `paper6/` sources and the PDFs under `~/research/papers/` can stay where they
are; they are inputs, not deliverables.

### PF-1 — AUTHOR RULING, 2026-08-22: manuscript text stays out of git

The author has ruled that article text is not committed. PF-1's recommendation to
move the drafts under `paper/draft/` is **withdrawn**. Do not add manuscript files
to this repository.

Two things the ruling leaves open, recorded so they are not lost:

1. **The drafts still have no backup or history.** `~/research/papers/` is not a
   repository and the manuscript cannot be regenerated from anything. Whatever
   mechanism the author prefers — a separate *private* repository, cloud sync, or
   dated snapshots taken before each edit round — the requirement is only that a
   lost or clobbered draft be recoverable and that "what changed since the last
   round" be answerable. This does not need to be git and does not need to be this
   repository.

2. **The inverse exposure now matters more, and points the other way.** This
   repository is scheduled for public release at tag `v1.0-method-paper` with a
   Zenodo DOI (Appendix F). `paper/notes/` is *already tracked* — 40 files — and
   publishing it publishes:
   - `paper6_q2_corrections.md`, a correction ledger against a **published** paper
     whose corrections have not yet been filed with its venue;
   - `STOP_propagation_equation_finding.md` and both cold-read findings files,
     i.e. adversarial reviews of a manuscript that will be under review;
   - `kosov_validation_protocol.md`, describing a blind validation of a co-author
     that has not been run;
   - the execution briefs and `PROJECT_STATE.md`, including venue strategy and the
     Paper 6 submission-order constraint.

   Some of that is defensible transparency and some of it is plainly internal. The
   decision of what ships in the public artifact is the author's and should be made
   deliberately **before** the release tag, not inherited from what happened to be
   committed. Options: keep `paper/notes/` tracked but exclude it from the released
   archive; split the internal notes into a private repository; or curate a subset
   (the provenance audit and regeneration scripts are genuinely part of the
   artifact story; the correction ledger and review notes are not).

   Added to the submission gate.
