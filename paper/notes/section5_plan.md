# §5 Drafting Plan (for author sanity check before drafting)

**Status:** written 2026-08-10, after the pessimistic-convention unification and
the RE1-TT mechanism decomposition. §5 target length ~8.5 pp of a ~29.5 pp v1.

## Subsection order and which numbers appear where

§5 opens with **5.1 Research questions** (RQ1 ranking accuracy vs 6 baselines with
supervised/unsupervised reported separately; RQ2 explanation quality; RQ3 scale
behaviour and failure mechanism; RQ4 mitigation headroom; RQ5 parameter
sensitivity; RQ6 calibration) — no numbers. **5.2 Setup** carries the structural
constants only: 3 RCAEval systems (12 / 15 / 64 services), 125 cases each, 375
total, 5 fault types, chance baselines 1/12 ≈ 0.083, 1/15 ≈ 0.067, 1/64 ≈ 0.016,
the inject-time-clean contract and the `_latency-50` alias. **5.3 Fair-extraction
adapter contracts** is prose + one table (7 adapters × what each populates),
no metrics. **5.4 Metrics** restates SG/SC/EC/ECE compactly and introduces the
fuzzy-integrated variants (membership-weighted SG, graded π in SC) — the numbers
here are the *crisp vs fuzzy* variant comparison, pending that run. **5.5
Headline results** is where the locked canonical set lands, three tables with
95 % bootstrap CIs (n = 10,000, seed 42): FCP AC@1 **0.400 / 0.160 / 0.008**,
ECE **0.119 / 0.051 / 0.243**, SG **1.000** on all three, SC 0.266 / 0.158 /
0.086, EC 0.824 / 0.749 / 0.789, alongside the six baselines (DejaVu 0.696 /
0.848 / 0.744 top on AC@1 everywhere; yRCA 0.328 / 0.256 / 0.104 as the other
explanation-side method); a footnote states the pessimistic tie convention and
the +0.048 / +0.072 / +0.024 inflation naive scoring would produce; TT is
explicitly **below the 1/64 chance baseline**. **5.6 Failure-mechanism
decomposition** carries the two-mechanism split of the 124 TT failures —
**(a) saturation 87 (70 %)**, **(b) silence 31 (25 %)**, residual 6 — plus the
re-verified fingerprint (43 distinct top-1, most-frequent 25.8 %, ground-truth H
median 0.950 for (a), 0.000 for (b)) and the calibration cross-evidence
(ECE 0.219 → 0.243 under honest scoring ⇒ confidently wrong at scale).
**5.7 Mitigation** reports local-H **score refinement** against mechanism (a)
only: ceiling **0.008 → 0.232** (28 of 30 in-block ground truths rescuable),
measured gain TBD, mechanism (b) headroom provably zero. **5.8 Self-coherence**
analyses why FCP's SC is 0.266 → 0.086 (its own links vs its own propagation
table; DEVIATIONS records 31.7 % of FCP links are Fault→Fault, 84/165 ontology-
endorsed). **5.9 Sensitivity** reports τ ∈ {0.5…0.9} × SG/EC, B ∈ {5,10,15,20} ×
ECE, δ ∈ {0.5…1.0} × FCP AC@1/SG/SC/EC, with a ranking-inversion check (job
queued). **5.10 Calibration** closes with per-fault ECE regimes and the
within-method / mixed-effects correlation treatment replacing Paper 6's pooled
875-pair Spearman.

## Invariants for drafting
- Every number traces to a file under `results/` recorded in RESULTS_PROVENANCE.md.
- Pessimistic convention everywhere; no naive-convention value appears without
  being labelled as such.
- No forward references to §6 (NO-GO for v1); operator validation is Future Work.
- The AICT conference version is never cited — prose only, disclosure in §1.
