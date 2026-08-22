# Finalization brief — deliver the manuscript as a Word file

Supersedes Part 2 Task P2-5 (LaTeX/EMSE template). The deliverable is a **.docx
on the author's machine**, not a LaTeX build. Venue is undecided and drafted to
EMSE conventions; Word keeps reformatting cheap later.

Standing rules from `CLAUDE_CODE_EXECUTION_PROMPT.md` §0 still apply: tracker
equals disk, file evidence per completion claim, durable files, verified-not-
asserted, and the STOP triggers (any §5 number moving, any contradiction with the
locked canonical set, any re-derivation disagreement).

**Author ruling: manuscript text is NOT committed to the repository.** Drafts and
the .docx stay under `~/research/papers/`. Notes and scripts continue to be
committed as before.

---

## Step 1 — Apply cold read v2

From `paper/notes/coldread_findings_v2.md`. MF-B, MF-C, MF-D, SF-A, SF-B, SF-C
are small and self-contained; do them first. MF-A is Step 2.

- **MF-B** — §7 gains a sixth "less comfortable" item: the explanation quality
  measured here is *structural*, and whether that structure helps a human under
  time pressure is untested, because the operator study is not part of v1.
- **MF-C** — remove the internal "Drafting status" table from the assembly step,
  not just from the assembled file.
- **MF-D** — write marker 14 into §4.6 and §5.3, drop the `[AUTHOR-VERIFY]`:
  `confidence = clip(top1_C / sum(C over top-k), 0, 1)`, top-k = 3, zero on an
  empty head; the Java reference reports absolute `finalConfidence`, so the
  normalisation is an adapter-level deviation.
- **SF-A** — name RE1-TT in §7's "31 of 124".
- **SF-B** — the Kosov deadline (2026-08-25) has passed or is passing. Resolve it:
  either the validation landed and §5.8 takes the qualified-independence variant
  from `kosov_validation_protocol.md`, or it did not and both §5.8 and §7 stop
  saying a re-derivation "is under way". Do not ship an unresolved tense.
- **SF-C** — drop "nothing in our results suggests it would be hard" from §6′.1.

## Step 2 — Expand §2 (MF-A), and treat citation integrity as a STOP condition

§2 currently runs 708 words over 11 references. Target 1,800–2,200 words. Required
coverage: microservice RCA beyond the six evaluated baselines; **LLM-based RCA**
(the largest gap — a 2026 RCA paper silent on it reads as out of date); actual
instances of ontology-based fault diagnosis outside microservices, not just the
Noy–McGuinness methodology paper; fuzzy diagnosis beyond the original Mamdani
reference; and RCA evaluation/benchmarking work beyond RCAEval.

**Fabricated citations are the single largest risk in this step, and a fabricated
reference in a submitted manuscript is a career-level problem, not a typo.**
Therefore:

- Every new citation must be a real, locatable work with title, authors, venue,
  year, and DOI or a stable URL.
- Write every new citation to `paper/notes/new_citations_for_author_check.md` with
  its DOI/URL and one line on what it is cited *for*, so the author can verify the
  set in one pass.
- **If you cannot verify a work exists, do not cite it.** Write the gap into that
  file as "claim needs a citation — none verified" and leave the sentence
  unsupported for the author to fill. An honest gap is recoverable; an invented
  reference is not.
- Do not pad the count. A precise 40 verified references beats 60 with three
  invented ones.

## Step 3 — Bibliography

Resolve all 14 `[REF:*]` placeholders plus the new §2 citations into a single
reference list, Springer author–date style. `paper6/Paper6_BibVerification_Report.md`
and `paper6/Paper6_BibCorrections_Log_v7.docx` carry verification work from the
sibling paper — reuse where they overlap rather than re-verifying.

The AICT conference paper is **not** cited (Option C); §1 carries the disclosure
sentence. Upgrade to a proceedings citation only if AICT is accepted before
submission — check status.

## Step 4 — Figures

Three, into `paper/figures/` with generating source alongside each:

1. **Figure 2 — architecture (§3.1).** Four layers. Redraw from scratch; no reuse
   of the Springer/LNNS chapter artwork.
2. **Figure 3 — Algorithm 1 pseudocode (§4.4).** Must reflect the **corrected**
   equations: δ inside the Noisy-OR product, H(s) as per-iteration anchor, no
   `(1−δ)·C_prev` term, adaptive routing, clamp.
3. **Figure 4 — canonical explanation (§4.7).** Case `re1-ob_adservice_cpu_3`,
   four atoms and five typed links, from
   `paper/artifacts/foda_fcp_explanation_samples.json`. Show both channels
   (`fuzzy_membership` = H, `confidence_share`) distinctly.

Export at ≥300 dpi PNG or as vector, sized to fit a single column.

## Step 5 — Tables and appendices

