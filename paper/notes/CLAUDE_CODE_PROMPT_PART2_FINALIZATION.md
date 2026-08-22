# Execution brief — PART 2: finalization to submission

Runs **after** `CLAUDE_CODE_EXECUTION_PROMPT.md` (Part 1, Tasks 1–8). Part 1's
standing rules in §0 — tracker-equals-disk, file evidence per completion claim,
durable files, verified-not-asserted, the STOP triggers, no code changes without
authorisation — apply unchanged here. Re-read them before starting.

Part 1 takes the manuscript from "equations wrong, §1/§2/§7 missing" to "complete
draft". Part 2 takes it from complete draft to submittable. Target: EMSE,
~29.5 pages, submission ~September 2026.

---

## Task 0 — URGENT, do this before anything else

`paper/notes/PROJECT_STATE.md` predates the 2026-08-22 STOP and re-enshrines a
**withdrawn** specification. Any fresh conversation reading it as a handoff brief
will faithfully execute a repair to a theorem about an operator the method does
not use. Replace §4's "PENDING — blocking" block with:

```markdown
**PENDING — blocking (REVISED 2026-08-22, see STOP_propagation_equation_finding.md):**
- **R1** Eqs. (2)–(4) are a mis-transcription. The implementation applies δ as a
  per-edge attenuator *inside* the Noisy-OR product and has no (1−δ)·C_prev(s)
  term; H(s) is a per-iteration anchor. Source is canonical (WorkedExampleTest.java
  + evaluation/methods/foda_fcp.py). Rewrite both routing branches.
- **R2** Theorem 1 restated: ρ = δ·max(1−H)·W ≤ δ < 1. **Strict contraction for
  every δ < 1 regardless of W and H — the W = 1 boundary case does not exist and
  the former Fix 8a spec is WITHDRAWN, not amended.** Sole boundary case is δ = 1
  (non-expansive only); δ = 1.0 is a swept configuration and needs a §5.9
  disclosure sentence that convergence there is empirical.
- **R3** Theorem 2 on the corrected Jacobian (no (1−δ)𝟙[s=t] diagonal), four
  Perron–Frobenius steps named. Worked example: both bounds coincide at 0.476,
  true ρ(J) = 0.3614, predicts the observed 14 iterations.
- **Fix 8c** closure: fresh script against the CORRECTED equations must reproduce
  0.7255/0.5271/0.5453 in 14 iterations.
- **Fix 8d** CLOSED — marker 14 (confidence formula) and marker 7
  (correlation-graph parameters) both extracted verbatim.
- **R4** DEVIATIONS.md entry + aict_errata.md placeholder (AUTHOR-ONLY, pending).
- **P2-1** δ-sweep provenance gap — see below. BLOCKING for §5.9.
```

Two further edits to the same file: §6's list of what verification has already
caught gains *"and a central propagation equation that did not match its
implementation"* — that list is the argument for the discipline and this is its
strongest entry. And §4's "Drafted: §4 (complete)" is no longer true.

---

## Task P2-1 — BLOCKING: the δ sweep has no durable provenance

**Finding, 2026-08-22.** The project's provenance rule is that every number traces
to a file under `results/` recorded in `RESULTS_PROVENANCE.md`. The δ dose–response
does not.

Verified:
- `find` across the whole repo for `*delta*`, `*sweep*`, `*ablation*`, `*refined*`
  returns only `paper/notes/delta_tradeoff_2026-08-11.md`,
  `paper/notes/ablation_results_2026-08-10.md`, and `sweep_resume.log`. **No CSVs.**
- `grep -i "delta\|sweep\|ablation\|scratch" RESULTS_PROVENANCE.md` returns
  **zero matches**.
- `delta_tradeoff_2026-08-11.md` cites its source as
  `scratchpad/delta_ext/delta_extended_{re1-ob,re1-ss,re1-tt}.csv` — a
  session-local path under `/private/tmp/`, from a session ~11 days old. Assume
  gone.

**What depends on it:** the entire §5.9 dose–response table; the 1.4× / 2.6× / 58×
headline; the dominance argument; TT SC 0.086→0.372 and EC 0.789→0.835; the basin
values MF-1/MF-2/MF-3 correct the text against; SF-1's Appendix II reference; the
`ac1_refined` column; and **§1's ratified contribution (iii)**, which is the δ
dose–response itself. This is the paper's most consequential measurement and it is
currently backed by a markdown note rather than by data.

**Required:**
1. Re-run the extended sweep from the harness: 11 δ values × 3 systems × 125 cases,
   pessimistic convention, dual-channel atom semantics, `ac1_shipped` and
   `ac1_refined` columns, all four metrics at each point.
