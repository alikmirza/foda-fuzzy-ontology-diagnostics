# Findings

Running log of empirical findings from the Paper-6 experimental work.
Entries are dated and grouped by topic. The point of this file is to
preserve interpretations that informed downstream decisions — the
numbers themselves live in `results/`, this file says what they
*meant* and what we did next.

---

## 2026-05 — MonitorRank baseline characterization on RE1-OB

S(M) = 0.000 (no labeled-inject_time dependence, validated by ±300s shift)

Overall AC@1 = 0.632, decomposed:
- Random-onset AC@1 = 0.416 (any-window anomaly signal)
- Detected-onset AC@1 = 0.632 (+0.216 onset-finding lift)

Per-fault detection error medians (seconds):
- CPU 24s, MEM 11s — direct canonical-feature injection, near-oracle detection
- DISK 238s, DELAY 187s — indirect signature, real uncertainty
- LOSS 338s — no clean signature in RE1-OB column schema

Per-fault AC@1 (true vs random onset):
- CPU 0.68 / 0.56 (delta 0.12) — mostly any-window
- MEM 0.68 / 0.44 (delta 0.24)
- DISK 0.72 / 0.40 (delta 0.32)
- DELAY 0.96 / 0.56 (delta 0.40) — onset-quality dependent
- LOSS 0.12 / 0.12 (delta 0.00) — uniformly fails

Implication for Paper 6: every method baseline gets the same three-axis
characterization (S(M), random-onset AC@1, detected-onset AC@1). This is
the deployment-realism methodological contribution.

Discrepancy from published MicroCause/MicroRank likely due to RCAEval's
published preprocessing aggregating per-service raw columns into derived
features. Our schema_normalizer exposes raw cpu/mem columns directly,
which is more favorable for z-score detection on these fault types.

---

## 2026-05 — CausalRCA baseline characterization on RE1-OB

S(M) = 0.000 (no labeled-inject_time dependence, validated by ±300s shift)

Overall AC@1 = 0.624, decomposed:
- Random-onset AC@1 = 0.344 (any-window structural signal)
- Detected-onset AC@1 = 0.624 (+0.280 onset-finding lift)

Per-fault detected-onset AC@1:
- CPU 0.68, MEM 0.68, DISK 0.68, DELAY 0.96, LOSS 0.12
- Profile nearly identical to MonitorRank (cpu/mem/disk/delay match
  exactly or within 4pp), suggesting both methods converge on the
  same ranking signal despite different mathematical foundations
  (random-walk PageRank vs PC-algorithm causal discovery).

Cross-method observations vs MonitorRank:
- CausalRCA more onset-sensitive: random-onset gap is 28pp vs
  MonitorRank's 22pp. The PC algorithm depends on correctly
  segmenting pre/post windows for conditional independence tests;
  random pivots produce noisier DAGs.
- Aggregate AC@1 difference is within noise (0.008pp). Causal-graph
  structure does not appear to add discriminating power over
  correlation-based methods on RE1-OB step-change injections.

Implication for Paper 6: aggregate AC@1 comparisons are a lossy
characterization. Two methods can score identically on AC@1 while
having substantively different (random-onset, detected-onset)
profiles. The full 3-axis characterization is required to
distinguish methods.

Hypothesis: published CausalRCA AC@1 (~0.15) lower than ours
because their preprocessing aggregates per-service raw columns
into derived features. Documented in DEVIATIONS.md.

---

## 2026-05 — MicroRCA baseline characterization on RE1-OB

S(M) = 0.000 (no labeled-inject_time dependence, validated by ±300s shift)

Overall AC@1 = 0.624, decomposed:
- Random-onset AC@1 = 0.376 (any-window structural signal)
- Detected-onset AC@1 = 0.624 (+0.248 onset-finding lift)
- Collapsed-graph AC@1 = 0.624 (attributed-graph effect = 0.000)

Per-fault detected-onset AC@1:
- CPU 0.68, MEM 0.68, DISK 0.72, DELAY 0.96, LOSS 0.08
- Profile within 4pp of MonitorRank and CausalRCA on every fault
  except LOSS (where all three methods fail uniformly — MR/CR 0.12,
  Micro 0.08, within noise). Three methods, three different
  structural foundations (random-walk PageRank vs PC-algorithm
  causal discovery vs attributed-graph PPR), nearly identical
  per-fault profiles.