Tables 1a–c typeset from the committed CSVs with bootstrap CIs from
`paper/artifacts/bootstrap_ac1_cis.md`.

Appendices, letters not Roman numerals (fix the two-scheme collision recorded in
`appendix_map.md`): **A** propagation table (22 individuals, 0 self-pairs);
**B** the 16-rule Mamdani base; **C** adapter contracts per method;
**D** extended δ sweep (this is what SF-1's ceiling sentence points at — update its
wording to the letter you assign); **E** membership-function parameters;
**F** artifact release + cross-reference checklist.

## Step 6 — Marker sweep

Drive `[AUTHOR-VERIFY]`, `[TODO]`, `[NOTE-TO-AUTHOR]`, `[TABLE]` to zero.
`[NEW-MATH]` on Theorem 2 and marker 8 (SLO sources) are **author-only** — do not
invent either. List whatever remains in `paper/notes/submission_gate.md` as
outstanding author actions, with what each needs.

Marker 16 (TT wall-clock) needs a short timing run on RE1-TT — do it, or record
that the claim is dropped.

## Step 6b — Rewrite all mathematics as LaTeX

**Precedent, verified 2026-08-22.** `~/research/papers/last-Mirzazada_NDU_2026_Tezis.docx`
carries **11 native Word equations (`m:oMath`), 0 MathType/OLE objects** — LaTeX
converted to real Word equation objects. That is the target. `paper6/Paper6_v11_final.docx`
by contrast has **0 native equations and 7 images** — its math was pasted as
pictures. Do not repeat the Paper 6 approach.

The manuscript's math is currently Unicode plain text (`∏`, `≤`, `‖·‖_∞`,
`C^{(k)}`, `δ`), which pandoc passes through as prose and which produces no
equation object at all. Rewrite it:

- Display equations in `$$…$$`, inline math in `$…$`.
- Covers §4.2 (membership functions), §4.3 (firing strength), §4.4 (Eqs. 2–4),
  §4.5 (both theorems, their proofs, the Corollary, the Jacobian, both bounds),
  §5.4 (SG_fuzzy, SC_fuzzy), §5.7 (lexicographic refinement and the ε → 0 limit).
- Inline symbols in running prose count: δ, ρ, H(s), C\*, ρ(W̃), ‖C − C′‖_∞.
- Keep manual equation numbers (2), (3), (4) as right-aligned text. Do not use
  Word field auto-numbering — every cross-reference is written against these.

**Piecewise definitions need `\begin{cases}`.** The trapezoidal and triangular
membership functions of §4.2 are piecewise. Write them as
`\begin{cases} … \\ … \end{cases}`, never as comma-separated branches on one
line. The thesis file above contains exactly this failure in its third equation —
its piecewise μ_HIGH collapsed to `μHIGH(x)=0, x ≤ 100(x-100)/200, 100 < x ≤ 3001,`
with the branches run together. Use it as the negative example.

## Step 7 — Build the Word file

Preferred path: `pandoc manuscript_assembled.md -o <output>.docx` with a
`reference.docx` supplying styles. If Springer publishes a Word template for EMSE,
use it as the reference document; otherwise build a clean academic reference.docx:
single column, 11–12 pt serif body, numbered headings to three levels, captioned
figures and tables, an author-date reference list.

Requirements for the output file:

- Title, authors, abstract, keywords as front matter.
- All figures **embedded** (not linked) and captioned.
- Tables as real Word tables, not images, so they remain editable.
- Equations legible — Word equation objects or clean images; do not ship raw
  markdown math.
- Cross-references resolved to real section, figure, table and appendix numbers;
  no `§6′` artifacts and no reference to the abandoned §6.
- Page count reported. This settles the words-per-page question that the earlier
  41–43 page estimate could not.

**Save to `~/research/papers/FODA-FCP_method_paper_v1.docx`.** Do not commit it or
the drafts to the repository.

## Step 8 — Final gate

Complete `paper/notes/submission_gate.md` and report it. Beyond the existing
checklist, confirm:

- Every number matches the locked canonical set.
- §1 carries exactly the four ratified contributions, (iii) as a finding.
- TT phrased canonically wherever it appears.
- Abstract is variant B; no operator-relevance claim in title or abstract.
- Independence appears only in decomposed form.
- Every citation in the reference list is verified — cross-check against
  `new_citations_for_author_check.md`.
- Kosov Option B resolved one way or the other, and §5.8/§7 match the outcome.
- Submission-order constraint noted: Paper 6 must not be in review concurrently.

## Also flag for the author, do not act on it

`paper/notes/` is tracked and scheduled for public release with the Zenodo DOI at
tag `v1.0-method-paper`. It contains the Paper 6 correction ledger, the cold-read
findings, the Kosov protocol, and the execution briefs. The author should decide
deliberately what ships in the public artifact **before** tagging. Raise it; do not
change what is tracked.