2. Write the CSVs into `results/` under stable names.
3. Add `RESULTS_PROVENANCE.md` entries with generating commit, scoring convention
   and seed, matching the format of the existing entries.
4. Diff every regenerated value against `delta_tradeoff_2026-08-11.md`.
   **Any disagreement in any digit is a STOP** — it would move §5.9's numbers and
   with them a named contribution.
5. Do the same audit for `ablation_results_2026-08-10.md` and for the §5.7 refined
   variant, and for the §5.6 per-case instrumentation SF-3 needs. Record what is
   durable and what is not in `paper/notes/provenance_audit_2026-08.md`.

Until this closes, §5.9 must not be treated as final and §1 contribution (iii)
must not be drafted as settled.

---

## Task P2-2 — Figures

Three, all currently markers. None may reuse prior artwork.

1. **Figure 2 — architecture (§3.1).** Four layers: telemetry/anomaly, fuzzy
   inference, knowledge, explanation. **Redraw from scratch — no reuse of the
   Springer/LNNS chapter artwork [D8].** `foda_ml_architecture.drawio` in the repo
   root is a starting reference for content, not a source to copy.
2. **Figure 3 — Algorithm 1 pseudocode (§4.4).** fuzzify → infer → route →
   propagate → rank, typeset from the reference implementation's control flow.
   **Must reflect the corrected equations from Part 1 Task 1**, including the
   adaptive routing (topological sort attempt, Jacobi fallback) and the clamp.
3. **Figure 4 — canonical explanation example (§4.7).** Case
   `re1-ob_adservice_cpu_3`: four atoms (Fault, two ContributingFactors,
   Recommendation), five typed links. Source data:
   `paper/artifacts/foda_fcp_explanation_samples.json`. Show the dual channels
   (`fuzzy_membership` = H, `confidence_share`) distinctly — the split is a
   ratified design point and the figure is where a reader sees it.

Figures go in a `paper/figures/` directory with the generating source alongside
each output.

---

## Task P2-3 — Appendices, and fix the naming scheme

**Finding:** the drafts reference Appendix **A**, **B**, **E**, **F** only. C and
D are never referenced. Meanwhile `coldread_v1_fixes.md` item F5 refers to
"Appendix I", and SF-1's ratified wording refers to "Appendix II". **Two
incompatible numbering schemes are in circulation and neither is complete.**
Choose one — letters, since the drafts use them — and map every existing
reference onto it. Write the mapping to `paper/notes/appendix_map.md`.

Contents to produce:

| Appendix | Content | Source |
|---|---|---|
| A | Full 22-individual propagation table, curation rationale, known omissions | `ontology/DiagnosticKB.owl` |
| B | Full 16-rule Mamdani base (R01–R16), six categories, CF values | rule-base YAML |
| C | Adapter contracts per method (marker 18) | `DEVIATIONS.md` |
| D | Extended δ sweep, all 11 values × 3 systems × all metrics | the CSVs from P2-1 |
| E | Membership-function parameter tables | §4.2 / reference impl |
| F | Artifact release + LaTeX cross-reference checklist (S8) | new |