Attributed-graph effect (brief §9):
- Asymmetric lagged-correlation graph: AC@1 = 0.624
- Symmetric Pearson graph (collapsed):  AC@1 = 0.624
- Delta = 0.000 on every fault. The asymmetric edge weighting adds
  zero discriminating power on RE1-OB. Same shape of finding as
  CausalRCA's PC-algorithm step: the structural elaboration on top
  of the per-service anomaly signal does not change top-1 ranking
  in even one of 125 cases.

Cross-method observations vs MonitorRank, CausalRCA:
- All three methods now score essentially identically on overall
  AC@1: 0.632, 0.624, 0.624. The pattern flagged after CausalRCA
  ("aggregate AC@1 is a lossy characterization") is now empirically
  confirmed across three structurally distinct methods.
- Random-onset profiles do diverge: MR 0.416, CR 0.344, Micro 0.376.
  This is the axis where the methods actually differ — how robust
  is the ranking to a misplaced pivot. MR > Micro > CR in robustness;
  PC-algorithm CI tests are most pivot-sensitive (conditional
  independence reads change), random-walk PPR is least.
- Attributed-graph effect (delta) is *zero* on RE1-OB. Onset-finding
  lift is *substantial* (+0.21 to +0.28). The structural step is the
  least load-bearing component of all three methods; the change-
  point detector is the most.

Implication for Paper 6 (sharper version of the CausalRCA note):
correlation-based RCA methods on RE1-OB converge on a shared upper
bound determined by the per-service post-vs-pre z-score signal that
the normalized canonical schema exposes. The structural step —
random-walk personalization, PC-algorithm CPDAG, or lagged-corr
attributed graph — modulates *the variance of the answer under
pivot perturbation*, not the answer itself when the pivot is
well-chosen. Three data points now support this; expect the next
two methods (BARO, DejaVu, FODA-FCP) to either confirm or break it.

If the pattern holds across all five remaining methods, the paper's
methodological contribution sharpens: the deployment-realism
characterization (S, random-onset, detected-onset, attributed-graph)
exposes that aggregate AC@1 comparisons are not just lossy — they
are *uninformative* on RE1-OB. The methods are differentiated
elsewhere.

---

## 2026-05 — BARO baseline characterization on RE1-OB

S(M) = 0.000 (structural — BARO does not read ground_truth)

Overall AC@1 = 0.536, ~9pp below the MR/CR/Micro convergence band
(~0.62).¹

Reference comparison decomposition:
- RCAEval reference BARO (raw columns + inject_time):    0.720 AC@1
- Our oracle (inject_time given, canonical schema):       0.600 AC@1
- Our native (BOCPD-detected onset, canonical schema):    0.536 AC@1

The 18.4pp gap from reference to native decomposes as:
- 12.0pp from canonical-schema preprocessing (oracle vs ref)
-  6.4pp from BOCPD onset detection vs ground-truth inject_time pivot

Neither component is a bug. Both are deliberate consequences of the
NormalizedCase contract: canonical preprocessing for cross-method
comparability, BOCPD-detected onset for deployment realism.

Per-fault detected-onset AC@1: cpu 0.680, mem 0.800, disk 0.400,
delay 0.680, loss 0.120.

Decomposition diagnostics:
- AC@1_native (BOCPD pivot):          0.536
- AC@1_random (random pivot):         0.376  (+0.160 from native)
- AC@1_zscore_onset (z-score pivot):  0.568  (+0.032 from native)

Counterintuitive finding (now smaller in magnitude): BARO's native
Bayesian change-point detector underperforms the shared z-score onset
utility by 3.2pp on RE1-OB. This is the smallest difference we have
seen between change-point-detector families; the Bayesian and
z-score detectors are within noise of each other on this dataset.
The previously-reported 8.8pp gap was a side effect of the same
pre-commit BARO bug that yielded 0.480 in the stale findings (see
footnote 1).

