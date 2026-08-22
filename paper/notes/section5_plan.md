# §5 Drafting Contract (author + advisor review copy)

**Status:** v2, 2026-08-10 — expanded from the v1 plan after the
pessimistic-convention unification (commit `d485957`) and the RE1-TT
failure-mechanism decomposition. **§5 must not be drafted until this contract
and the §5.7 reframing proposal are ratified.**

Target: ~8.5 pp of a ~29.5 pp v1 manuscript (EMSE first).

## Locked inputs (nothing in §5 may contradict these)

| Quantity | RE1-OB | RE1-SS | RE1-TT |
|---|---|---|---|
| FODA-FCP AC@1 | 0.400 | 0.160 | **0.008** (below 1/64 ≈ 0.0156) |
| FODA-FCP ECE | 0.119 | 0.051 | 0.243 |
| FODA-FCP SG | 1.000 | 1.000 | 1.000 |
| FODA-FCP SC | 0.266 | 0.158 | 0.086 |
| FODA-FCP EC | 0.824 | 0.749 | 0.789 |
| Chance baseline | 0.083 | 0.067 | 0.016 |

Convention: pessimistic tie handling (worst rank in tie block) for AC@1 **and**
the ECE correctness label. Provenance: every number traces to a file in
`results/` listed in `RESULTS_PROVENANCE.md` at commit `d485957`.

## Subsection order, numbers, and provenance

| § | Content | Numbers appearing here | Source |
|---|---|---|---|
| 5.1 Research questions | RQ1 ranking accuracy vs 6 baselines (supervised/unsupervised separated); RQ2 explanation quality; RQ3 scale behaviour + failure mechanism; RQ4 mitigation headroom; RQ5 parameter sensitivity; RQ6 calibration | none | **NEW** (Paper 6 is framework-first, not RQ-first) |
| 5.2 Setup | 3 systems (12/15/64 services), 125 cases each = 375, 5 fault types, chance baselines, inject-time-clean contract, shift-invariance S(M)=0, `_latency-50` alias | structural constants only | **REUSE** Paper 6 §4.1 + **NEW** from repo `DEVIATIONS.md` N1–N4 (hash-positioned window, inject_time hiding) |
| 5.3 Fair-extraction adapter contracts | one table: 7 adapters × what each populates/cannot populate; anti-peeking validator; fairness argument (absent ≠ zero-quality) | none | **NEW** (writing task over `DEVIATIONS.md` per-method sections + `evaluation/methods/*.py`) — closes reviewer criticism R4 |
| 5.4 Metrics | compact SG/SC/EC/ECE restatement + fuzzy-integrated variants (membership-weighted SG, graded π in SC) | crisp-vs-fuzzy variant comparison (pending that run) | **ADAPT** Paper 6 §3.2–3.5 (Algorithms 1–3 compressed) + **NEW** fuzzy integration — closes R2 |
| 5.5 Headline results | 3 tables, all 7 methods × 5 metrics, 95% bootstrap CIs (n=10,000, seed 42); supervised (DejaVu) separated from unsupervised band; yRCA modality caveat; footnote stating the tie convention and the naive-scoring inflation it avoids (+0.048/+0.072/+0.024) | **the full locked set above**, plus DejaVu 0.696/0.848/0.744, yRCA 0.328/0.256/0.104, and the other baselines | **NEW tables** from `results/phase2_integration_headline_*.csv` + `paper/artifacts/bootstrap_ac1_cis.md`; presentation **ADAPT** Paper 6 §4.2 — closes R5 |
| 5.6 Failure-mechanism decomposition | **two-mechanism structure (mandated)** — see next section | 124 failures = **(a) 87 / (b) 31 / residual 6**; fingerprint 43 distinct top-1, 25.8% most-frequent; H median 0.950 for (a), 0.000 for (b); ECE 0.219→0.243 cross-evidence | **REUSE** Paper 6 §4.5 Noisy-OR analysis (Eq. 13, neighbour counts, alternative-hypothesis elimination) + **NEW** mechanism split from `paper/notes/tt_mechanism_split.md` |
| 5.7 Mitigation | local-H **score refinement** (ε → 0 lexicographic form), mechanism (a) only — **RATIFIED 2026-08-10** | ceiling **0.008 → 0.152** (locked); 30 in-block / 26 loose / 18 strict / 8 lost to H-ties; mechanism (b) headroom = 0 (two independent confirmations); measured gain [MEASURED-TBD] | **NEW** engineering + measurement — closes R7 |
| 5.8 Self-coherence | why FCP's own links disagree with its own propagation table; decomposition of emitted links; fix-vs-account decision | SC 0.266 → 0.158 → 0.086; 31.7% of FCP links are Fault→Fault (165/520), 84/165 ontology-endorsed | **NEW** analysis over `results/phase2_semantic_coherence.csv` + `DEVIATIONS.md` SC design history — closes R6 |
| 5.9 Sensitivity | τ ∈ {0.5…0.9} × SG/EC; B ∈ {5,10,15,20} × ECE; δ ∈ {0.5…1.0} × FCP AC@1/SG/SC/EC; ranking-inversion check | from the running ablation job (OB + SS complete, TT running) | **NEW** runs — closes R8 |
| 5.10 Calibration | per-fault ECE regimes; within-method / mixed-effects correlation treatment replacing Paper 6's pooled 875-pair Spearman | per-fault ECE tables; corrected correlations | **ADAPT** Paper 6 §4.4 re-angled on FCP + **NEW** statistical treatment — closes R9 |

