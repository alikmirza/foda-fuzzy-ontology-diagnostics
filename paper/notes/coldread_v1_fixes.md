> **BLOCKED 2026-08-22 — see `STOP_propagation_equation_finding.md`.**
> Fix 8c's re-derivation showed that §4.4's printed equations (2), (3), (4) are
> not the implemented algorithm. The implementation applies δ as a per-edge
> attenuator inside the Noisy-OR product and has no `(1−δ)·C_prev(s)` term;
> the printed form gives C\* = (0.7706, 0.6095, 0.6316) in 19 iterations against
> the asserted (0.7255, 0.5271, 0.5453) in 14. Consequences: eqs (2)/(3)/(4),
> Theorem 1, Theorem 2, the Corollary and §5.9's mechanism sentence are all
> affected, and **the ratified Fix 8a repair is withdrawn pending ruling** — the
> W = 1 boundary case it repairs does not exist for the actual operator
> (ρ ≤ δ·max(1−H)·W ≤ δ < 1 for all δ < 1, W ≤ 1, any H). δ = 1 is the sole
> boundary case.
>
> **UNBLOCKED 2026-08-22 by ruling; Part 1 Tasks 1–3 executed.** Equations,
> theorems and the re-derivation are now on the corrected operator; see the
> R1/R2/R3 rows below. The rest of the 2026-08-22 fix sequence (MF-8/S2 → S1 →
> MF-1/2/3 → MF-6 → MF-7 → S4 → S7 → SF-1..4 → §1/§2/§7) remains to be done.
> Fix 8d marker 14 (confidence formula) IS resolved — verbatim extraction in the
> STOP note. Marker 7 (correlation-graph parameters) remains open.
>
> Cold read v2 findings against the on-disk text: `coldread_findings_v2_partial.md`.

# Cold-read v1 — consolidated fix tracker

Every item from both cold reads (A1–A6 advisor, F1–F5 + S1–S8 drafter),
plus Fix 5, Fix 8 and the marker fills, mapped to resolution and evidence.
Status as of 2026-08-11.

## A-execution (ontology provenance) — COMPLETE