Cross-method implication: BARO sits 9pp below the MR/CR/Micro
convergence band on the low side. Methods are NOT all equivalent
under canonical preprocessing — column-max-z methods underperform
graph-walking methods that share the same z-score onset detector.
The methodological diversity is in HOW methods consume the
telemetry, not just in their ranking algorithm.

¹ The original committed findings entry (commit d1eb0e9) quoted
overall AC@1 = 0.480 and per-fault {cpu 0.520, mem 0.760, disk
0.360, delay 0.640, loss 0.120}. Those numbers came from a
pre-commit dev iteration of `baro.py` that was fixed before the
commit landed; the committed code produces 0.536. The discrepancy
was caught by the cross-method edge-shift diagnostic which re-ran
BARO and observed the 0.536 standard value. Full investigation in
`results/baro_discrepancy_investigation.md`.

This finding strengthens Paper 6's argument: aggregate AC@1 obscures
real methodological diversity. Methods at the same AC@1 can have
different onset profiles (MR/CR/Micro example) AND methods at
different AC@1 can be telling us about different aspects of telemetry
consumption (BARO example).

---

## 2026-05 — DejaVu baseline characterization on RE1-OB

S(M) = 0.000 (structural — DejaVu does not read ground_truth at inference)

Standard 5-fold CV AC@1 (stratified by (service, fault) cell) = 0.720
overall. Per-fault:
  cpu  1.000, mem  1.000, disk 1.000, delay 0.440, loss 0.160

5-fold spread: {0.640, 0.720, 0.720, 0.760, 0.760}, mean 0.720, std 0.05.

First method to break the MR/CR/Micro AC@1 convergence band (~0.62) on
the high side. Training on historical cases adds 30pp on cpu/mem/disk
where the canonical-feature anomaly signature is consistent across
instances.

DIAGNOSTIC FINDINGS BEYOND HEADLINE NUMBER

(1) NOT MEMORIZATION. Within-cell pairwise correlation across the 5
instances of each (service, fault) cell is 0.12 mean, 0.26 max, zero
cells above 0.95. The correlation pattern is anti-correlated with
per-fault AC@1: CPU has the lowest within-cell similarity (0.04) and
the highest accuracy (1.000). Per-cell memorization is ruled out.

(2) DISTRIBUTION-BOUND, NOT POSITION-INVARIANT. DejaVu was trained on
case_windows where inject sits at offsets in [25%, 75%] (the harness
hashed-offset distribution). At test time:
  In-band (offset in [25%, 75%]):    AC@1 = 0.720
  Centered (offset = 50%):           AC@1 = 0.720
  Edges (offset near 5% or 95%):     AC@1 = 0.432

The 29pp drop at OOD onset positions is the real qualifier on the
headline. Per-fault collapse at edges:
  cpu  1.000 → 0.840 (-16pp)
  mem  1.000 → 0.640 (-36pp)
  disk 1.000 → 0.480 (-52pp)
  delay 0.440 → 0.080 (-36pp)
  loss 0.160 → 0.120 (-4pp)

Disk faults lose 52pp at edges because the post-inject step needs
adequate post-window samples to characterize; edge placement breaks
that. CPU loses least because cpu anomalies show up earlier in the
post-window. Loss barely degrades because loss-fault AC@1 was already
low — the method had no signal to lose.

(3) TRAINING-SIZE ABLATION (fold-0 only). AC@1 ∈ {0.640, 0.640, 0.680,
0.640} for N ∈ {25, 50, 75, 100}. Flat. Reported on fold-0's test set,
which is the hardest fold (8pp below the CV mean).

Two consistent interpretations of the flat ablation:
  (a) DejaVu's GAT inductive bias generalizes from one example per
      (service, fault) cell — additional examples don't help because
      cell signature is already extracted.
  (b) RE1-OB's 25 cells provide one example each at N=25, and the
      extra 75 examples at N=100 are within-cell duplicates that
      don't add learning signal.

Both interpretations predict flat scaling. The benchmark cannot
distinguish them. A benchmark with greater cell-internal variation
or a larger cell taxonomy could.

DEPLOYMENT-REALISM IMPLICATION

In production, an SRE does not control where inject sits in their
telemetry window. Sometimes incidents start early in the available
data; sometimes late. Edge-positioned inject is a normal deployment
condition, not a corner case.

