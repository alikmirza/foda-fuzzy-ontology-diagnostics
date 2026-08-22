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
> **Disk state at this moment:** no draft file has been modified. The 2026-08-22
> fix sequence (MF-8/S2 → S1 → MF-1/2/3 → MF-6 → MF-7 → S4 → S7 → Fix 8a → 8b →
> 8c → 8d → SF-1..4 → §1/§2/§7) is HELD at item 10, items 1–9 not started.
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
| Fix 8a Theorem 1 W = 1 repair | **PENDING** | strict contraction (1−δ)+δ(1−H(s))·W_s < 1 where H > 0 or W_s < 1; H = 0 + full budget residual gets the damping-only argument, to be noted as *common* (system-silent services, 25–37 % of cases) rather than pathological; Corollary recomputed |
| Fix 8b Theorem 2 Perron–Frobenius | **PENDING** | name the entrywise-nonnegativity → monotonicity-of-ρ → eigenvalue-shift steps, three lines |
| Fix 8c worked example re-derivation | **PENDING** | fresh independent script; check against C\* = (0.7255, 0.5271, 0.5453) |
| Fix 8d confidence formula + correlation-graph params | **PENDING** | extract verbatim from adapter source (markers 14 and 7) |

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