Appendix D is the one SF-1 points at ("higher-δ refined values in Appendix …
exceed the ceiling because the failure decomposition differs there"), so SF-1's
wording must be updated to whatever letter you assign.

---

## Task P2-4 — Bibliography

Resolve every `[REF:*]` placeholder to a real citation and build the master
bibliography. Known placeholders: `REF:Tbilisi`, `REF:RCAEval`, `REF:Mamdani`,
`REF:Pearl1988`, `REF:NoyMcGuinness`, `REF:failure-pattern-surveys`, `REF:repo`.
Grep both drafts and the new §1/§2/§7 for any others.

**The AICT conference paper is NOT cited** (Option C). §1 carries the disclosure
sentence instead. Upgrade to a proceedings citation only if AICT is accepted
before submission — check status before finalizing.

`paper6/Paper6_BibVerification_Report.md` and
`paper6/Paper6_BibCorrections_Log_v7.docx` carry verification work from the
sibling paper; reuse where the references overlap rather than re-verifying.

---

## Task P2-5 — LaTeX conversion and the S8 checklist

Convert the assembled markdown to the EMSE (Springer) template. **Do not
restructure for TSC** — TSC is the fallback venue and restructuring for it is
explicitly ruled out.

Build the S8 cross-reference checklist into Appendix F and run it:
- every `§x.y` reference resolves to a section that exists;
- every Figure/Table/Appendix reference resolves;
- every forward pointer added in Part 1 (§3.5→§5.9, §5.5→§5.10, §5.4→§5.9) lands;
- no reference to §6 or "§6′" survives — §6 is NO-GO for v1;
- equation numbers are consistent after the Part 1 rewrite.

Check the page budget against ~29.5 pages and report the actual figure.

---

## Task P2-6 — Artifact release

- Tag `v1.0-method-paper`.
- Mint the Zenodo DOI; cite it in the paper.
- Canonical repo URL is `https://github.com/alikmirza/foda-fuzzy-ontology-diagnostics`.
  **The published Tbilisi chapter prints `alik-mirza` — a dead link.** File an
  erratum or set up a redirect, and record which was done.
- Correct the stale "18 rules" javadoc (canonical is 16 rules / 6 categories for
  the harness configuration; 20/8 is the conference configuration).
- Release checklist into Appendix F.

---

## Task P2-7 — Final submission gate

Every line must be true, with file evidence, before submission. Write the
completed gate to `paper/notes/submission_gate.md`.

**Markers**
- [ ] Zero unresolved `[AUTHOR-VERIFY]`, `[NEW-MATH]`, `[TODO]`, `[TABLE]`,
      `[COMPRESSED DEFINITIONS]`, `[NOTE-TO-AUTHOR]` in any section.
- [ ] Marker 8 (SLO sources) resolved by the author or the claim removed — it is
      AUTHOR-ONLY and cannot be invented.
- [ ] Marker 3 (CASCADING_FAILURE surrogate stands in the evaluated
      configuration) confirmed by the author.
- [ ] Theorem 2 independently re-derived by the author, against the **corrected**
      statement.

**Numbers**
- [ ] Every value matches the locked canonical set in Part 1 §0.1.
- [ ] Every number traces to `results/` via `RESULTS_PROVENANCE.md` — including
      the δ sweep (P2-1).
- [ ] TT is phrased canonically everywhere: *"0.008, below the 1/64 ≈ 0.016
      chance baseline (95 % CI [0.000, 0.024])"*.
- [ ] Ceiling derivation uses one canonical phrasing throughout (S7).
- [ ] §5.8's three figures stay distinguished: 0.509 rate, 0.403 pooled, 0.266
      reported.

**Rulings**
- [ ] §1 lists exactly the four ratified contributions, (iii) phrased as a
      finding.
- [ ] δ = 0.85 is the headline configuration everywhere including the abstract.
- [ ] Abstract is variant B (without §6); no operator-relevance claim in title or
      abstract.
- [ ] Independence appears only in decomposed form (across-methods vs
      within-method).
- [ ] Silence taxonomy uses exactly three terms; "No-Recommendation" is not
      called silence.
- [ ] AICT disclosure sentence present; AICT not cited unless accepted.
- [ ] No ε constant anywhere in the refinement description.

**Provenance and coordination**
- [ ] Ontology provenance disclosed in §3.6, §3.4, §5.8, `DEVIATIONS.md`, and
      Paper 6 ledger #5.
- [ ] **Kosov blind validation (Option B): decided.** Two-week deadline from
      2026-08-11 → **2026-08-25**. If it lands, §5.8 switches to the
      qualified-independence variant (pre-drafted in
      `kosov_validation_protocol.md`); if the deadline passes, the A-only variant
      stands and the note says so explicitly. Non-gating either way, but the
      decision must be recorded rather than left ambiguous.
- [ ] **Submission-order constraint honoured:** Paper 6 is not in review
      concurrently. This paper reverses two of Paper 6's published conclusions
      (its ECE values and its axis-independence claim) and withdraws a provenance
      claim both rely on.
- [ ] Paper 6 ledger current — including whether it restates the mis-transcribed
      equations (Part 1 Task 4.3).
- [ ] `aict_errata.md` resolved by the author, or explicitly deferred with the
      reason recorded.
- [ ] Commits carry plain messages under the author's identity, no AI-attribution
      trailers.

---

## Deliverables

1. Corrected `PROJECT_STATE.md`.
2. Regenerated δ-sweep CSVs in `results/` + `RESULTS_PROVENANCE.md` entries +
   `provenance_audit_2026-08.md`.
3. `paper/figures/` with three figures and their sources.
4. Appendices A–F + `appendix_map.md`.
5. Resolved bibliography.
6. LaTeX manuscript in the EMSE template, with the page count reported.
7. Release: tag, DOI, erratum record, corrected javadoc.
8. `submission_gate.md`, completed.
9. A completion report naming, per task, the files changed and what changed.

**A reviewer re-checks all of it against the MF/SF findings and the R1–R6
rulings. Completion claims without file evidence are treated as not done.**