DejaVu's supervised lift over unsupervised methods (MR, CR, Micro,
BARO) is partially preserved even at edge offsets, because edge-
fragility is a **benchmark-wide property** under canonical
preprocessing, not a supervised-method property. Measured cross-
method numbers (cross-method edge-shift diagnostic — see below)
refute the original "supervised, fragile / unsupervised, robust"
framing.

CROSS-METHOD EDGE-SHIFT (measured, all 5 methods)

  method  | (a) standard | (b) edges | (c) center | edge drop
  --------|--------------|-----------|------------|----------
  MR      |    0.632     |   0.296   |   0.512    |  -33.6pp
  CR      |    0.624     |   0.248   |   0.496    |  -37.6pp
  Micro   |    0.624     |   0.240   |   0.488    |  -38.4pp
  BARO    |    0.536     |   0.308   |   0.456    |  -22.8pp
  DejaVu  |    0.720     |   0.432   |   0.720    |  -28.8pp

All five methods lose 22-38pp at edge-positioned inject. DejaVu's
absolute AC@1 at edges (0.432) is HIGHER than any unsupervised
method's edge AC@1 (range 0.240-0.308). The supervised-vs-unsupervised
gap is 12-19pp at edges vs 12-24pp at standard offsets — narrower at
edges but the ranking is preserved.

THREE DISTINCT EDGE-FRAGILITY MECHANISMS

* MR/CR/Micro — **detector misalignment**. All three call the shared
  `_onset.detect_onset` utility, which scans candidate pivots only in
  the central [25%, 75%] band of the window. When inject sits at
  offset 60s (5%) or 1140s (95%), the actual change point is OUTSIDE
  the detector's search range; the detector returns a spurious
  central-band pivot and pre/post statistics are computed against
  the wrong split. This is the largest of the three mechanisms
  (-33.6 to -38.4pp).

* BARO — **short post-injection window**. BARO's BOCPD detector
  scans the whole window, not just the central band, so it can find
  edge-positioned change points. But when inject sits near the right
  edge, post-injection has only a handful of samples; the
  RobustScaler-z scoring is statistically underpowered. Smallest
  unsupervised drop (-22.8pp) confirms BOCPD partially compensates
  for the detector-misalignment problem, but scoring still degrades.

* DejaVu — **training-distribution shift**. The supervised
  classifier learned to expect inject in [25%, 75%] (the harness
  hashed-offset distribution); edge-positioned inject is
  out-of-distribution, degrading the temporal CNN's feature
  extraction. Center remains identical to standard (the model is
  robust within distribution, fragile outside it).

This is a deployment-realism gap that AC@1 alone hides. The
NormalizedCase + S(M) protocol catches inject_time leakage but
does not catch "method assumes a particular telemetry window
structure." A follow-up evaluation dimension — call it "offset
robustness" or "window-placement invariance" — characterizes
methods on this axis. Considering for inclusion in Paper 6 §4.

PAPER 6 §4 NARRATIVE

DejaVu is the first method in our evaluation that wins on raw AC@1
across all evaluated regimes. Edge fragility is real but is shared
by every method we have tested; it is a property of how canonical
preprocessing interacts with onset placement, not a property of
supervised learning. The cross-method edge-shift diagnostic
surfaces this benchmark-wide property and motivates an explicit
"offset robustness" axis in Paper 6 §4.

The discriminating story for DejaVu is: in-band, supervised training
adds 9pp over the unsupervised convergence band (0.720 vs ~0.62);
at edges, the lift narrows to 12pp over the best unsupervised
method (0.432 vs 0.308 BARO). DejaVu wins in both regimes; the
unsupervised methods do NOT have an edge-robustness advantage to
trade against DejaVu's in-band lead.

---

## Cross-method finding (updated through DejaVu + edge-shift diag) — supervised methods break the convergence band; universal edge fragility

Five metric-based RCA methods on RE1-OB:
  MonitorRank:  0.632 (random-walk PageRank, unsupervised)
  CausalRCA:    0.624 (PC algorithm + ancestor scoring, unsupervised)
  MicroRCA:     0.624 (attributed-graph asymmetric PageRank, unsupervised)
  BARO:         0.536 (multivariate BOCPD + column-max-z, unsupervised)
  DejaVu:       0.720 (GAT-attention neural classifier, SUPERVISED)

