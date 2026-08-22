# §5 REUSE vs NEW — per-subsection summary (drafted pass 1)

Covers the six subsections drafted 2026-08-10 (5.1, 5.2, 5.3, 5.5, 5.6, 5.8).
Verify against `paper/notes/section5_plan.md`.

## 5.1 Research questions — 100 % NEW
No source contains an RQ structure (Paper 6 is framework-first). RQ1–RQ6 written
fresh; RQ4 wording follows the ratified mechanism-(a)-only scope.

## 5.2 Setup — ~60 % REUSE / 40 % NEW
- REUSE (Paper 6 §4.1): three systems with service counts, 125 cases × 5 fault
  types, chance baselines, inject-time-clean rationale, shift-invariance,
  `_latency-50` alias disclosure.
- NEW (from repo `DEVIATIONS.md` N1–N4 + `DESIGN_inject_time_removal.md`, never
  in any paper): hash-positioned window in the middle half, the raise-on-access
  contract, the static no-peeking validator.
- NEW: the scoring-convention paragraph with the +0.048 / +0.072 / +0.024
  inflation figures.

## 5.3 Adapter contracts — ~95 % NEW
Promised but never defined in Paper 6 (reviewer criticism R4). Written from the
adapter sources and the per-method deviation sections. The contract statement
("may reshape, may not invent"), the null-is-signal argument, and the
supervised/log-native comparability flags are all new prose. Adapter table
still to be filled from the deviation log.

## 5.4 Metrics + fuzzy variants — ~100 % NEW (drafted 2026-08-10, pass 3)
- REUSE: compressed crisp SG/SC/EC/ECE definitions from the framework spec (~1 p, placeholder).
- NEW: the membership-weighted SG_fuzzy / SC_fuzzy definitions.
- NEW: the dual-channel correction narrative (share vs Mamdani H) and its
  regression-verified numerical neutrality.
- NEW: measured H-weighted numbers, RE1-OB — SG 1.000 -> 0.744, SC 0.266 ->
  0.236, yRCA 0.267 -> 0.253.
- NEW: pre-registered prediction + its FAILURE reported verbatim, with the
  stated failure condition that fired (share 0.752 vs H 0.744, delta 0.008).
- NEW: the named finding — grounding is GATED, not graded (H bimodal: median
  0.820 firing, 0 in silence); 36/465 atoms over 26 cases with share>0 and H=0
  (mem 16, cpu 12, delay 5, disk 2, loss 1) — "propagation asserts, rule base
  disowns."
- NEW: three-instrument convergence paragraph (§5.4 / §5.6.2 / §5.9 read one
  phenomenon) with the non-independence caveat.
- NEW: R2 closure in honest form + explicit statement that no alternative
  fuzzy-metric search was conducted (forking-paths discipline).

## 5.5 Headline results — numbers REUSE-from-artifacts, prose ~80 % NEW
- Numbers: all from `results/phase2_integration_headline_*.csv` and
  `paper/artifacts/bootstrap_ac1_cis.md` at `d485957` (regenerated, not copied
  from Paper 6).
- REUSE (Paper 6 §4.2 framing): the two-group split observation, the
  floor-versus-grounded language, yRCA's monotone SG decline.
- NEW: supervised/unsupervised separation as an explicit reporting class (R5);
  the "SG = 1.000 is a design property, stability is the finding" reframing
  (this is the R1 circularity answer); TT presented with its CI per amendment 1a.

## 5.6 Mechanism decomposition — ~40 % REUSE / 60 % NEW
- REUSE (Paper 6 §4.5): the Noisy-OR density argument (3 neighbours vs 10–20),
  the 43-distinct-top-1 and 25.8 % fingerprint, the two alternative-hypothesis
  eliminations, ground-truth H ≈ 0.95.
- NEW: the entire two-mechanism structure (87 / 31 / 6) from
  `tt_mechanism_split.md`; the silence mechanism, absent from every source; the
  calibration cross-evidence (ECE 0.219 → 0.243 as confidently-wrong evidence);
  the corrected scope of the H claim (93/124, not all — Paper 6 correction #2);
  §5.6.4's three conclusions.

## 5.7 Mitigation — ~100 % NEW (drafted 2026-08-10, pass 2)
- NEW: the impossibility opener (pessimistic AC@1 invariant to within-block
  order; gt rank = block size) — a methodological point no source contains.
- NEW: the lexicographic (C, H) formulation with the one-sentence
  acknowledgment that C' = C - eps(1-H) coincides in the eps -> 0 limit, plus
  the numerical justification (min non-zero C-gap ~1e-12 on RE1-TT).
- NEW: post-hoc disclosure paragraph (designed after observing TT failure
  structure; no held-out system; characterized variant; as-shipped stays
  headline).
- NEW: ceiling derivation 30 in-block / 26 loose / 18 strict / 8 lost to
  H-ties -> 19/125 = 0.152, with the +1 identified as the single
  already-correct case (ts-travel-service disk).
- NEW: mechanism (b) zero-headroom confirmed two ways (H = 0 everywhere;
  strict scoring rescues none of the 31 vacuous ties).
- [MEASURED-TBD] slot with the pre-written honest-negative explanation.
- Only REUSE: the 0.744 DejaVu comparator from the committed headline tables.

## 5.8 Self-coherence — ~100 % NEW analysis
Paper 6 reports FCP's SC values but never analyses them (reviewer criticism
R6). New: the correlation-topology-vs-curated-table account of the gap; the
two readings and the argument for not filtering links through the ontology
(which would make the metric vacuous); the density explanation of the
0.266 → 0.086 decline; the ontology-work-not-link-suppression conclusion.

## Open items inside the drafted text
1. §5.3 adapter table — fill from `DEVIATIONS.md` per-method sections.
2. §5.5 Tables 1a–c — typeset from the committed CSVs with CIs.
3. ~~§5.6.2 per-fault breakdown of the 31 silence cases~~ — RESOLVED: mem 8, delay 7, disk 7, cpu 5, loss 4; the draft's earlier "predominantly packet-loss and latency" guess was wrong and has been corrected to "spread across all five fault types."
4. §5.8 link counts (165 Fault→Fault / 84 endorsed) — [AUTHOR-VERIFY] against
   current per-case data; the figure comes from the deviation log.

## Pass-2 additions (2026-08-10)
- §5.7 drafted (above).
- §5.6.2 corrected with the measured per-fault silence distribution.
- Refined-variant measurement queued for all three systems (ruling 4), log
  `scratchpad/refined_variant.log`; fills the [MEASURED-TBD] slot.
