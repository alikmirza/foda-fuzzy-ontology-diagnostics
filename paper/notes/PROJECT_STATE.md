# PROJECT STATE — handoff brief

Written 2026-08-11. Read this first when continuing in a fresh conversation.
Everything below is settled unless marked PENDING or AUTHOR-ONLY.

---

## 1. Project identity

We are writing **"FODA-FCP: Explainable Root Cause Analysis for Microservices via
Fuzzy Ontology Reasoning"** — authors A. Mirzazada, P. Kosov, L. Gardashova —
targeting **EMSE first** (TSC fallback, do not restructure for it), submission
~September 2026, ~29.5 pages. It is **Q1 anchor #1** of a two-paper dissertation
plan. The plan exists because an earlier evaluation-framework manuscript
("Paper 6") was judged premature and circular by both the supervisor and a formal
reviewer: it evaluated a method that had never been published. Paper 6 is
therefore **held back** for later Q2 submission, reframed to cite this paper, and
carries a **7-item correction ledger** plus a hard **submission-order
constraint** — the two manuscripts must never be in review concurrently, because
this paper reverses two of Paper 6's published conclusions (its ECE values and
its axis-independence claim) and withdraws a provenance claim both rely on.

---

## 2. Locked canonical numbers

**Provenance rule:** every number traces to a file under `results/` recorded in
`RESULTS_PROVENANCE.md`, computed at commit `d485957` (or later, with the commit
recorded), under the **pessimistic tie convention** (ground truth takes the worst
rank in its score-tie block, for AC@1 *and* the ECE correctness label). Nothing
is hand-edited; nothing is quoted from Paper 6.

| Quantity (FODA-FCP) | RE1-OB (12 svc) | RE1-SS (15 svc) | RE1-TT (64 svc) |
|---|---|---|---|
| **AC@1 (headline, δ = 0.85)** | 0.400 | 0.160 | **0.008** |
| ECE | 0.119 | 0.051 | 0.243 |
| SG (crisp) | 1.000 | 1.000 | 1.000 |
| SG (H-weighted) | 0.744 | 0.632 | 0.736 |
| SC | 0.266 | 0.158 | 0.086 |
| EC | 0.824 | 0.749 | 0.789 |
| Chance baseline | 0.083 | 0.067 | 0.016 |

- **TT presentation is fixed:** always *"0.008, below the 1/64 ≈ 0.016 chance
  baseline (95 % CI [0.000, 0.024])"* — CI shown because it straddles chance;
  claim rides the point estimate.
- **§5.7 refinement:** ceiling **0.152** (19/125 = 1 already-correct +
  18 strict rescues); measured **0.144** on TT (17 gained, 0 lost); no effect on
  OB/SS (0 gained, 0 lost — the successful prediction).
- **δ dose–response (§5.9):** shipped → δ→0 limit gives **0.400→0.560 (1.4×)**,
  **0.160→0.408 (2.6×)**, **0.008→0.464 (58×)**; SC and EC improve alongside
  (TT SC 0.086→0.372); SG invariant at 1.000. No accuracy–explanation trade-off.
- **Baselines (unchanged across all reruns):** DejaVu 0.696/0.848/0.744;
  MonitorRank 0.632/0.656/0.480; CausalRCA 0.624/0.656/0.472; MicroRCA
  0.624/0.648/0.456; BARO 0.536/0.584/0.392; yRCA 0.328/0.256/0.104.
- **§5.8 link arithmetic:** 520 links on OB → 270 mitigation + 85 unmapped
  excluded = **165 scored**, **84 endorsed** (49 at 1.0, 35 at 0.5); 84/165 =
  0.509 is the endorsement rate, 0.403 the pooled strength-weighted mean, and
  **0.266 the reported per-case mean**.
- **§5.10 within-method correlations:** FCP ρ(AC@1, SC) = +0.593/+0.635/+0.197;
  five of seven methods have constant semantic metrics, so pooled correlations
  measured only between-method structure.

---

## 3. Standing rulings register