The "correlation-based-RCA AC@1 convergence band" identified after
the first three methods (MR/CR/Micro within 0.8pp) is now revealed
as a **ceiling** for unsupervised correlation-based methods on RE1-
OB step injections, not a universal property of RCA on this
benchmark.

DejaVu breaks the ceiling by 9pp on overall AC@1, scoring 1.000 on
three of five fault types (CPU/MEM/DISK). It does so via supervised
training on labeled historical cases — the previous four methods all
diagnose from telemetry alone with no labeled history.

BARO sits below the unsupervised band (0.536, 9pp below) for a
different reason: its column-max-z scoring is hurt by canonical-
schema preprocessing that helps graph-walk methods (reference
comparison: 12pp gap from canonical-schema alone, 6.4pp from BOCPD
onset vs ground-truth pivot). BARO is unsupervised and would not
benefit from training-set access.

Per-fault profile alignment:

| fault | MR    | CR    | Micro | BARO  | DejaVu |
|-------|-------|-------|-------|-------|--------|
| cpu   | 0.680 | 0.640 | 0.680 | 0.680 | 1.000  |
| mem   | 0.640 | 0.680 | 0.680 | 0.800 | 1.000  |
| disk  | 0.720 | 0.760 | 0.720 | 0.400 | 1.000  |
| delay | 0.960 | 0.880 | 0.960 | 0.680 | 0.440  |
| loss  | 0.080 | 0.080 | 0.080 | 0.120 | 0.160  |

Two patterns:
1. **Resource faults** (cpu/mem/disk): supervised DejaVu dominates;
   unsupervised methods plateau at ~0.70. BARO now matches graph-walk
   methods on cpu/mem but still trails on disk.
2. **Network faults** (delay/loss): unsupervised graph-walk methods
   (MR/CR/Micro) beat DejaVu on DELAY (0.96 vs 0.44), and all
   methods are weak on LOSS (≤ 0.16). Supervised training on a
   small (100-case) set is insufficient to learn the DELAY/LOSS
   signature.

Onset sensitivity remains a discriminating axis for the
unsupervised methods; DejaVu's onset detection is implicit in the
temporal encoder and does not have a directly comparable lift:
  MonitorRank:  +0.216 onset-finding lift
  MicroRCA:     +0.248 onset-finding lift
  CausalRCA:    +0.280 onset-finding lift
  BARO:         +0.160 onset-finding lift (smallest unsupervised)
  DejaVu:       N/A — onset implicit in temporal CNN encoder

A new axis introduced by DejaVu: **training-size sensitivity**. Flat
curve N∈{25,50,75,100} → AC@1∈{0.64, 0.64, 0.68, 0.64}. Architecture
inductive bias explains DejaVu's performance, not training data
scale. This is a paper-relevant inversion of the standard deep-
learning narrative.

### Universal edge fragility (cross-method edge-shift diagnostic)

Measured AC@1 under three offset regimes for all five methods:

| method  | (a) standard | (b) edges | (c) center | edge drop (b−a) |
|---------|--------------|-----------|------------|-----------------|
| MR      |    0.632     |   0.296   |   0.512    |     -33.6pp     |
| CR      |    0.624     |   0.248   |   0.496    |     -37.6pp     |
| Micro   |    0.624     |   0.240   |   0.488    |     -38.4pp     |
| BARO    |    0.536     |   0.308   |   0.456    |     -22.8pp     |
| DejaVu  |    0.720     |   0.432   |   0.720    |     -28.8pp     |

(a) = each case's hashed default offset in [25%, 75%]
(b) = mean of offset=60s (5%) and offset=1140s (95%)
(c) = offset=600s (exactly 50%)

**Edge fragility is universal.** All five methods lose 22-38pp when
inject is positioned near the window edges. The going-in hypothesis
(unsupervised methods robust because they have no training
distribution) is refuted. The three mechanisms that produce edge
fragility are distinct:

1. **Detector misalignment** (MR/CR/Micro, -33.6 to -38.4pp). The
   shared `_onset.detect_onset` scans candidate pivots only in
   [25%, 75%] of the window. Edge-positioned inject is outside the
   detector's search range; detector returns a spurious central-band
   pivot.