| item | resolution | evidence |
|---|---|---|
| §3.6 correction | Rewritten: vocabulary + 8 prototypes predate the benchmark (`32358e8`, 2026-05-04); the 22-individual propagation table does not (`85cbb8d`, 2026-05-12), authored concurrently with the coherence metric because that metric needed a fault-typicality reference. Both commits cited inline. Two safeguards stated (zero benchmark vocabulary; no transitive closure). | `section3_foda_diagnostickb.md` §3.6 |
| §3 opening | "a benchmark the ontology was not tuned to" removed; replaced with a two-layer provenance pointer to §3.6. | §3 intro ¶ |
| §3.4 framing | "curated"/prior framing dropped; now "curated domain knowledge whose authorship timing is disclosed in §3.6 and analysed in §5.8". | §3.4 |
| §5.8 rewrite | New opening paragraph: the check is against a concurrently-authored table, stated plainly; direction-of-result argument added (a flattering table would give high SC; measured SC is low and declining); independent re-derivation flagged as under way. Two-readings analysis and all numbers unchanged. | §5.8 ¶1–2 |
| DEVIATIONS.md | Provenance entry with the full six-row timeline table, consequences, safeguards, and pointer to the validation protocol. | `DEVIATIONS.md` |
| Paper 6 ledger | Correction #5 added (same disclosure required at Paper 6 revision). | `paper6_q2_corrections.md` |
| A6 grep-sweep | No surviving "prior"/"independent" claim applied to the propagation table in drafts, outline or notes. Two hits reviewed and cleared: the new disclosure paragraph itself, and an unrelated use of "independent" (SG's invariance to δ). | grep verified |
| Option B spec | Blind protocol written: materials to provide/withhold, three agreement measures, both result-variants pre-drafted, interpretation guardrail for a low-overlap outcome. | `kosov_validation_protocol.md` |

## Advisor items

| item | status | resolution |
|---|---|---|
| **A1** silence = two phenomena, three counts | **COMPLETE** | Two terms introduced: **system silence** (no service has evidence; all C = 0) and **head silence** (all *reported* atoms have H = 0). Counts: system 31/46/31, head 32/46/33, no-Recommendation 35/48/48. The §5.4 identity uses head silence and reproduces SG_fuzzy exactly. **Gap cases diagnosed** — 3 cases (OB 1, TT 2) where the method had evidence but propagation promoted zero-support services above it; named **evidence displacement**. `re1-ob_cartservice_mem_2` is the cleanest instance: the only service with rule support was the ground truth, and it was displaced out of the reported top-3. Terminology applied in §5.4, §5.6.2, §5.9; case IDs recorded. **Also flagged:** measured no-Recommendation on OB is 35, not the 31 Paper 6 states — candidate Paper 6 correction #6. | 
| **A2** §5.9 monotonicity overstated | **COMPLETE** | Restated as monotone *from the shipped setting downward*; non-monotonicity above it reported explicitly (TT SC 0.086 → 0.172, EC 0.789 → 0.827 at δ = 1.0, minimum near δ ≈ 0.7–0.75), with no mechanism claim. Dominance conclusion re-grounded on the δ ≤ 0.2 region. Same qualifier added to §4's framing note. |
| **A3** 84/165 vs SC = 0.266 | **COMPLETE** | Exact arithmetic measured and written into §5.8: 520 links on OB → 270 mitigation (excluded) + 85 unmapped (excluded) = **165 scored**, of which **84 endorsed** (49 at 1.0, 35 at 0.5). So 84/165 = 0.509 is the endorsement *rate*; the strength-weighted pooled mean is 0.403; the reported 0.266 is the **mean of per-case means**, lower because cases weight equally regardless of link count. Marker 23 resolved — the 165/84 deviation-log figures are correct at current head. |
| **A4** pooled-ρ vs Paper 6 published | **COMPLETE** | Determined to be recomputation, not misquote: Paper 6 published −0.190/+0.107/−0.015 (commit `f6bf9d3`); the −0.216/+0.111/−0.010 in §5.10 come from the regenerated pessimistic-convention data. §5.10 sentence rewritten to state both and attribute the shift to the convention change. |
| A5 | folded into the A-execution table above | |
| A6 | grep-sweep, see A-execution table | |

## Drafter items

| item | status | resolution |
|---|---|---|
| F1 §5.9 printed before §5.8 | FIXED | order restored 5.7 → 5.8 → 5.9 → 5.10 |
| F2 stale §5 header | FIXED | v0.2, all ten drafted |
| F3 stale status table | FIXED | four rows corrected |
| F4 §4.7 broken sentence | FIXED | fragment repaired |
| F5 Appendix I contradicted §5.6.2 | FIXED | "loss/delay-dominated" replaced with the measured spread; supersession noted |
| S1 self-contained definitions | **PENDING** | ratified; ~1 p to write into §5.4 using A1 terminology |
| S2 §5.5/§5.10 contradiction | **PENDING** | ratified: narrow §5.5 to across-methods + forward pointer |
| S3 δ headline concession | **PENDING** | ratified: δ→0 may appear in abstract/§1 **as a finding**, never as co-primary config |
| S4 §3.5 forward clause | **PENDING** | one clause pointing to §5.9 |
| S5 §1 from shifted story | **PENDING** | step 10; δ dose-response promoted to named contribution |
| S6 submission-order constraint | **DONE** | header added to `paper6_q2_corrections.md` |
| S7 canonical ceiling derivation | **PENDING** | one phrasing for 18/19, 0.144 vs 0.152, 17+1 |
| S8 LaTeX-time checklist | **PENDING** | to Appendix F |

## Fix 5 / Fix 8

| item | status | note |
|---|---|---|
| Fix 5 git verification | **COMPLETE — claim refuted, A executed** | see A-execution above; this was the STOP-condition item |
| **R1** Eqs. (2)–(4) rewritten to the implemented operator | **DONE 2026-08-22** | §4.4 rewritten in `~/research/papers/draft/section4_fcp_algorithm.md`: δ is a per-edge attenuator *inside* the Noisy-OR product, no `(1−δ)·C_prev(s)` term, H(s) a per-iteration anchor, clamp made explicit; the "both formulations converge to the same fixed point on DAGs" sentence re-anchored to the shared formula and differing sweep order. Verified: 0 occurrences of `(1 − δ) · C` remain in §4.4. |
| **Fix 8a** (former ratified repair) | **WITHDRAWN, NOT WRITTEN** | The W = 1 boundary case does not exist for the actual operator (ρ = δ·max(1−H)·W ≤ δ < 1 for all δ < 1, any W ≤ 1, any H). Verified absent from the draft: 0 matches for "W = 1 boundary", "damping-only argument", "25–37". |
| **R2** Theorem 1 restated | **DONE 2026-08-22** | §4.5: ρ = δ·max(1−H)·W ≤ δ, strict contraction for every δ < 1 regardless of W and H, proof via ∂P/∂C(t) ≤ δ·w(s,t) plus non-expansive clamp. W = 1 written as the *ordinary* case; H = 0 services noted as common (a quarter to a third of the benchmark) but harmless. Sole degenerate case δ = 1 stated, with a pointer that §5.9 must disclose it. Corollary recomputed: worst case ρ = 0.85 → N = 85; the old "≈ 30 iterations" is not re-attributed. |
| **R3 / Fix 8b** Theorem 2 on the corrected Jacobian | **DONE 2026-08-22** | §4.5: no `(1−δ)𝟙[s=t]` diagonal; four Perron–Frobenius steps named explicitly (entrywise non-negativity → entrywise domination → monotonicity of ρ on non-negative matrices → positive homogeneity). `[NEW-MATH]` marker retained and re-scoped to the corrected statement. Verified: 0 matches for the stale 0.626. |
| **Fix 8c** worked-example re-derivation | **CLOSED — NO STOP** | Fresh script `paper/notes/fix8c_rederive_corrected.py` (does not reuse `fix8c_rederive.py`). Reproduces C\* = (0.7255, 0.5271, 0.5453) and the 10-dp values, 14 iterations at ε = 10⁻⁶, both bounds 0.476, true ρ(J) = 0.3614, and the geometric-mean identity 0.85 · 0.7 · 0.6073 = 0.3614 — **verified numerically before being written into §4.5**. Run recorded in `paper/notes/fix8c_closure.md`. |
| **Narrative correction** (worked example) | **DONE 2026-08-22** | §4.5 no longer claims the local bound is much tighter than the global one: on a uniform cycle ρ(W̃) = W so the two coincide at 0.476. The example's value is restated as ρ(J) = 0.3614 predicting the observed 14 iterations (bound predicts 19), with the gap attributed to worst-case max(1−H) = 0.8 versus the geometric mean 0.6073. |
| Fix 8d confidence formula (marker 14) | **RESOLVED** | verbatim extraction in `STOP_propagation_equation_finding.md` §5; still to be written into §4.6 and §5.3's deviation list |
| Fix 8d correlation-graph params (marker 7) | **RESOLVED** | Not pending — the full extraction is in `CLAUDE_CODE_EXECUTION_PROMPT.md` Task 6 (R6): `_infer_topology`, `topology_threshold = 0.5`, `lag = 1`, directed edge u→v weighted \|lagged_corr(u,v)\| admitted at ≥ threshold with u leading v (`w_uv ≥ w_vu`), self-loops excluded, per-service signal = highest-\|z\| among cpu/mem/latency/error/traffic with the documented no-deviation fallback, docstring confirming the shared convention with MicroRCA and yRCA. Written into §4.1 by Task 6. |

## Marker fills (step 9)

| marker | status |
|---|---|
| 18 adapter table | PENDING — fill from `DEVIATIONS.md` per-method sections |
| 20–22 Tables 1a–c | PENDING — typeset from committed CSVs with bootstrap CIs |
| 16 TT wall-clock | PENDING — from harness logs |
| 23 §5.8 link counts | **RESOLVED** by A3 (165 scored / 84 endorsed confirmed) |
| 2 competency questions, 3 CASCADING_FAILURE surrogate | PENDING — repo-resolvable |
| 8 SLO sources | **AUTHOR-ONLY** — provenance of the calibration thresholds is not in the repository |
| 1, 5, 17 header markers | cosmetic, resolve at typesetting |

## Remaining author-only items

1. SLO sources behind the membership-function thresholds (marker 8).
2. Independent re-derivation of Theorem 2 before submission (marker 13).
3. Kosov validation run (Option B, two-week deadline, non-gating).
4. Confirmation that the CASCADING_FAILURE surrogate stands in the evaluated
   configuration (marker 3) — repo-checkable but a design decision to own.


---

# Part 1 Tasks 4–7 — 2026-08-22

Evidence paths are relative to `~/research/papers/draft/` for sections and to the
repository root otherwise.

## Review corrections C1–C3 (from `review_tasks1_3.md`)

| item | resolution | evidence |
|---|---|---|
| C1 degenerate case too narrow | "H ≡ 0" replaced by **min_s H(s) = 0** throughout Theorem 1; stated as the *typical* profile, not a corner (system silence 25–37 % of cases, and outside silence most cases still contain a service the rule base does not fire on); δ = 1 disclosure given the extra clause that the non-expansive regime is the normal condition there | `section4_fcp_algorithm.md` §4.5 |
| C2 ceiling off by one | verified numerically: log(10⁻⁶)/log(0.85) = 85.0086, 0.85⁸⁵ = 1.0014 × 10⁻⁶ > ε, so **N = 86**; other two (18.61 → 19, 13.57 → 14) confirmed correct and left | §4.5 Corollary |
| C3 tightness condition backwards | replaced with "strictly tighter whenever the **row sums are unequal** — a uniform cycle … is precisely the case in which the two coincide" | §4.5, after Theorem 2 |

## Task 4 (R4) — disclosure and errata

| item | resolution | evidence |
|---|---|---|
| DEVIATIONS entry | full mis-transcription record: printed vs implemented form, how it surfaced (Fix 8c), the (0.7706…) vs (0.7255…) disagreement, ruling that source is canonical, artifacts affected, what is unaffected, closure pointer | `DEVIATIONS.md` § "Propagation equations: manuscript mis-transcription" |
| AICT errata | placeholder created, marked **AUTHOR-ONLY — pending**; structured as claim-as-printed / corrected form / action required / decision; explicitly does not guess what AICT printed | `paper/notes/aict_errata.md` |
| Paper 6 assessment | **it does restate them** — Eq. (13) prints `C(s) = 1 − ∏(1 − H(n)·edge_weight(n,s))`, which omits δ, uses the neighbour's *local* H where the code uses propagated C, and drops the (1 − H(s)) anchor. Different from the journal draft's error (Paper 6 has no (1−δ) term anywhere). No Paper 6 number moves. | ledger correction **#7**; #6 is the pre-existing no-Recommendation item, now written up properly and left open |

## Task 5 (R5) — language sweep

| item | resolution | evidence |
|---|---|---|
| §5.9 mechanism sentence | convex-mixing sentence replaced: δ multiplies the confidence each edge transmits; lowering δ attenuates edges uniformly | §5.9 damping paragraph |
| δ = 1 disclosure | added in the sweep's setup: Theorem 1 gives only non-expansiveness at δ = 1, the profile that triggers it is typical, convergence there is **empirical**, implementation returns the last iterate after MAX_ITER, and it did close on every case here | §5.9 |
| §4 framing note | propagation described as δ-attenuated transmission; MF-2 basin qualification added | §4 framing note |
| §3.5 propagation row | "Damped Noisy-OR" → Noisy-OR over δ-attenuated edges; S4 forward clause to §5.9 added in the same edit | §3.5 table |
| §5.7 untouched — **verified, not assumed** | both loads re-read: the impossibility claim rests on the scoring convention and makes no reference to how C was produced; the ceiling rests on code-produced C and H, independently re-derived 2026-08-22 with all values reproducing | `paper/notes/r5_sweep_verification.md` |
| residual sweep | 0 occurrences of `(1 − δ)·C`, `convex`, `blend` remain in §3, §4, §5 | grep verified |

## Task 6 (R6) — markers 14 and 7

| item | resolution | evidence |
|---|---|---|
| marker 7 (correlation-graph parameters) | tracker corrected — was never pending; written into §4.1: threshold 0.5, lag 1, edge u→v weighted \|lagged_corr\|, stronger-lead disambiguation, self-loops excluded, highest-\|z\| representative signal with documented fallback, > lag+1 sample requirement, shared convention with MicroRCA/yRCA | §4.1; `[AUTHOR-VERIFY]` removed |
| marker 14 (confidence formula) | resolved in the STOP note; **still to be written into §4.6 and §5.3's deviation list** | pending — carried to the next round |

## Task 7 — held items

| item | resolution | evidence |
|---|---|---|
| MF-8 / S2 | §5.5's independence claim narrowed to **across methods**, with the within-method coupling explicitly excluded and pointed to §5.10 | §5.5 |
| S1 | placeholder replaced with ~1 page defining SG, SC, EC and ECE self-containedly, plus the system/head silence terms | §5.4 |
| MF-1 | monotonicity framing replaced by **dominance**: interior optimum on OB, flat step on TT, plateau on SS all stated; δ ≤ 0.2 beats shipped on every axis on all three systems with the nine values quoted | §5.9 (i) |
| MF-2 / MF-3 | two-sided basin δ ∈ [0.5, 0.85] written with the full TT step sequences; minima stated separately (SC 0.074 at δ = 0.75, EC 0.763 at δ = 0.65); "coherence rises with the same damping" and "completeness rises or holds" both removed | §5.9 (iii); §4 framing note |
| MF-6 | both dangling pointers now land — new §5.9 (iv) covers system silence as inert under damping and evidence displacement with the `re1-ob_cartservice_mem_2` exemplar | §5.9 (iv) |
| MF-7 | §6′.1 reference redirected to §7 | §5.5 |
| S4 | §3.5 forward clause to §5.9 | §3.5 |
| S7 | one canonical phrasing everywhere: 19/125 = 0.152 and 18/125 = 0.144; verified 3 occurrences of each, 0 of the old variants | §5.7 ×3 |
| SF-1 | ceiling sentence scoped to δ = 0.85, with the higher-δ refined values (0.192, 0.208) named and pointed at Appendix D | §5.7 |
| SF-2 | re-verified the parse (22 individuals, **0 self-pairs**) then edited: denominator 8 × 7 = **56**, remainder **34**, self-propagation stated as not represented | §3.4 |
| SF-3 | **count is exactly 4 — no STOP.** Partition verified per case: 18 strict / 8 tied / 4 strictly below the block maximum, 18+8+4 = 30 and loose 26 = 18+8 both hold. Missing category written into §5.7 with its distinct consequence (promoting by H would select the wrong service) | `paper/notes/sf3_block_decomposition.md`; §5.7 |
| SF-4 | the count does **not** surface in §5 — §5.5's completeness sentence is qualitative. Recorded here per spec: **Paper 6 correction #6 (no-Recommendation 35 vs 31) has no anchor in this manuscript's text**, and no contested number was imported to create one | §5.5 |
| marker 18 (adapter table) | written from source. **Corrected two prose claims in the process:** links are emitted by **six** of seven methods (only MonitorRank emits none), not four; and an ontology-class string is written by **three** adapters — DejaVu mints `foda:Service/…` and `foda:FailureType/…` in its own namespace, which resolve to nothing in DiagnosticKB and so score zero, correctly | §5.3 |
| markers 20–22 (Tables 1a–c) | typeset from `results/phase2_integration_headline_*.csv` with CIs from `paper/artifacts/bootstrap_ac1_cis.md`; locked values verified present (0.400 [0.320, 0.488], 0.160 [0.096, 0.232], 0.008 [0.000, 0.024]) | §5.5 |
| marker 3 | resolved from source — `foda_fcp.py:127` maps CASCADING_FAILURE → ResourceContention, so the surrogate is in the evaluated configuration | §3.3 |
| marker 2 | narrowed rather than closed: the CQ list is accurate as a description of the query surface; whether these were the *design-time* questions is author knowledge | §3.2 |
| marker 16 (TT wall-clock) | **not done** — needs a timing run | pending |
| marker 8 (SLO sources) | **AUTHOR-ONLY**, untouched, not invented | §4.2 |