| Ruling | Content |
|---|---|
| **No re-baselining** | δ = 0.85 is the headline configuration everywhere including the abstract. Low-δ settings are characterised variants. The δ→0 result **may** appear in the abstract and §1 contributions **as a finding**, never as a co-primary configuration. Rationale in the paper: selecting δ on the evaluation benchmark would invalidate the evaluation; held-out selection is future-work item #1. |
| **No forking paths** | No searching for a different fuzzy metric that would show a larger effect; stated in §5.4 as an explicit non-action. Same discipline applies to post-hoc δ selection. |
| **Lexicographic refinement** | §5.7's variant ranks by (−C, −H) with pessimistic scoring over (C,H)-tie blocks — the ε→0 limit of C′ = C − ε(1−H). No ε constant appears in the paper (min non-zero C-gap ≈ 10⁻¹², numerically indefensible). |
| **Dual-channel atoms** | Atoms carry `fuzzy_membership` = Mamdani H(s) **and** `confidence_share` = C(s)/Σ_head C. Both link-weight computations pinned to the share, so the split is numerically neutral (regression-verified: AC@1 0.4000, SG 1.0000, SC 0.2660, EC 0.8240 unchanged). |
| **Silence taxonomy (3 terms)** | **System silence** = no service has evidence, all C = 0 (31/46/31) — the §5.6.2 failure mechanism. **Head silence** = all *reported* atoms have H = 0 (32/46/33) — what the §5.4 identity uses. **Evidence displacement** = head-silent but not system-silent (3 cases) — propagation promoted zero-support services above supported ones. "No-Recommendation" (35/48/48) is a third, weaker condition and is **not** silence. |
| **Provenance disclosure** | **Option A executed**: the 22-individual propagation table was authored 2026-05-12 (`85cbb8d`), during evaluation, concurrently with the coherence metric; the vocabulary and 8 fault prototypes predate it (`32358e8`, 2026-05-04). Disclosed in §3.6/§3.4/§5.8, DEVIATIONS.md and Paper 6 ledger #5. **Option B PENDING**: blind re-derivation by Kosov, 2-week deadline from 2026-08-11, non-gating; protocol in `kosov_validation_protocol.md`, both result-variants pre-drafted. Option C (demote SC) rejected. |
| **S1** ratified | §5.4 defines all four metrics self-containedly (~1 p). The framework paper is unpublished and cannot be leaned on. |
| **S2** ratified | §5.5's independence claim narrowed to *across methods*, with a forward pointer to §5.10's within-method result. |
| **S3** ratified with concession | See "no re-baselining" above. |
| **S4** ratified | §3.5 gains one forward clause pointing to §5.9. |
| **S5** ratified | §1 drafted from the shifted story; δ dose–response promoted to a named contribution. |
| **S6** ratified | Submission-order constraint recorded in the Paper 6 ledger header. |
| **S7** ratified | One canonical phrasing of the ceiling derivation throughout. |
| **S8** ratified | LaTeX-time cross-reference checklist into Appendix F. |
| **§6 operator study** | **NO-GO for v1** — employer permission unconfirmed. Module design retained for the revision round; abstract variant B (without §6) ships; no operator-relevance claims in title or abstract. |
| **AICT conference paper** | Not cited (Option C). §1 carries a disclosure sentence: preliminary 6-page version under review at IEEE AICT 2026, this paper extends it with [aict_delta.md summary]. Upgrade to a proceedings citation only if accepted before submission. |
| **Rule base** | 16 rules / 6 categories is canonical (the harness configuration). The 20-rule/8-category YAML is the conference-paper configuration; the javadoc's "18" is stale. Footnoted in §4.3. |
| **Repo** | Canonical URL `https://github.com/alikmirza/foda-fuzzy-ontology-diagnostics`. The published Tbilisi chapter prints `alik-mirza` — dead link, needs erratum or redirect. Release: tag `v1.0-method-paper`, Zenodo DOI, checklist in Appendix F. |
| **Commits** | No AI-attribution trailers. Plain messages under the author's identity. |

---

## 4. Current state

**Drafted:** §3 (complete), §5.1–5.10 (complete). **§4 is NOT complete** — its
propagation equations (2)–(4), Theorem 1, Theorem 2 and the Corollary are under
the R1–R3 rewrite above; §4.5's worked-example narrative survives but its
supporting mathematics does not. One commit landed (`d485957`) unifying the
scoring convention across the harness.

**Fixed after cold read:** section ordering, stale headers, a broken §4.7
sentence, an appendix that contradicted §5.6.2, the ontology-provenance claim
(the STOP-condition item), plus advisor items A1–A4.

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