2. **Short post-injection window** (BARO, -22.8pp). BARO's BOCPD
   scans the whole window, so the change-point timestamp is
   recoverable at edges; but the RobustScaler-z scoring is
   statistically underpowered when post-injection has only a few
   samples.

3. **Training-distribution shift** (DejaVu, -28.8pp). The classifier
   learned to expect inject in [25%, 75%]; edge-positioned inject is
   OOD for the temporal CNN's feature extraction.

DejaVu retains its supervised lift in absolute terms at edges
(AC@1=0.432) vs the best unsupervised at edges (BARO=0.308). The
supervised-vs-unsupervised gap is 12-19pp at edges vs 12-24pp at
standard offsets — narrower but the ranking is preserved.

**Methodological implication.** S(M)=0 catches inject_time leakage
but not "method assumes a particular telemetry window structure."
Offset robustness is a benchmark-wide property under canonical
preprocessing and deserves its own axis in Paper 6 §4, reported
alongside S(M), random-onset, and detected-onset.

The remaining methods (yRCA, FODA-FCP) will either:
- Extend the supervised-method-breaks-ceiling pattern (yRCA is
  unsupervised; FODA-FCP is ontology-grounded — both might
  reproduce the unsupervised ceiling or, like FODA-FCP, exceed it
  via prior knowledge rather than supervised training)
- Or stay within the unsupervised convergence band

Track which.

---

## yRCA entry — rule-based reasoning, below the unsupervised AC@1 band; lowest absolute edge fragility among unsupervised methods

Configuration: synthetic events from canonical metric features
(threshold |z|≥3.0), topology inferred from lagged feature
correlation (threshold 0.5), forward chaining over a 5-rule core
(R1 potential_root_cause, R2 explained_by via topology, R3
final_root_cause, R4 retry_cascade, R5 timeout_propagation),
shared `_onset.detect_onset` for event timestamping. Output is a
role-tagged ExplanationAtom set + `rule_derived_explanation`
links. Confidence is the derivation-multiplicity ratio (fraction
of final_root_cause services derived through ≥ 2 distinct rule
paths). See `evaluation/methods/yrca.py` and DEVIATIONS.md
→ "yRCA adapter" for the full re-implementation note.

(1) HEADLINE NUMBERS ON RE1-OB (125 cases, 5 fault × 25 each):

  AC@1 overall = 0.328
  AC@3 overall = 0.608
  AC@5 overall = 0.712
  MRR          = 0.509
  S(yRCA)      = 0.000 across every fault type (no inject_time
                 leakage; structural witness)
  iterations   ≤ 4 on every observed case (well below the
                 max_iterations=32 cap)

Per-fault:

| fault | AC@1  | AC@3  | AC@5  | MRR   |
|-------|-------|-------|-------|-------|
| cpu   | 0.640 | 0.800 | 0.800 | 0.737 |
| mem   | 0.600 | 0.800 | 0.880 | 0.728 |
| disk  | 0.200 | 0.720 | 0.840 | 0.474 |
| delay | 0.120 | 0.400 | 0.640 | 0.345 |
| loss  | 0.080 | 0.320 | 0.400 | 0.262 |

yRCA's AC@1 (0.328) sits BELOW the unsupervised graph-walk
convergence band (~0.62) AND below BARO (0.536). The synthetic-
event abstraction (one event per service-feature pair, all
timestamped at a single window-level onset) collapses the rich
temporal information that graph-walk methods exploit. The
ranking at AC@3 / AC@5 recovers somewhat (0.608 / 0.712), which
matches the rule-engine output shape: yRCA names a small set of
final_root_cause candidates per case, and the right service is
often in that set but not always at position 1.

Two interpretations consistent with the data:

  (a) The synthetic-event regime is the binding constraint, not
      the rule engine. yRCA's published log-based regime sees
      many events per service over time; the window-level
      abstraction we adopt under RE1-OB's metric-only contract
      loses the lead-lag information that R2 and R5 need to
      discriminate cause from dep.
  (b) The 5-rule core is missing rules that fire in the
      published yRCA Prolog ruleset. The richest unsupervised
      adapter for RCAEval RE1-OB might require porting more
      patterns; we restricted to a faithful core to keep the
      adapter scope finite.