## Where the (a)/(b) split lands

§5.6 is organised *by mechanism*, not by narrative:

- **5.6.1 Saturation (a)** — 87 of 124 TT failures (70%). C ties at exactly
  1.000 across blocks of 2–30 services; ground-truth H median 0.950. Carries
  the Paper 6 Noisy-OR account and the re-verified fingerprint. Calibration
  cross-evidence: ECE worsens 0.219 → 0.243 under honest scoring because
  saturated blocks carry maximal confidence — the method is *confidently*
  wrong at scale.
- **5.6.2 Silence (b)** — 31 of 124 (25%). C = 0.000 for all 64 services; no
  Mamdani rule fires anywhere; ground-truth H = 0.000 in 31/31. Rule-coverage
  territory, not ranking pathology.
- **5.6.3 Residual** — 6 of 124 (5%). Unique top-1 at C = 1.000 with ground
  truth outside the block: propagation-topology errors.
- **Correction carried forward:** Paper 6's blanket "ground-truth H = 0.88–0.95
  on failures" holds for (a) + residual only (93/124). §5.6 states the split
  from the start; Paper 6 gets the caveat at its Q2 revision.

§5.7 then addresses **only** mechanism (a); §5.6.2 explicitly hands mechanism
(b) to Future Work (§7) as Mamdani rule-coverage work (Paper-8), together with
density-aware damping and log-pool aggregation.

## Drafting invariants

1. Every number traces to a `results/` file recorded in `RESULTS_PROVENANCE.md`.
2. Pessimistic convention everywhere; no naive-convention value appears
   without being labelled as such.
3. No forward references to §6 (NO-GO for v1); operator validation is Future
   Work only.
4. The AICT conference version is never cited — prose reference only, with the
   disclosure sentence in §1.
5. TT is described as **below the chance baseline**, not "near-chance."
   **[Amendment 1a, ratified 2026-08-10]** Wherever TT's headline AC@1 appears,
   present it as: *"0.008, below the 1/64 ≈ 0.016 chance baseline (95% CI
   [0.000, 0.024])"* — the CI is displayed because it straddles chance; the
   claim rides the point estimate. This applies to §5.5, §5.6, the abstract,
   and §1.
7. **[Amendment 1b]** §5.4's crisp-vs-fuzzy metric comparison run is queued
   behind the TT ablations (detached; log path recorded in the run ledger
   below). §5.4 is drafted only when that run lands.

## Run ledger (detached jobs feeding §5)

| Job | Feeds | Log | Status |
|---|---|---|---|
| τ/B/δ ablations | §5.9 | `scratchpad/ablations.log` | OB + SS complete; TT running |
| strict-ceiling recompute | §5.7 | `scratchpad/strict_ceiling.log` | running (ruling 2a) |
| crisp-vs-fuzzy metrics | §5.4 | `scratchpad/fuzzy_metrics.log` | queued behind ablations |
6. Reviewer-criticism coverage is explicit: R2 (5.4), R4 (5.3), R5 (5.5),
   R6 (5.8), R7 (5.6–5.7), R8 (5.9), R9 (5.10).