**PENDING — unblocked drafting:** S1 definitions; S2/S4/S7/S8 prose; marker fills
(adapter table from DEVIATIONS, Tables 1a–c from the committed CSVs with
bootstrap CIs, TT wall-clock, two repo-resolvable AUTHOR-VERIFYs); §1, §2, §7.

**PENDING — figures:** architecture (§3.1, redraw from scratch — no Springer
artwork reuse), canonical-explanation example (§4.7), Algorithm 1 pseudocode.

**AUTHOR-ONLY:** SLO sources behind the membership-function thresholds; the
independent re-derivation of Theorem 2; the Kosov validation run; confirmation
that the CASCADING_FAILURE surrogate stands in the evaluated configuration.

**Next checkpoint:** cold read v2 on the assembled manuscript once §1/§2/§7 exist
and Fix 8 is closed.

---

## 5. File map

Drafts — `~/research/papers/draft/`: `section3_foda_diagnostickb.md`,
`section4_fcp_algorithm.md`, `section5_evaluation.md`.

Planning — `~/research/papers/outline/`: `method_paper_outline.md` (decision log
lives here), `content_map.md` (REUSE/ADAPT/NEW per subsection), `aict_delta.md`
(non-duplication table).

Notes — `~/IdeaProjects/foda-fuzzy-ontology-diagnostics/paper/notes/`:
`PROJECT_STATE.md` (this file) · `coldread_v1_fixes.md` (master fix tracker) ·
`coldread_findings_v1.md` · `coldread_bundle_v1.md` (assembled §3–§5 + marker
index) · `section5_plan.md` (drafting contract) · `section5_reuse_new_summary.md`
· `silence_definitions.md` · `tt_mechanism_split.md` · `delta_tradeoff_2026-08-11.md`
· `ablation_results_2026-08-10.md` · `sg_fuzzy_verification.md` ·
`section5_7_reframing_proposal.md` · `ontology_provenance_finding.md` ·
`kosov_validation_protocol.md` · `paper6_q2_corrections.md` ·
`canonical_verification_2026-08-10.md`.

Repo — `~/IdeaProjects/foda-fuzzy-ontology-diagnostics/`: `DEVIATIONS.md` (all
adapter and convention deviations) · `RESULTS_PROVENANCE.md` · `results/*.csv` ·
`paper/artifacts/bootstrap_ac1_cis.md` · `ontology/DiagnosticKB.owl` ·
`evaluation/` (harness) · `fuzzy-rca-engine/` (Java reference).

Sources — `~/research/papers/`: `paper6/Paper6_v11_final.docx`,
`AM_LG_PK_AICT2026.pdf`, `Paper_Tbilisi_revised_final.pdf`.

Scratch (session-local, not durable) —
`/private/tmp/claude-501/.../scratchpad/`: ablation and variant CSVs, run logs.
Promote to `results/` with a provenance entry before quoting in the paper.

---

## 6. Process rules in force

1. **Verified, not asserted.** Every claim about the code or data is checked
   against the code or data before it enters a draft. This has caught, so far: a
   scoring-convention bug, a mislabelled membership channel, a false tiebreak
   description, an algebraic identity mistaken for an empirical finding, a
   false ontology-provenance claim, and a central propagation equation that did
   not match its implementation. Assume the next routine check will also bite.
2. **Durable files, not chat.** Any output the author needs to review —
   verification results, plans, REUSE/NEW summaries, findings — is written to
   `paper/notes/`, never left in conversation only.
3. **AUTHOR-VERIFY discipline.** Claims that cannot be checked from the
   repository are marked `[AUTHOR-VERIFY]` inline and listed in the marker index.
   `[NEW-MATH]` marks derivations needing independent re-derivation before
   submission. Neither may be silently resolved.
4. **Stop and report.** Halt immediately and report, before any further work,
   when: a verification contradicts a drafted claim; a measured number differs
   from a locked canonical value; a pre-registered prediction fails; or a
   provenance check comes back negative. Do not absorb surprises into the draft.
5. **Pre-registration.** Where a measurement could be read as tuned, record the
   prediction and its failure condition *before* running it, and report the
   outcome either way. Two such commitments exist in the current draft — one
   fired (§5.4), one did not (§5.7); both are reported.
6. **Repo hygiene.** Result files are regenerated by harness code, never
   hand-edited, and recorded in `RESULTS_PROVENANCE.md` with generating commit,
   scoring convention and seed. Code changes outside an explicit authorisation
   require a ruling first.