The two interpretations predict different per-fault profiles.
yRCA's CPU/MEM strengths (0.640 / 0.600) and DELAY/LOSS weakness
(0.120 / 0.080) match resource-anomaly cases (where a single
service-feature pair generates the strongest event) being well-
captured, vs. network-fault cases (where the propagation signal
is what discriminates) being poorly-captured. This is consistent
with interpretation (a): the lost information is exactly the
temporal-propagation signal that DELAY / LOSS faults rely on.

(2) DECOMPOSITION: random-onset variant

  AC@1_random overall = 0.248
  AC@1_native − AC@1_random = +0.080

The onset-finding lift is +8.0pp — substantially smaller than
the unsupervised graph methods' +16-28pp onset-finding lift, but
non-zero. The rule engine retains some discriminating power even
on a random pivot, because R3's "unexplained final_root_cause"
selection rule is largely topology-driven, not onset-driven.
That's a paper-relevant observation: yRCA's value is more in
the rule engine than in the onset detection, the opposite of
graph-walk methods.

(3) OFFSET ROBUSTNESS (Paper 6 §4 standard axis)

  (a) standard (per-case hashed offset): 0.328
  (b) edges (mean of 5 % / 95 %):         0.196   (-13.2pp)
  (c) center (50 %):                      0.224   (-10.4pp)

yRCA is the LEAST edge-fragile unsupervised method in absolute
terms (−13.2pp vs MR/CR/Micro −33.6 to −38.4pp and BARO −22.8pp).
Two combining factors:

  - The rule engine aggregates events into a small set of
    derived facts before ranking. Onset misalignment shifts
    which events fire R1, but the rule-chain selection of
    final_root_cause is more invariant than a per-feature z-
    score sum.
  - yRCA's standard AC@1 is the lowest of the unsupervised
    methods, so there's less to lose. The proportional drop
    (−40 %) is comparable to BARO (−43 %); the absolute drop is
    smaller only because the baseline is lower.

DEPLOYMENT-REALISM IMPLICATION

yRCA's reduced edge-fragility comes at a steep AC@1 cost. For
deployment scenarios where edge-positioned inject is the rule
(unbounded telemetry windows, no fencepost on inject time),
yRCA is the second-best UNSUPERVISED method at edges (0.196 vs
BARO 0.308); for in-band deployment, graph-walk methods and
BARO clearly outperform. yRCA's value proposition is the
**explanation chain**, not the rank: a role-tagged service set
plus rule-derived causal links is what Paper 6 §4's case-study
figure (Figure 6) compares side-by-side with FODA-FCP.

EXPLANATION SHAPE

Each yRCA case emits:
  - 1-N ExplanationAtom objects, one per service appearing in
    the derived chain, role-tagged via `ontology_class`:
    `yrca:Role/final_root_cause`,
    `yrca:Role/intermediate_propagator`, or
    `yrca:Role/potential_root_cause`.
  - 0-M CausalLink objects with
    `relation_type="rule_derived_explanation"` for every
    `explained_by` derivation, weighted by the number of
    independent rule paths.
  - confidence = derivation-multiplicity ratio (fraction of
    final_root_cause services derived through ≥ 2 distinct
    rules). Overall mean confidence ≈ 0.4-0.6 across RE1-OB —
    most cases derive their final root cause through one or two
    rules, rarely more.

