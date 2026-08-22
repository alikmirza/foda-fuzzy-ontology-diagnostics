# RE1-TT Failure-Mechanism Decomposition (FODA-FCP, current head + pessimistic convention)

Generated 2026-08-10 from `fcp_tt_diagnostics` (FCP re-run over all 125 RE1-TT
cases, per-service C and H captured; classified CSV in session scratchpad,
to be promoted into results/ if quoted in the paper). Failure set = the
canonical pessimistic AC@1 = 0.008 (1 correct / 124 failures).

## Mechanism split of the 124 failures

| Mechanism | n | Share | Signature |
|---|---|---|---|
| (a) SATURATION | 87 | 70.2% | C ties at exactly 1.000, tie blocks of 2–30 services; ground-truth H median 0.950 (local detection succeeds, Noisy-OR washes it out) |
| (b) SILENCE | 31 | 25.0% | C = 0.000 for ALL 64 services (no Mamdani rule fires anywhere); ground-truth H = 0.000 in 31/31 |
| (d) discriminated-but-wrong | 6 | 4.8% | unique top-1 at C = 1.000, ground truth outside the block; gt H median 0.915 |

## Fingerprint confirmation (Paper 6 §4.5 claims, re-verified under head)

- 43 distinct top-1 services among the 124 failures ✓ (Paper 6: 43)
- Most-frequent failure top-1 = 25.8% ✓ (Paper 6: "26 percent")
- Ground-truth H = 0.88–0.95 on failures — **holds for mechanisms (a)+(d)
  (93/124, median 0.950) but NOT for (b), where H = 0.000.** Paper 6's
  blanket phrasing needs this caveat at its Q2 revision; the method paper
  states the split from the start.

## §5.7 consequence — measured, and a framing correction

**Order-level tiebreaking cannot move canonical AC@1 at all.** Pessimistic
scoring assigns the ground truth the worst rank in its score-tie block, so
any reordering *within* a tie block (alphabetical, local-H, anything) is
invisible to the metric. The D7 mitigation is only meaningful as **score
refinement** — folding local evidence into the score itself (e.g.
C′ = C − ε·(1 − H), ε small), which breaks score ties and therefore changes
pessimistic ranks.

Measured headroom of H-based score refinement, mechanism (a) only:
- ground truth inside the saturated tie block: 30 of 87
- of those, gt H strictly greater than every other block member's H (STRICT rescue): **18 cases** (26 under loose ≥ counting; 8 lost to H-ties)
- upper bound, STRICT (unique H-max; ruling 2a): 18 rescues → AC@1 0.008 → **0.152** on RE1-TT (19/125 = 1 baseline-correct + 18). Loose H-tie counting gives 26 rescues but is superseded.

Mechanism (b) headroom: **zero** — H = 0 for every service; there is no
signal to refine. Silence is Mamdani-rule-coverage territory (the injected
fault's telemetry signature matches no rule antecedent under the z-score
fuzzification): Future Work / Paper-8, exactly per the D7 ruling.

Mechanism (d) headroom: zero for ranking-side fixes (the block excludes the
ground truth); these are propagation-topology errors.

## §5.6 drafting notes

- Two-mechanism structure confirmed quantitatively: 70% saturation / 25%
  silence / 5% residual.
- Calibration cross-evidence: TT ECE worsens 0.219 → 0.243 under honest
  scoring because mechanism-(a) blocks carry C = 1.000 (maximal confidence,
  scored wrong) — the method is *confidently* wrong at scale.
- **CORRECTED 2026-08-11:** the 31 silence cases are *not* fault-type
  concentrated. Measured distribution: memory 8, delay 7, disk 7, CPU 5,
  packet loss 4 — spread across all five types. The earlier
  "loss/delay-dominated" reading was an unverified guess and is superseded;
  §5.6.2 states the measured distribution. The coverage gap is general.