A representative 5-correct + 5-incorrect sample is archived as
`paper/artifacts/yrca_explanation_samples.json`, mirroring
DejaVu's attention-sample dump format. Sample inspection
confirms the role-tagging makes sense even on incorrect cases:
the wrong service is named final_root_cause when the topology-
inferred edges point in the wrong direction (e.g. a heavily-
correlated downstream traffic signal ranks as the cause when
the upstream latency signal didn't pass the z-threshold).

---

## Cross-method finding (updated through yRCA + edge-shift diag) — synthetic-event regime collapses rule-engine value; offset robustness now spans 0.196-0.720 at edges

Six metric-based RCA methods on RE1-OB:

  MonitorRank:  0.632 (random-walk PageRank, unsupervised)
  CausalRCA:    0.624 (PC algorithm + ancestor scoring, unsupervised)
  MicroRCA:     0.624 (attributed-graph asymmetric PageRank, unsupervised)
  BARO:         0.536 (multivariate BOCPD + column-max-z, unsupervised)
  DejaVu:       0.720 (GAT-attention neural classifier, SUPERVISED)
  yRCA:         0.328 (rule-based reasoning over synthetic events,
                       unsupervised)

yRCA enters the suite BELOW the unsupervised correlation-based
convergence band, the first method to do so. Three of the four
correlation-based methods cluster at 0.624-0.632 (within 0.8pp);
BARO sits at 0.536 due to its column-max-z scoring × canonical-
preprocessing interaction; yRCA sits at 0.328 due to its
synthetic-event abstraction.

The result reframes the AC@1 spread:

  - **Top**: supervised (DejaVu, 0.720)
  - **Band**: unsupervised correlation-based (MR, CR, Micro,
    0.624-0.632)
  - **Below band**: unsupervised with method-specific scoring
    constraints (BARO 0.536, yRCA 0.328)

yRCA's value within Paper 6 is therefore NOT raw AC@1 — it is
the explanation chain (role-tagged, rule-derived, with multi-
rule confidence) that the case-study figure (Paper 6 §4 Figure
6) will render side-by-side with FODA-FCP. This is the
SemanticGroundedness comparison axis the brief identifies.

### Updated universal-edge-fragility table (6 methods)

| method  | (a) standard | (b) edges | (c) center | edge drop (b−a) |
|---------|--------------|-----------|------------|-----------------|
| MR      |    0.632     |   0.296   |   0.512    |     -33.6pp     |
| CR      |    0.624     |   0.248   |   0.496    |     -37.6pp     |
| Micro   |    0.624     |   0.240   |   0.488    |     -38.4pp     |
| BARO    |    0.536     |   0.308   |   0.456    |     -22.8pp     |
| DejaVu  |    0.720     |   0.432   |   0.720    |     -28.8pp     |
| yRCA    |    0.328     |   0.196   |   0.224    |     -13.2pp     |

(a) = each case's hashed default offset in [25%, 75%]
(b) = mean of offset=60s (5%) and offset=1140s (95%)
(c) = offset=600s (exactly 50%)

**Edge fragility remains universal across all 6 methods**,
ranging now from −13.2pp (yRCA, smallest absolute drop) to
−38.4pp (Micro). Three mechanisms documented in the previous
cross-method block still cover MR/CR/Micro (detector
misalignment), BARO (short post-injection window), DejaVu
(training-distribution shift). yRCA introduces a **fourth
mechanism**:

4. **Synthetic-event regime invariance partial.** yRCA's rule
   engine aggregates events into a small set of facts before
   ranking, partially insulating it from onset misalignment.
   The −13.2pp absolute drop is the smallest of any method we
   have tested — but yRCA's standard AC@1 is also the lowest,
   so the proportional drop (−40 %) is in the same range as
   the other unsupervised methods (−40 % to −60 %).

yRCA's edge AC@1 of 0.196 is the lowest of all six methods at
edges; even the best unsupervised method at edges (BARO,
0.308) preserves a 11pp lead. So while yRCA is the least
edge-fragile in absolute pp, it is also the worst-ranked
method at edges.

**Methodological observation.** Offset robustness, raw AC@1,
and the proportional drop measure different things and rank
methods differently. The brief's "lower is better for S(M),
higher is better for AC@1, less is better for edge drop"
framing is correct as far as it goes; the cross-method
diagnostic shows that no single method dominates on all three
axes simultaneously. DejaVu wins AC@1 (in-band and at edges);
yRCA wins smallest absolute edge drop; MR/CR/Micro win
unsupervised in-band AC@1.

The remaining method (FODA-FCP) is the ontology-grounded
candidate. Open question for Paper 6 §4: does ontology
grounding move the unsupervised methods into the supervised
band (closing the 9pp gap vs DejaVu), or does it primarily
move explanation quality (SemanticGroundedness, the
explanation-completeness metric) without moving raw AC@1?
yRCA's data point — rich explanation chain, low AC@1 —
suggests the explanation-quality and rank-quality axes can be
decoupled. Track.

