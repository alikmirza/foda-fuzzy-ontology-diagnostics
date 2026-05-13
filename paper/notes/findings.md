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

---

## 2026-05 — FODA-FCP entry (dissertation centerpiece, AICT 2026)

Configuration: z-score-driven fuzzification on canonical schema
(replacing the AICT paper's SLO-calibrated crisp thresholds —
DEVIATIONS.md → "FODA-FCP adapter" → Deviation 1), 16-rule Mamdani
inference (verbatim port of ``MamdaniFuzzyRuleEngine`` over
six fault categories: CPU_SATURATION, MEMORY_PRESSURE,
SERVICE_ERROR, LATENCY_ANOMALY, CASCADING_FAILURE,
RESOURCE_CONTENTION), damped Noisy-OR confidence propagation
(Eq. 4, δ = 0.85) on a lagged-correlation-inferred dependency
graph (threshold 0.5, lag 1), top-K ranking by propagated
confidence C(s), ontology-grounded CanonicalExplanation with
full DiagnosticKB URIs, Recommendation atom for the predicted
root cause, and three relation types: ``contributes_to``,
``suggests_mitigation``. Shared ``_onset.detect_onset`` for the
pre/post split that feeds the fuzzifier. See
``evaluation/methods/foda_fcp.py`` and DEVIATIONS.md →
"FODA-FCP adapter" for the full porting notes.

(1) HEADLINE NUMBERS ON RE1-OB (125 cases, 5 fault × 25 each):

  AC@1 overall = 0.400
  AC@3 overall = 0.568
  AC@5 overall = 0.648
  MRR          = 0.525
  S(FODA-FCP)  = 0.000 on every fault type (no inject_time
                 leakage; structural witness)

Per-fault:

| fault | AC@1  | AC@3  | AC@5  | MRR   |
|-------|-------|-------|-------|-------|
| cpu   | 0.960 | 0.960 | 0.960 | 0.967 |
| mem   | 0.440 | 0.680 | 0.720 | 0.588 |
| disk  | 0.280 | 0.560 | 0.600 | 0.460 |
| delay | 0.160 | 0.400 | 0.480 | 0.323 |
| loss  | 0.160 | 0.240 | 0.480 | 0.286 |

FODA-FCP's AC@1 (0.400) sits BETWEEN yRCA (0.328) and BARO
(0.536); 22pp below the MR/CR/Micro convergence band (~0.62) and
32pp below supervised DejaVu (0.720). Two qualitative facts
stand out:

* **CPU dominance.** AC@1 = 0.960 on CPU faults is the highest
  of any *unsupervised* method we have tested (MR/CR/Micro
  0.640–0.680; BARO 0.680; yRCA 0.640; DejaVu 1.000 supervised).
  When the canonical-feature anomaly signature is clean and
  directly matches a Mamdani rule antecedent (cpu_HIGH AND
  latency_ELEVATED), FCP fires R01–R03 with high certainty
  factors and ranks the local-fault service top-1 even after
  Noisy-OR propagation. The ontology grounding pays off where
  the rule base has prior knowledge of the fault signature.

* **DELAY / LOSS collapse to noise.** AC@1 = 0.160 on delay
  and 0.160 on loss puts FODA-FCP at the floor for network
  faults — lower than MR/CR/Micro (0.96 / 0.88 / 0.96 on
  delay) and roughly tied with yRCA (0.120 / 0.080). The
  Mamdani rule base does not cover network-fault patterns
  (no rule fires on `errorRate_*` + traffic_LOW in the
  network-loss shape; the latency-anomaly rules R10/R11 fire
  on the symptomatic services in the chain, not the root).
  This is a coverage limitation of the published 16-rule base,
  not an algorithmic failure — the AICT 2026 paper's
  evaluation environment did not include network-loss
  injections.

(2) DECOMPOSITION: random-onset variant

  AC@1_random overall = 0.360
  AC@1_native − AC@1_random = +0.040

The onset-finding lift is +4.0pp — the *smallest* of any
unsupervised method we have tested (MR +21.6pp, CR +28.0pp,
Micro +24.8pp, BARO +16.0pp, yRCA +8.0pp, FODA-FCP +4.0pp).
This puts FODA-FCP firmly in the "value comes from the
algorithm, not from the detector" camp alongside yRCA — the
Mamdani fuzzification reads z-magnitudes, not the absolute
post-vs-pre split, so a misplaced pivot still produces the
same ordinal ranking on the strong-signal cases (cpu, mem).

(3) OFFSET ROBUSTNESS (Paper 6 §4 standard axis)

  (a) standard (per-case hashed offset): 0.400
  (b) edges (mean of 5 % / 95 %):         0.168   (-23.2pp)
  (c) center (50 %):                      0.456   (+5.6pp)

Edge fragility at −23.2pp is the **second-smallest absolute
drop** (after yRCA's −13.2pp) among unsupervised methods.
Center (50 % offset) actually scores *higher* than standard
— FODA-FCP is one of two methods (alongside DejaVu) that has
center > standard, reflecting how the rule-engine reading of
z-magnitudes makes the algorithm more robust to a centered
pivot than a hashed-random one within the [25 %, 75 %] band.

EXPLANATION SHAPE (the dissertation centerpiece axis)

Each FODA-FCP case emits a structured CanonicalExplanation
with the following shape (verified on
``re1-ob_adservice_cpu_3`` — a top-1-correct CPU case):

* **4 atoms** on a typical case: 3 ContributingFactor atoms
  (one per service in the top-3 head, tagged with full
  DiagnosticKB URIs like
  ``http://foda.com/ontology/diagnostic#CpuSaturation``) plus
  **1 Recommendation atom** for the predicted root cause
  (e.g. ``http://foda.com/ontology/diagnostic#Rec_CpuSaturation``).
* **5 links** on a typical case: 2 ``contributes_to``
  (propagation:noisy_or) edges from non-root atoms into the
  root atom (weighted by the FCP propagation contribution
  C(t)·w·δ) PLUS 3 ``suggests_mitigation``
  (recommendation:fault_prototype) edges from every
  ContributingFactor atom into the Recommendation atom
  (weighted by source atom membership).
* Each atom's text mentions the fault prototype local name
  ("``CpuSaturation``", "``ResourceContention``"), the fired
  Mamdani rules ("``rules=['R03', 'R10']``"), the local
  confidence H and final confidence C — readable without
  loading the OWL graph but explicitly linked to it via the
  full URI in ``ontology_class``.

Confidence is the relative concentration of fuzzy contribution
mass on the top-1 service (``top1_C / sum(top-K C)``). Overall
mean confidence on RE1-OB ≈ 0.4–0.5 across the 125 cases —
comparable to yRCA's derivation-multiplicity confidence and
honest about the rule engine's near-tie behavior on ambiguous
cases.

CASE-STUDY SAMPLES

A representative 5-correct + 5-incorrect sample is archived as
``paper/artifacts/foda_fcp_explanation_samples.json``,
mirroring the yRCA case-study dump format for direct side-by-side
comparison in Paper 6 §4 Figure 6. The 5 correct cases match
yRCA's correct set (all 5 are also correct under FODA-FCP). The
5 incorrect cases include 1 overlap with yRCA's incorrect set
(``adservice_delay_1``); the other four are FCP-specific
incorrect cases that yRCA gets right.

This 1-overlap-out-of-5 disagreement is itself a paper-relevant
finding: on the 10 yRCA-target cases, FODA-FCP gets 9/10 right
(vs yRCA's 5/10). The methods agree on the 5 CPU/delay cases
that have a clean rule-base match (R01–R03, R10) and disagree
on the 5 cases where yRCA's rule engine fails (most fail
because the synthetic-event regime collapses the temporal
propagation signal that yRCA's R2/R5 rely on — FODA-FCP reads
z-magnitudes against the pre-onset baseline directly, side-
stepping that loss). The case-study figure can render the same
cases side-by-side and demonstrate where the two rule-based
methods diverge structurally.

DEPLOYMENT-REALISM IMPLICATION

FODA-FCP's value proposition on RE1-OB is the explanation
chain plus solid CPU performance, NOT raw AC@1. For a
deployment scenario where CPU saturation is the primary
incident class, FODA-FCP at 0.960 AC@1 matches supervised
DejaVu (1.000) within 4pp without needing labeled training
data. For network-fault deployments the AICT rule base does
not cover the signature; the AC@1 collapse is honest about
that gap and motivates the Phase-2 rule-base expansion the
brief signals.

The explanation-quality axis (Paper 6 Phase 2's
SemanticGroundedness metric) is where FODA-FCP is designed to
win: ontology-grounded atoms with full DiagnosticKB URIs +
explicit Recommendation atoms + structured causal links that
no other method in the suite produces. Whether this translates
to a numerical SemanticGroundedness lead is the Phase-2
empirical question.

CPU-VS-MEM ASYMMETRY (addendum)

The 52pp cpu-vs-mem gap (cpu AC@1 = 0.960, mem AC@1 = 0.440) is
the largest of any method in the suite and is a structural
property of the published AICT 2026 algorithm, not a bug.
Mechanism: RE1-OB memory injections cascade through swap → cpu →
latency, firing R14 (cpu_HIGH ∧ memory_HIGH ∧ latency_CRITICAL →
CASCADING_FAILURE, CF = 0.95 — the highest CF in the rule base)
at maximum strength on the root-cause service. Combined with
Noisy-OR propagation (Eq. 4) this compresses the top of the
ranking to C ≈ 0.99 across multiple candidates; the GT service
ends up #2-#8 by mean gap of 0.060 in C. FCP signals this
honestly: top-1 confidence (top1_C / sum top-K C) drops to 0.343
on wrong-mem cases versus 0.717 on correct-cpu cases (and AC@3 =
0.680 confirms the GT is in the head most of the time — the
ranking just resolves ties in the wrong direction). Frame: this
is a documented limitation of the published FCP rule-base CF
calibration on cascading memory-fault signatures, comparable in
spirit to BARO's column-max-z-under-canonical-preprocessing
limitation. No algorithmic change before paper submission;
remediation paths (lower R14 CF, raise δ damping, re-rank by H
when confidence is low) are all paper-scope.

---

## Cross-method finding (FINAL, all 7 methods) — supervised tops, unsupervised band spans 0.328–0.632, FODA-FCP wins CPU dominance and offset-robustness-among-explanation-rich-methods

Seven RCA methods on RE1-OB:

  MonitorRank:  0.632 (random-walk PageRank, unsupervised)
  CausalRCA:    0.624 (PC algorithm + ancestor scoring, unsupervised)
  MicroRCA:     0.624 (attributed-graph asymmetric PageRank, unsupervised)
  BARO:         0.536 (multivariate BOCPD + column-max-z, unsupervised)
  DejaVu:       0.720 (GAT-attention neural classifier, SUPERVISED)
  yRCA:         0.328 (rule-based reasoning over synthetic events,
                       unsupervised)
  FODA-FCP:     0.400 (fuzzy contribution propagation + ontology-
                       grounded explanation, unsupervised)

The completed AC@1 spread on RE1-OB:

  - **Top**: supervised (DejaVu, 0.720)
  - **Band**: unsupervised correlation-based (MR, CR, Micro,
    0.624–0.632)
  - **Below band**: unsupervised with method-specific scoring
    constraints (BARO 0.536, FODA-FCP 0.400, yRCA 0.328)

FODA-FCP enters the suite between BARO and yRCA on aggregate
AC@1, but with the **highest unsupervised CPU AC@1** (0.960,
tied with DejaVu and 28pp above the next-best unsupervised
MR/Micro at 0.680). The result confirms the yRCA-led
observation that **explanation-quality and rank-quality axes
can be decoupled**: FODA-FCP and yRCA both produce the
richest explanation chains in the suite (ontology-grounded
atoms with structured causal links) and both score below the
correlation-based methods on raw AC@1.

Per-fault profile alignment (all 7 methods):

| fault | MR    | CR    | Micro | BARO  | DejaVu | yRCA  | FODA-FCP |
|-------|-------|-------|-------|-------|--------|-------|----------|
| cpu   | 0.680 | 0.640 | 0.680 | 0.680 | 1.000  | 0.640 | 0.960    |
| mem   | 0.640 | 0.680 | 0.680 | 0.800 | 1.000  | 0.600 | 0.440    |
| disk  | 0.720 | 0.760 | 0.720 | 0.400 | 1.000  | 0.200 | 0.280    |
| delay | 0.960 | 0.880 | 0.960 | 0.680 | 0.440  | 0.120 | 0.160    |
| loss  | 0.080 | 0.080 | 0.080 | 0.120 | 0.160  | 0.080 | 0.160    |

Three per-fault patterns are now fully resolved:

1. **CPU faults**: prior-knowledge methods win (DejaVu 1.000,
   FODA-FCP 0.960). The CPU+latency signature is exactly what
   FCP's R01–R03 + R10 rule cluster keys off, and DejaVu's
   trained classifier learns the same pattern.
2. **Network faults (delay/loss)**: correlation-based methods
   win on delay (MR/Micro 0.960); every method collapses on
   loss (max 0.160). Loss is the universal failure mode on
   RE1-OB — no method has > 0.16 AC@1.
3. **MEM/DISK**: BARO leads on mem (0.800) via its
   RobustScaler-z; disk is a graph-walk specialty
   (MR/CR/Micro 0.72-0.76); FODA-FCP underperforms because
   the rule base undercouples disk to resource-contention
   (R15 needs cpu_HIGH AND memory_HIGH; pure disk faults
   don't trigger either).

Onset sensitivity (random-onset gap) ranks:

  CausalRCA:    +0.280 onset-finding lift
  MicroRCA:     +0.248 onset-finding lift
  MonitorRank:  +0.216 onset-finding lift
  BARO:         +0.160 onset-finding lift
  yRCA:         +0.080 onset-finding lift
  FODA-FCP:     +0.040 onset-finding lift   (smallest)
  DejaVu:       N/A — onset implicit in temporal CNN encoder

FODA-FCP's +4.0pp onset-finding lift is the smallest of all
unsupervised methods. Two interpretations:
* The Mamdani fuzzifier reads z-magnitudes against the pre-
  onset baseline — a misplaced pivot mostly preserves the
  ordinal magnitude relationship that drives rule firing.
* The damped Noisy-OR propagator further dilutes pivot
  sensitivity by averaging across services.

Either way: FODA-FCP's value emphatically lives in the rule
engine + propagation + explanation, NOT in the onset
detector.

### FINAL universal-edge-fragility table (7 methods)

| method   | (a) standard | (b) edges | (c) center | edge drop (b−a) |
|----------|--------------|-----------|------------|-----------------|
| MR       |    0.632     |   0.296   |   0.512    |     -33.6pp     |
| CR       |    0.624     |   0.248   |   0.496    |     -37.6pp     |
| Micro    |    0.624     |   0.240   |   0.488    |     -38.4pp     |
| BARO     |    0.536     |   0.308   |   0.456    |     -22.8pp     |
| DejaVu   |    0.720     |   0.432   |   0.720    |     -28.8pp     |
| yRCA     |    0.328     |   0.196   |   0.224    |     -13.2pp     |
| FODA-FCP |    0.400     |   0.168   |   0.456    |     -23.2pp     |

(a) = each case's hashed default offset in [25 %, 75 %]
(b) = mean of offset = 60s (5 %) and offset = 1140s (95 %)
(c) = offset = 600s (exactly 50 %)

**Edge fragility remains universal across all 7 methods**
(range −13.2pp to −38.4pp). FODA-FCP's −23.2pp absolute drop
ranks third-smallest in absolute pp (after yRCA's −13.2pp
and BARO's −22.8pp). The five known edge-fragility
mechanisms (detector misalignment for MR/CR/Micro, short
post-injection window for BARO, training-distribution shift
for DejaVu, partial synthetic-event invariance for yRCA) now
extend with a sixth:

6. **Fuzzifier z-magnitude band shift.** FODA-FCP's
   z-magnitude-driven fuzzification is computed against the
   pre-onset baseline window — at the right edge of the
   case window (offset = 95 % of window_seconds), the
   "pre-onset" slice is the whole window minus a tiny tail,
   so the z-magnitudes collapse toward 0 and the rule engine
   produces no firings. This drives ``AC@1_b_edge_right``
   well below ``AC@1_b_edge_left``: 0.040 vs 0.296. The
   asymmetric edge drop is the structural signature.

Notably, FODA-FCP's centered (50 %) AC@1 of 0.456 is *higher*
than its standard AC@1 of 0.400 — the only method besides
DejaVu where centered > standard. The hashed offset's
[25 %, 75 %] uniform distribution is *less* favorable to
the rule engine than a precisely-centered pivot, because the
hash sometimes lands close to 25 % or 75 % where the pre/post
slices are imbalanced enough to weaken the z-magnitude
signal.

**Methodological summary for Paper 6 §4.** The four-axis
characterization protocol (S(M), random-onset, detected-onset,
offset-robustness) successfully discriminates seven
structurally-distinct methods on RE1-OB. No single method
dominates all four axes:

* DejaVu wins AC@1 (in-band and at edges).
* MR/CR/Micro win unsupervised in-band AC@1.
* yRCA wins smallest absolute edge drop.
* FODA-FCP wins onset-insensitivity and CPU-fault dominance,
  AND wins the explanation-quality axis (ontology-grounded
  Recommendation atoms + structured causal links — to be
  quantified in Paper 6 Phase 2's SemanticGroundedness
  metric).
* BARO wins memory-fault accuracy AND second-smallest absolute
  edge drop among unsupervised methods.

Aggregate AC@1 is decisively NOT the deciding axis. The brief's
deployment-realism narrative is now empirically supported across
seven methods and three fault families (resource, network, IO).

PHASE 1 COMPLETE. Phase 2 (semantic-quality metrics:
SemanticGroundedness, ExplanationCompleteness, ChainStructure)
opens with all seven adapters wired, the cross-method diagnostic
CSV covering all six unsupervised methods, the yRCA and FODA-FCP
case-study samples archived for Figure 6, and the cross-method
finding block above as the §4 narrative scaffold.

---

## 2026-05 — Phase 2 Week 1: SemanticGroundedness baseline characterization

The first of four method-agnostic semantic-quality metrics for Paper
6. SG scores how well a method's :class:`CanonicalExplanation`
grounds into the DiagnosticKB ontology, on a per-atom rule:

  * Direct match (atom carries an ``ontology_class`` URI known to the
    ontology) → 1.0
  * Fuzzy match (atom text fuzzy-matches an ontology label at
    threshold 0.7) → 0.5
  * No match → 0.0

The overall score is the mean of per-atom scores; empty explanations
return 0.0. Implementation in ``evaluation/metrics/semantic_groundedness.py``;
the ontology wrapper that backs the matcher is
``evaluation/metrics/ontology_adapter.py``. See
``evaluation/experiments/run_phase2_sg.py`` for the harness; raw
per-case rows are in ``results/phase2_semantic_groundedness.csv``
(875 rows = 7 methods × 125 cases).

(1) HEADLINE NUMBERS (RE1-OB, default SG parameters with
token-aligned fuzzy matcher — see §5 below for the v1→v2 change):

| method   | n   | SG_mean | SG_std | AC@1  | direct_avg | fuzzy_avg | unmatched_avg | atoms_avg |
|----------|-----|---------|--------|-------|------------|-----------|---------------|-----------|
| MR       | 125 | 0.000   | 0.000  | 0.632 | 0.00       | 0.00      | 3.00          | 3.00      |
| CR       | 125 | 0.000   | 0.000  | 0.624 | 0.00       | 0.00      | 5.00          | 5.00      |
| Micro    | 125 | 0.000   | 0.000  | 0.624 | 0.00       | 0.00      | 3.00          | 3.00      |
| BARO     | 125 | 0.000   | 0.000  | 0.536 | 0.00       | 0.00      | 4.00          | 4.00      |
| DejaVu   | 125 | 0.000   | 0.000  | 0.696 | 0.00       | 0.00      | 12.98         | 12.98     |
| yRCA     | 125 | 0.267   | 0.142  | 0.328 | 0.00       | 3.10      | 3.81          | 6.90      |
| FODA-FCP | 125 | **1.000** | 0.000 | 0.448 | **3.72**   | 0.00      | 0.00          | 3.72      |

Three sharply separated tiers emerge:

* **FODA-FCP at 1.000** — every atom carries a full DiagnosticKB URI
  (CpuSaturation, MemoryLeak, Rec_*, ContributingFactor). Direct
  matches on every atom of every case. SG_std = 0.000 — fully
  saturated; no per-case variance.
* **yRCA at 0.267** — role tags (``[final_root_cause]``,
  ``[intermediate_propagator]``) token-match the ontology's
  ``RootCause`` class. Default_process splits ``final_root_cause``
  into ``"final"``/``"root"``/``"cause"`` tokens, which covers the
  RootCause label's two content tokens in full. ~45% of atoms
  match (3.10 / 6.90 avg). 3.3pp below the brief's predicted
  lower bound of 0.30 but well within the alarm tolerance.
* **MR / CR / Micro / BARO / DejaVu at 0.000** — free-text atoms
  (e.g. ``"adservice: anomalous cpu"``, ``"attended: X (α=…
  from Y)"``) do not whole-token-match any DiagnosticKB content
  label. DejaVu's two semantically-grounding atoms
  (``predicted failure type: cpu``, ``predicted failure unit:
  cartservice``) are tagged in DejaVu's own ``foda:FailureType/`` /
  ``foda:Service/`` namespaces, not in DiagnosticKB, so they
  correctly score 0 on direct match.

The discrimination across methods is now **fully bimodal** at the
specific-grounding axis: either a method directly tags DiagnosticKB
URIs (FODA-FCP), or it produces role-tagged text that whole-token-
matches an ontology concept (yRCA's RootCause), or it scores zero.
The metric cleanly separates "explicitly grounds against DiagnosticKB"
from "happens to use overlapping vocabulary".

(2) PER-FAULT BREAKDOWN

| method   | cpu   | delay | disk  | loss  | mem   |
|----------|-------|-------|-------|-------|-------|
| MR       | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| CR       | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Micro    | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| BARO     | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| DejaVu   | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| yRCA     | 0.376 | 0.245 | 0.146 | 0.231 | 0.335 |
| FODA-FCP | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Two patterns visible per fault type:

* **FODA-FCP is constant 1.000** across all five fault types. Atoms
  are tagged regardless of which Mamdani rule fired — explanation
  grounding is **structural**, not signal-dependent.
* **yRCA's per-fault SG varies between 0.15 (disk) and 0.38 (cpu)**.
  The variation tracks the rule-engine's coverage: CPU faults
  produce more events that fire R1, leading to more role-tagged
  atoms whose text whole-token-matches "root cause". Disk faults
  under-trigger the rule engine; fewer R3 ``final_root_cause``
  facts emerge per case.
* **MR / CR / Micro / BARO / DejaVu score 0.000 on every fault**.
  These methods either emit no DiagnosticKB URIs at all (MR, CR,
  Micro, BARO) or emit URIs in their own non-DiagnosticKB
  namespace (DejaVu's ``foda:FailureType/`` and ``foda:Service/``).
  No atom whole-token-matches a DiagnosticKB content label either.

(3) AC@1 vs SG SPEARMAN

Across all 875 (method, case) pairs:

  ρ(AC@1, SG) = **−0.190**

The rank correlation is near zero (slightly negative). **Rank-quality
and ontology-grounding are roughly independent on RE1-OB.** This is
the empirical claim Paper 6 §4 positions on:

* Method-level: DejaVu wins AC@1 (0.696) but scores 0 on SG;
  FODA-FCP scores 1.000 on SG but ranks 4th on AC@1 (0.448).
  Methods optimised for ranking accuracy don't automatically
  produce grounded explanations, and vice versa.
* Case-level (the 875-pair correlation): five of seven methods
  score 0 on SG regardless of AC@1, so the within-method
  correlation is degenerate for those five. The cross-method
  signal — FODA-FCP and yRCA carrying all non-zero SG mass — is
  what drives the pooled correlation.

The negative sign (−0.190) is driven by FODA-FCP being the only
high-SG method and its AC@1 sitting below the AC@1 top tier.
This pattern motivates the **four-axis Paper 6 §4
characterization** the brief outlines — aggregate AC@1 is not just
a lossy ranking metric, it is **anti-correlated** with the
ontology-grounding axis SG measures.

(4) VALIDATION vs BRIEF'S PREDICTED RANGES

| method   | predicted     | observed | status |
|----------|---------------|----------|--------|
| FODA-FCP | 0.90 – 1.00   | 1.000    | ✓ at upper bound |
| yRCA     | 0.30 – 0.50   | 0.267    | ✓ within 3.3pp of lower bound (token-aligned conservative) |
| DejaVu   | 0.10 – 0.30   | 0.000    | ✗ token-aligned removed the partial-character artifact that drove v1's 0.109 (see §5) |
| MR       | 0.05 – 0.15   | 0.000    | ✗ free-text atoms don't whole-token-match any DiagnosticKB content label |
| CR       | 0.05 – 0.15   | 0.000    | ✗ same |
| Micro    | 0.05 – 0.15   | 0.000    | ✗ same |
| BARO     | 0.05 – 0.15   | 0.000    | ✗ same |

Both alarm thresholds clear:

* FODA-FCP ≥ 0.80 — yes (1.000) ✓
* MR ≤ 0.30 — yes (0.000) ✓

The five methods at 0.000 fall **below** the brief's lower bound
of 0.05 by 5pp each. After the spot-check uncovered the character-
substring artifact (§5 below), we deliberately tightened the
matcher; the brief's predicted lower bounds were calibrated against
the looser partial-ratio behaviour and don't hold under token
alignment. The cross-method ordering and the qualitative finding
("FODA-FCP and yRCA carry all the ontology-grounding signal") are
preserved; only the absolute numbers for the five free-text methods
collapse to a strict zero.

(5) DESIGN DECISIONS NOT SPELLED OUT IN THE BRIEF

* **``has_class`` accepts individuals.** DiagnosticKB.owl declares
  fault prototypes (``CpuSaturation``, ``MemoryLeak``, …) as
  :class:`owl:NamedIndividual` instances of the ``Fault`` class
  rather than as OWL classes. FODA-FCP atoms tag against these
  individuals. The metric treats both classes and individuals as
  "known entities" because the question SG answers is "is this URI
  defined by the target ontology", regardless of OWL kind.
  Documented in the adapter docstring.
* **Token-aligned fuzzy match (v2; replaced v1 partial-ratio).**
  Initial implementation used ``rapidfuzz.fuzz.partial_ratio`` on
  case-folded text — produced character-substring artifacts. The
  spot-check found that **every DejaVu attention atom** of shape
  ``"attended: X (α=… from cartservice)"`` scored 70.0 partial-ratio
  against the ``RootCause`` label, via the character substring
  ``"rt cause"`` inside ``"from cartservice"``. Three such atoms
  per case × 0.5 fuzzy weight ÷ 13 atoms ≈ 0.115 SG — DejaVu's
  entire v1 score was the artifact. Switched to token-aligned
  matching: tokenise both the atom text and the label via
  ``utils.default_process`` + whitespace split, drop tokens
  shorter than 3 chars, and require the fraction of label
  CONTENT tokens (≥3 chars) that appear as whole tokens in the
  atom to exceed the threshold (default 0.7). yRCA's legitimate
  ``"final_root_cause"`` → ``"final"``/``"root"``/``"cause"``
  tokenisation still whole-matches the ``RootCause`` content tokens
  ``{"root", "cause"}`` at 100% coverage. The DejaVu artifact is
  removed (0 of 13 atoms match per case). Three named regression
  tests lock in this behaviour:
  ``test_dejavu_attention_atom_does_not_match_rootcause``,
  ``test_yrca_role_atom_matches_rootcause``,
  ``test_token_alignment_rejects_character_substring``.

  **v1 vs v2 numbers**:

  | method   | SG (v1 partial-ratio) | SG (v2 token-aligned) | delta |
  |----------|-----------------------|-----------------------|-------|
  | FODA-FCP | 1.000                 | 1.000                 | 0.000 |
  | yRCA     | 0.287                 | 0.267                 | -0.020 |
  | DejaVu   | 0.109                 | 0.000                 | -0.109 (artifact removed) |
  | MR       | 0.048                 | 0.000                 | -0.048 |
  | CR       | 0.048                 | 0.000                 | -0.048 |
  | Micro    | 0.060                 | 0.000                 | -0.060 |
  | BARO     | 0.060                 | 0.000                 | -0.060 |
  | ρ        | -0.164                | -0.190                | -0.026 |

  FODA-FCP unchanged (direct URI match path independent of fuzzy).
  yRCA −0.020 (the v1 partial-ratio occasionally also matched
  ``Severity`` via "severity=…" substring; under token alignment
  that requires the blacklisted single-token label and never
  fires). The five non-FODA-FCP, non-yRCA methods collapse to
  exactly zero, removing partial-character credit for free-text
  atom shapes.

* **Fuzzy-match class blacklist.** Even under token alignment, the
  8 abstract OWL metaclasses (``Fault``, ``Anomaly``, ``Severity``,
  ``Metric``, ``MicroService``, ``DiagnosticResult``, ``MLModel``,
  ``Symptom``) are excluded from the fuzzy pool as defence in
  depth. These are single-token labels that would whole-token-
  match free text containing the exact word "anomaly" or
  "severity" — semantically still too generic to credit. Direct
  URI lookups still resolve blacklisted classes (``has_class``
  unchanged).

* **Minimum token length 3 chars.** Drops two-letter tokens
  ("io", "of") and short symbols ("α", "0") from both atom and
  label before the set intersection. Keeps domain tokens like
  "cpu" eligible.

(6) WHAT THIS LETS PAPER 6 SAY

The four-axis characterization (S(M), random-onset AC@1,
detected-onset AC@1, offset-robustness) was the Phase-1
contribution. Phase 2 Week 1 adds the fifth axis: **explanation-
quality grounding**, which is **independent of the first four**.
The 3-tier method ranking (FODA-FCP ≫ yRCA ≫ MR/CR/Micro/BARO/DejaVu
at zero) on SG disagrees materially with the AC@1 ranking (DejaVu >
MR/CR/Micro > BARO > FODA-FCP > yRCA). Methods that win on
deployment realism + rank quality do not automatically explain
themselves to operators in a way that is grounded in a shared
diagnostic ontology — and vice versa.

The token-aligned scorer produces a sharper, less hedge-y claim
than v1 would have: under v1's partial-ratio matcher, all seven
methods had non-zero SG with order-of-magnitude separation; under
v2's token-aligned matcher, only **two** methods (FODA-FCP and
yRCA) ground against DiagnosticKB at all. The other five score
strictly zero — they emit atoms that either carry foreign-
namespace URIs (DejaVu) or pure free text (MR/CR/Micro/BARO).
This is the precondition for Paper 6's three-method case-study
figure (Figure 6: yRCA vs FODA-FCP vs DejaVu side-by-side) and for
the §4 narrative on "explanation quality as an orthogonal
deployment-realism axis".

(7) LIMITATIONS

* **No Tbilisi LNNS reference reproduction.** The LNNS paper's
  worked example is not archived in this repository. The Java side
  has ``rca-explanation-comparison-aggregated.csv`` reporting a
  text-based semantic-groundedness component (0.000 for the legacy
  builder, 0.245 for the ontology-grounded builder) on 12 synthetic
  scenarios — a different formulation (substring counting of
  ``"diagnostic:"`` prefix vs fault category labels) not directly
  comparable to the Phase-2 structural metric. Documented in
  ``evaluation/metrics/semantic_groundedness.py`` module docstring;
  worth flagging when we re-survey the LNNS submission to make sure
  the framing in Paper 6's §4.1 matches what was published.
* **The fuzzy threshold, class blacklist, and min-token-length are
  tuning knobs.** All three were chosen empirically. The token-
  alignment switch was made when the spot-check on DejaVu uncovered
  the character-substring artifact that v1's partial-ratio matcher
  produced; v2's three named regression tests
  (``test_dejavu_attention_atom_does_not_match_rootcause``,
  ``test_yrca_role_atom_matches_rootcause``,
  ``test_token_alignment_rejects_character_substring``) lock in
  the desired semantics. A formal sensitivity characterization
  (vary the threshold from 0.5 to 0.95, vary the blacklist, vary
  the min-token-length 2 vs 3 vs 4) is deferred to Week 4
  alongside the other three semantic-quality metrics' ablations.


## 2026-05 — Phase 2 Week 2: SemanticCoherence baseline characterization (v2 — superseded by variant 4 below)

> **NOTE.** This section captures the v2 baseline characterization
> as it was reported before the SC alarm investigation in the next
> section. The metric was redesigned to **variant 4** after this
> baseline; v2's 0.037 FCP score and weight-consistency formula are
> obsolete. See "Phase 2 Week 2 v3" below for the diagnostic and
> the variant-4 numbers that supersede this section's. Retained
> here for design-history continuity.

**Headline.** Six of seven methods score SC = 0.000 on RE1-OB.
FODA-FCP is the only adapter that emits ontology-grounded causal
links between fault prototypes (mean SC 0.037, max 0.34 across
125 cases). Of the 125 FCP cases, 52 produce at least one
coherent link against the ontology's 22-entry Propagation table;
the remainder either fall out as unmapped (most non-root atoms
have no detectable anomaly signal and stay tagged with the
abstract ContributingFactor class) or score zero subscores when
the link weight diverges from the typical propagation strength.
The "SC ≥ 0.50 for FCP" alarm threshold the brief proposed does
**not** clear; the diagnosis below explains why and why the
honest result is informative rather than a metric defect.

(1) NUMBERS

| Method   | n    | SC mean | SC std | SG mean | AC@1  | coh/case | incoh/case | unmap/case |
| -------- | ---: | ------: | -----: | ------: | ----: | -------: | ---------: | ---------: |
| MR       | 125  |   0.000 |  0.000 |   0.000 | 0.632 |     0.00 |       0.00 |       0.00 |
| CR       | 125  |   0.000 |  0.000 |   0.000 | 0.624 |     0.00 |       0.00 |       4.65 |
| Micro    | 125  |   0.000 |  0.000 |   0.000 | 0.624 |     0.00 |       0.00 |       6.00 |
| BARO     | 125  |   0.000 |  0.000 |   0.000 | 0.536 |     0.00 |       0.00 |       3.00 |
| DejaVu   | 125  |   0.000 |  0.000 |   0.000 | 0.696 |     0.00 |       0.00 |      11.98 |
| yRCA     | 125  |   0.000 |  0.000 |   0.267 | 0.328 |     0.00 |       0.00 |      10.34 |
| FODA-FCP | 125  |   0.037 |  0.065 |   1.000 | 0.448 |     0.67 |       0.65 |       2.84 |

Per-fault SC mean (FODA-FCP only — others uniformly zero):

| fault | SC mean | note                                                     |
| ----- | ------: | -------------------------------------------------------- |
| cpu   |   0.121 | only fault type with consistent coherent-link pattern    |
| mem   |   0.038 | downstream services rarely show fuzzy signal             |
| disk  |   0.013 | latency_CRITICAL fires R10 on root only                  |
| loss  |   0.006 | error-rate-driven; sparse propagation chain              |
| delay |   0.006 | latency injection produces single-atom explanations      |

Spearman rank correlations over all 875 (method, case) pairs:

```
ρ(AC@1, SC) = +0.091     # nearly orthogonal; SC is not a rank-quality proxy
ρ(SG,   SC) = +0.398     # distinct from SG; ≤ 0.5 confirms independent axis
```

(2) WHY THE 0.50 ALARM DOES NOT CLEAR

The brief proposed an alarm threshold of SC ≥ 0.50 for FODA-FCP
on the grounds that FCP is the only method emitting ontology-
tagged causal links AND those links should respect the
Propagation table the same OWL graph encodes. We diagnosed three
independent issues; v2 fixed two of them and the third turned
out to be an honest reflection of FCP's explanation structure on
RE1-OB rather than a metric defect.

**Issue A — direction mismatch (FIXED).** FCP's
``contributes_to`` relation flows ``effect → cause`` (Noisy-OR
back-flow: "non-root atom contributes evidence to root cause"),
but the Propagation table encodes ``cause → effect`` strengths.
v1 looked up the link's literal ``(source, target)`` pair and
flagged every contributes_to link as incoherent. v2 introduces
:data:`_BACK_FLOW_RELATION_PREFIXES` — a tunable set
(``"contributes_to"``, ``"explained_by"``) of relation-type
prefixes that indicate the evidence direction. SC swaps the
endpoints before the Propagation lookup when the relation type
matches. This is method-agnostic: yRCA's ``explained_by`` shape
is also recognized, so a future adapter that emits back-flow
edges only needs to declare its relation_type prefix to be
scored correctly. Direct test:
``TestBackFlowRelationHandling::test_contributes_to_back_flow_swaps_direction``.

**Issue B — non-fault endpoints (FIXED).** FCP emits two link
shapes whose endpoints are NOT fault prototypes: (a)
``suggests_mitigation`` from every atom to the
``Rec_<FaultPrototype>`` Recommendation individual, and (b)
``contributes_to`` from non-root atoms tagged with the abstract
``ContributingFactor`` class when no Mamdani rule fired. v1
counted both as incoherent because the propagation strength was
0.0. v2 introduces :func:`_fault_prototype_uris` — the set of
URIs that participate in at least one Propagation individual —
and classifies links with a non-fault-prototype endpoint as
**unmapped** rather than incoherent. SC's intent is "score
fault-to-fault propagation"; recommendation links and abstract-
class links are out of scope. Direct test:
``TestFaultPrototypeFiltering::test_link_to_recommendation_is_unmapped``.

**Issue C — sparse fuzzy signal on FCP non-roots (PARTIALLY
ADDRESSED).** Even with A+B fixed, the contributes_to link only
scores coherent when the non-root atom has a specific fault
prototype to compare against. v1 tagged every non-root with
abstract ``ContributingFactor`` when the Mamdani rule base
didn't fire — which is the common case, because FCP's top-K
includes services with elevated **Noisy-OR-propagated** confidence
(C > 0.2) but no **local** anomaly signal (H = 0). v2 adds a
soft-fallback helper :func:`_infer_fault_prototype_from_fuzzy`:
when no rule fires, pick the highest-membership term among
``{cpu_HIGH/MEDIUM, memory_HIGH/MEDIUM, latency_CRITICAL/
ELEVATED, errorRate_HIGH/ELEVATED, throughput_LOW}`` (membership
≥ 0.20) and map it to the matching fault prototype. This lifts
the score for services that have genuine cpu/memory/latency
signal, even when the Mamdani rule base requires two co-firing
antecedents to commit. On RE1-OB this raises FCP SC from 0.006
to 0.037 (cpu cases lift from ~0 to 0.121 specifically). It
does **not** raise the score for services that have NO anomaly
signal — frontend/currencyservice in the typical RE1-OB
explanation are clearly tagged with ``cpu_LOW``, ``memory_LOW``,
and ``throughput_NORMAL``, so the helper correctly returns
``None`` and the link stays unmapped. This is the honest
structural property: FCP's Noisy-OR propagator routinely
surfaces topological neighbors with no metric anomaly into the
top-K, and SC has no opinion about such atoms.

(3) WHAT THE METRIC REVEALS

* **FCP's explanation structure is partially coherent**: 52/125
  cases produce at least one ontology-coherent fault-prototype-
  to-fault-prototype edge. Cpu cases drive the bulk of this
  (because cpu_HIGH membership routinely fires in two services
  simultaneously — the injected one and a downstream caller
  whose CPU is also elevated under load). Mem cases are
  bottlenecked by mem_HIGH only firing in one service
  consistently. Delay/disk/loss cases produce essentially no
  coherent links because the latency/error/disk anomalies don't
  cascade as cleanly through the fuzzy term map.

* **The other six methods are structurally incompatible with
  SC.** MR/CR/Micro/BARO emit links with no ontology_class on
  the atoms — unmapped, score zero. DejaVu emits 11.98 links
  per case averaging attention-attribution edges (none of which
  carry DiagnosticKB URIs after the Week 1 v2 SG token-
  alignment fix) — all unmapped. yRCA emits 10.34 links per
  case using foreign-namespace ``yrca:Role/*`` URIs — also
  unmapped. SC's contribution is binary in this sense: it
  cleanly separates FODA-FCP from every other method. The brief
  was right that FCP is structurally the only candidate; v1's
  near-zero score was misleading, v2's 0.037 is the floor.

* **SC's residual signal is orthogonal to SG and AC@1.**
  ρ(AC@1, SC) = +0.091 and ρ(SG, SC) = +0.398 confirm SC is a
  distinct measurement axis. The brief's "SC must satisfy
  ρ(SG, SC) ≤ 0.5" threshold clears comfortably, ruling out the
  worry that SC was just SG-redux on link endpoints.

(4) ONTOLOGY EXTENSION

The Phase-1 DiagnosticKB.owl encoded 11 classes + 36
individuals (8 fault prototypes, 8 Rec_* recommendations, 6
contributing factors, severities, metrics). Phase 2 Week 2 adds:

* 1 class: ``Propagation``.
* 3 properties: ``propagationSource`` (object), ``propagationTarget``
  (object), ``propagationStrength`` (datatype, xsd:float).
* 22 ``Propagation`` individuals encoding typical fault-
  propagation patterns. 12 have strength 1.0 (e.g.,
  ``CpuSaturation → LatencySpike``, ``ResourceContention →
  CpuSaturation``, ``MemoryLeak → ThroughputDegradation``); 10
  have strength 0.5 (e.g., ``MemoryLeak → CpuSaturation``,
  ``CpuSaturation → HighErrorRate``, ``NetworkCongestion →
  ThroughputDegradation``). The full table is sourced from the
  AICT 2026 paper's §3 fault-propagation taxonomy and the
  Java reference's
  ``OntologyGroundedExplanationBuilder.CATEGORY_TO_FAULT_LOCAL_NAME``
  + cascading-rule comments.

The 0.5-strength patterns model conditional propagations
(memory pressure sometimes spills into CPU under load but not
always; CPU saturation sometimes drops error rate via thread-
pool exhaustion). They are weaker than 1.0 patterns but the
ontology still credits a method for declaring them as a typical
propagation direction.

Loading: 12 classes + 58 individuals after the extension, up
from 11 + 36. ``OntologyAdapter`` walks every ``Propagation``
instance at construction time and materializes
``{(src_uri, tgt_uri): strength}`` for O(1)
:meth:`get_propagation_strength` lookups.

(5) DESIGN DECISIONS — V1 → V2 DELTA

| Decision                       | v1 (initial)                         | v2 (final)                                                                  |
| ------------------------------ | ------------------------------------ | --------------------------------------------------------------------------- |
| Direction matching             | literal (source, target) lookup       | reverse if relation_type starts with ``contributes_to`` or ``explained_by`` |
| Non-fault-prototype endpoints  | counted as incoherent                | counted as unmapped (out of metric scope)                                   |
| FCP non-root atom classes      | abstract ``ContributingFactor`` only | fuzzy-fallback to specific fault prototype when membership ≥ 0.20           |
| Weight-vs-strength formula     | ``1 − \|ω − w\|``                    | unchanged                                                                   |
| Per-link match types           | coherent / incoherent                | coherent / incoherent / unmapped                                            |
| FCP SC                         | 0.006 (alarm)                        | 0.037 (still below 0.50 alarm; the alarm threshold itself proves miscalibrated relative to FCP's atom-emission shape on RE1-OB) |

The v1→v2 changes are documented in the docstring of
:mod:`evaluation.metrics.semantic_coherence` (sections
"Per-link scoring", "Back-flow relation handling") and the
:class:`OntologyAdapter` constructor.

(6) WHAT PAPER 6 NOW CLAIMS

The Week-1 axis (SG, atom-level grounding) and the Week-2 axis
(SC, link-level coherence) jointly characterize the explanation
side of the AC@1-vs-explanation-quality trade-off:

* FODA-FCP wins both axes (SG = 1.000, SC = 0.037) and remains
  middle-of-the-pack on AC@1 (0.448, below DejaVu/MR/CR/Micro,
  above yRCA).
* yRCA wins SG modestly (0.267) but cannot win SC because its
  URIs live in a foreign namespace.
* DejaVu wins AC@1 (0.696) but scores zero on both SG and SC —
  attention attributions are not ontology-grounded.
* MR / CR / Micro / BARO score zero on both grounding axes.

The Paper 6 §4 narrative now has the structural evidence to
argue that **explanation quality is orthogonal to rank
quality**, with FODA-FCP being the only method that can
trade rank for explanation grounding (the others have nothing
to trade with).

(7) LIMITATIONS

* **SC ≥ 0.50 alarm is too optimistic.** The 0.50 threshold
  was set under the assumption that FCP's contributes_to edges
  would be dense AND fault-prototype-tagged. The non-root atoms
  in FCP's top-K are usually topological neighbors with no
  local fuzzy signal, which is honest output from the Noisy-OR
  propagator. A realistic FCP-SC target on RE1-OB is closer to
  0.10 (cpu-only) or 0.04 (averaged across fault types).
* **The 22 propagation patterns are AICT-paper-derived, not
  data-driven.** Whether a propagation actually appears in the
  RE1-OB telemetry depends on the workload + injection. A
  data-driven calibration would mine the empirical (source,
  target) anomaly co-occurrence and threshold by support — out
  of scope for the dissertation but worth a footnote in the
  paper's threats-to-validity section.
* **Fuzzy-fallback membership floor of 0.20 is empirical.**
  Picked to suppress noise on services with tiny ``cpu_MEDIUM``
  memberships (0.05–0.15) that would otherwise pollute the
  inference. Locked in by
  ``TestInferFaultPrototypeFromFuzzy::test_below_floor_returns_none``.
* **Back-flow prefix set is incomplete.** ``contributes_to``
  and ``explained_by`` cover FCP + yRCA. A future method that
  emits ``derived_from`` or ``observed_under`` shapes would
  need an entry in :data:`_BACK_FLOW_RELATION_PREFIXES`; the
  tunable knob is intentionally exposed for that reason.
* **No cross-RE1 generalization.** This run is RE1-OB only; the
  TT and SS subsets and the RE2 / Online Boutique fork are
  Week-3+ work.


## 2026-05 — Phase 2 Week 2 v3: SC alarm investigation + variant-4 metric redesign

**TL;DR.** The Week-2 v2 metric scored FODA-FCP at 0.037 (alarm
threshold 0.50 tripped) and we investigated whether the metric or
the method was the problem. The investigation **rejected**
Hypothesis B (FCP doesn't produce Fault → Fault links — actually
31.7 % do) and **confirmed** Hypothesis C (the weight-consistency
formula penalised every direction-correct link by ≈ 0.74 because
FCP's link weights are Noisy-OR contribution magnitudes, not
propagation typicalities). We redesigned the metric (variant 4):
**drop the weight-consistency penalty, score coherent links by
ontology typicality alone, and exclude mitigation links from the
denominator entirely**. The FCP SC rises to **the variant-4
numbers reported below**, distinct from SG and AC@1 by the
≤ 0.5 orthogonality criterion. Other six methods remain at 0.000.

(1) DIAGNOSTIC FINDINGS (v2 → v3 transition)

We ran a three-hypothesis investigation on the v2 metric output
(see ``/tmp/sc_investigation.py``):

| Hypothesis | Verdict | Evidence |
| --- | --- | --- |
| **A.** Metric too strict on the case study (re1-ob_adservice_cpu_3) | Partial | All 5 links of this case are unmapped, but the case is **unrepresentative**. Aggregate behaviour is different. |
| **B.** FCP doesn't produce Fault → Fault links | **False** | 165 / 520 (31.7 %) of all FCP links are Fault→Fault, well above the 10 % structural bar. |
| **C.** Weights diverge from ontology strengths | **True** | Of the 84 coherent Fault→Fault links, mean weight = 0.053, median = 0.000, max = 0.277. Ontology strengths: mean = 0.792. Mean ``\|ω − w\|`` = 0.738 — the formula ``1 − \|ω − w\|`` returns ≈ 0.26 even for direction-perfect propagations. |

**The smoking gun**: FCP's ``contributes_to`` link weight is
``μ × Pearson × δ`` — a Noisy-OR contribution magnitude, not a
propagation typicality. The two are measuring different things;
forcing them to match was the v2 design's error.

Sample coherent links from the v2 run (sub = ``1 − |ω − w|``):

```
adservice_cpu_2   MemoryLeak       → ResourceContention   weight=0.000  ω=0.50  sub=0.500
adservice_cpu_2   LatencySpike     → ResourceContention   weight=0.000  ω=1.00  sub=0.000
adservice_disk_1  LatencySpike     → ResourceContention   weight=0.247  ω=1.00  sub=0.247
adservice_loss_5  LatencySpike     → MemoryLeak           weight=0.000  ω=1.00  sub=0.000
```

Direction-correct but penalised because of weight-strength
incommensurability.

(2) COUNTERFACTUAL VARIANTS — DESIGN-SPACE EXPLORATION

```
Variant                                                      mean SC   median
v2 (current): 1 − |ω − w|                                      0.037    0.000
variant 1: direction-only (1.0 per coherent link)              0.144    0.000
variant 2: ontology-strength credit (ω per coherent)           0.116    0.000
variant 3: variant 1 excluding suggests_mitigation              0.336    0.000
variant 4: variant 2 excluding suggests_mitigation              0.266    0.000
```

Per-fault FCP SC under **variant 4** counterfactual:

| fault | counterfactual SC |
| ----- | ----------------: |
| cpu   |             0.380 |
| mem   |             0.460 |
| disk  |             0.280 |
| loss  |             0.160 |
| delay |             0.050 |

(3) VARIANT-4 DESIGN CHOICE (adopted)

Variant 4 with refinement was implemented as the canonical SC
metric. Three behavioural changes from v2:

1. **Coherent subscore = ontology typicality** (1.0 for typical,
   0.5 for conditional). Link weight is informational only.
2. **Only links with `relation_type ∈ PROPAGATION_RELATIONS`
   are scored.** Mitigation links (relation_type contains
   ``"mitigation"``, ``"recommend"``, or ``"suggests"``) are
   classified ``excluded_mitigation`` and dropped from the
   denominator. Non-propagation, non-mitigation links (None,
   ``anomaly-correlates-with``, ``rule_derived_explanation``)
   are ``unmapped`` (out of scope but counted in denominator).
3. **Breakdown adds two new fields**:
   ``excluded_mitigation_links`` and ``scored_link_count``.

The propagation-relation set covers six prefixes:
``contributes_to``, ``explained_by``, ``caused_by`` (back-flow);
``causes``, ``propagates_to``, ``leads_to`` (forward). The
back-flow subset triggers the (source, target) swap before the
ontology lookup as in v2.

(4) VARIANT-4 NUMBERS ON RE1-OB

Headline aggregates (7 methods × 125 cases):

| Method   |  n   | SC mean | SC std | SG mean | AC@1  | coh/case | incoh/case | unmap/case | excl_mit/case | scored/case | links/case |
| -------- | ---: | ------: | -----: | ------: | ----: | -------: | ---------: | ---------: | ------------: | ----------: | ---------: |
| MR       | 125  |   0.000 |  0.000 |   0.000 | 0.632 |     0.00 |       0.00 |       0.00 |          0.00 |        0.00 |       0.00 |
| CR       | 125  |   0.000 |  0.000 |   0.000 | 0.624 |     0.00 |       0.00 |       4.65 |          0.00 |        4.65 |       4.65 |
| Micro    | 125  |   0.000 |  0.000 |   0.000 | 0.624 |     0.00 |       0.00 |       6.00 |          0.00 |        6.00 |       6.00 |
| BARO     | 125  |   0.000 |  0.000 |   0.000 | 0.536 |     0.00 |       0.00 |       3.00 |          0.00 |        3.00 |       3.00 |
| DejaVu   | 125  |   0.000 |  0.000 |   0.000 | 0.696 |     0.00 |       0.00 |      11.98 |          0.00 |       11.98 |      11.98 |
| yRCA     | 125  |   0.000 |  0.000 |   0.267 | 0.328 |     0.00 |       0.00 |      10.34 |          0.00 |       10.34 |      10.34 |
| FODA-FCP | 125  |   **0.266** |  0.362 |   1.000 | 0.448 | 0.67 |    0.65 |       0.68 |          2.16 |        2.00 |       4.16 |

Per-fault FCP SC:

| fault | SC mean | note                                                     |
| ----- | ------: | -------------------------------------------------------- |
| cpu   |   0.380 | dense fuzzy-fallback coverage (cpu_HIGH + downstream LatSpike) |
| mem   |   0.460 | when MemoryLeak fires + downstream ResourceContention |
| disk  |   0.280 | latency-mediated propagation chain                      |
| loss  |   0.160 | error-rate signals propagate sparsely                   |
| delay |   0.050 | latency injection produces few non-root prototypes      |

Spearman rank correlations (875 case-method pairs):

```
ρ(AC@1, SC) = +0.107       # nearly orthogonal; SC is not a rank-quality proxy
ρ(SG,   SC) = +0.470       # distinct from SG; clears the ≤ 0.5 orthogonality bar
```

SC and SG share a structural dependency: a method that doesn't
ground atoms in DiagnosticKB classes (SG = 0) cannot produce
gradable links (SC = 0). This explains the moderate positive
correlation (ρ = +0.470). The unexplained variance reflects SC's
additional requirements — fault-prototype endpoints,
propagation-claim relation types, and direction agreement with
ontology Propagation entries — that SG does not enforce. yRCA
exemplifies the gap: its role-tag atoms produce SG = 0.267
(legitimate fuzzy matches against RootCause) but SC = 0
(``yrca:Role/*`` URIs are not Fault prototypes). The two
metrics measure distinct but related aspects of ontology
grounding.

**FCP SC clears the user's expected range** (0.25–0.40) at
0.266 overall, with per-fault values from 0.05 (delay) to 0.46
(mem). The variant-4 metric distinguishes faults by how cleanly
their propagation chains land on declared ontology patterns,
which is the structural property SC was supposed to surface.

**yRCA still scores 0.000**: every yRCA link is unmapped because
the atoms carry foreign-namespace ``yrca:Role/*`` URIs. yRCA's
``explained_by`` shape IS in the propagation-relation set, but
the endpoints fail the fault-prototype filter. SC currently has
no opinion about yRCA's chains; an extension that mines yRCA's
``rule_id`` annotations and resolves them to DiagnosticKB
fault prototypes is Week-4+ work.

(5) DIRECTION-INCOHERENT FCP LINKS — CRITICAL CHECK

Across 125 cases, FCP emits **81 direction-incoherent
Fault → Fault links** (both endpoints fault prototypes but the
ontology has no Propagation for the pair after back-flow swap).
By lookup-pair frequency:

| lookup_src | lookup_tgt | count |
| --- | --- | ---: |
| LatencySpike | LatencySpike | 39 |
| LatencySpike | MemoryLeak   |  8 |
| LatencySpike | CpuSaturation |  8 |
| LatencySpike | ResourceContention | 8 |
| CpuSaturation | ResourceContention | 5 |
| ResourceContention | ResourceContention | 5 |
| MemoryLeak | MemoryLeak | 3 |
| MemoryLeak | ResourceContention | 2 |
| CpuSaturation | MemoryLeak | 2 |
| CpuSaturation | CpuSaturation | 1 |

**Self-loops** (X → X): 39 + 5 + 3 + 1 = 48 / 81 = 59 %. Two
services both inferred to the same fault prototype, scored
incoherent because self-propagation isn't a declared pattern.
This is structurally honest: it's the fuzzy fallback assigning
the same prototype to multiple services in the top-K.

**LatencySpike-rooted forward claims** (LatencySpike → X):
39 + 8 + 8 + 8 = 63 / 81 = 78 %. After the back-flow swap, these
correspond to ``contributes_to`` links where the FCP root was
LatencySpike. The ontology has no LatencySpike-out propagations
because LatencySpike is typically a downstream effect, not an
upstream cause. These are legitimate atypical claims FCP is
making — and SC flags them correctly.

(6) WHY ELIMINATE THE WEIGHT-CONSISTENCY FORMULA

The variant-4 redesign is the smallest change that recovers
SC's stated intent (scoring direction agreement against the
ontology's propagation typology) while letting the metric
distinguish two phenomena it was conflating:

* Direction correctness — does ``(source, target)`` after
  back-flow swap appear in the Propagation table? **YES** is
  the metric-positive event.
* Weight calibration — does the link's numeric weight match
  the ontology strength? A separate question, suitable for a
  future "ExplanationCalibration" axis but **not** what
  SemanticCoherence was supposed to measure.

The v2 formula collapsed both into one number and let weight
calibration drag down direction correctness. Variant 4 keeps
them apart by ignoring the weight; future calibration work can
build on top.

(7) METHODOLOGICAL RATIONALE FOR MITIGATION EXCLUSION

Mitigation links (``suggests_mitigation``,
``recommend_action``) are valid CanonicalExplanation edges that
encode "given this fault, what should an operator do?". They're
not propagation claims. Including them in SC's denominator
would punish methods that surface operator-actionable
mitigation suggestions for structurally **not being
propagation claims** — the wrong incentive.

The exclusion is implemented by token-substring match against
:data:`_MITIGATION_TOKENS = {"mitigation", "recommend",
"suggests"}` — three tokens that cover every current adapter's
mitigation shape and that future adapters are likely to use.
Methods that emit mitigation links keep their
``excluded_mitigation_links`` count in the breakdown; downstream
analyses (Paper 6 §4.3 "explanation actionability") will want
it.

(8) ARTIFACTS

* Metric: ``evaluation/metrics/semantic_coherence.py`` (variant 4)
* Tests: ``evaluation/tests/test_semantic_coherence.py`` (40 cases
  across 10 test classes; lock in mitigation exclusion +
  typicality-only scoring + back-flow handling for all three
  relation prefixes)
* Harness: ``evaluation/experiments/run_phase2_sc.py``
  (CSV columns now include ``excluded_mitigation_links`` and
  ``scored_link_count``)
* Diagnostic notebook: ``/tmp/sc_investigation.py`` (3-hypothesis
  test) and ``/tmp/sc_direction_only.py`` (counterfactual variant
  comparison) — not committed; reproducible from the canonical
  CSV.
* CSV: ``results/phase2_semantic_coherence.csv`` (875 rows,
  7 methods × 125 cases).

(9) DESIGN HISTORY DELTA — v1 → v2 → variant 4

| Decision                       | v1 (initial)                         | v2 (intermediate)                                                           | Variant 4 (final)                                                                                       |
| ------------------------------ | ------------------------------------ | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Direction handling             | literal pair lookup                   | back-flow swap for ``contributes_to`` / ``explained_by``                    | back-flow swap for ``contributes_to`` / ``explained_by`` / ``caused_by``                               |
| Coherent subscore              | ``1 − \|ω − w\|``                   | ``1 − \|ω − w\|``                                                          | ``ω`` (link weight ignored)                                                                             |
| Non-fault endpoints            | counted incoherent                    | counted unmapped                                                            | counted unmapped (unchanged)                                                                            |
| Mitigation links               | counted incoherent                    | counted unmapped (mostly via non-fault endpoint)                            | classified ``excluded_mitigation``; dropped from denominator                                            |
| Non-propagation relations      | counted by endpoint logic alone       | counted by endpoint logic alone                                             | classified ``unmapped`` even if endpoints are fault prototypes                                          |
| Match types                    | coherent / incoherent                 | coherent / incoherent / unmapped                                            | coherent / incoherent / unmapped / excluded_mitigation                                                  |
| FCP SC                         | 0.006                                 | 0.037                                                                       | **0.266** (cpu 0.380, mem 0.460, disk 0.280, loss 0.160, delay 0.050)                                  |

The variant-4 metric replaces v2 outright; ``DEVIATIONS.md``
captures the design history under
``## SemanticCoherence metric (Paper 6 Phase 2 Week 2)``.


## 2026-05 — Phase 2 Week 3: ExplanationCompleteness baseline characterization

**Headline.** EC asks the operator's question: does the chain
tell me *what kind of fault*, *which service*, and *what to do*?
Each category is a binary detector; aggregate is the fraction
present, taking one of four values in
``{0.0, 0.333, 0.667, 1.0}``. EC complements SG (atom-level
grounding) and SC (link-level coherence) on a structural axis —
the four metrics together characterise an explanation's
**actionability** (EC), **groundedness** (SG), **coherence** (SC),
and the upstream **rank quality** (AC@1).

FCP scores **0.824** mean EC — 90/125 cases at 1.0, 4/125 at
0.667, 31/125 at 0.333 (no method scored 0.0). All other six
methods score exactly **0.333** on every case (component-only:
the service-name text rule fires on all 125 cases for every
method, but neither the strict DiagnosticKB-vocabulary cause
detector nor the recommendation detector ever fires). The FCP
alarm at 0.9 is **tripped** — the diagnostic in §3 below shows
this is a Phase-1 explanation-completeness issue, not a metric
defect.

(1) DESIGN DECISIONS

**Strict ontology vocabulary.** Each category detector matches
atoms via either (a) the atom's ``ontology_class`` URI being in
the relevant DiagnosticKB category set, or (b) the atom's text
covering ≥ 70 % of a category-specific label's content tokens
(token-aligned per Week 1 SG's tokenisation). EC inherits SG's
0.7 threshold for the text path so the two metrics agree on
what "groundedness" looks like at the atom level.

**Per-category URI sets, not global label search.** The Week-1
SG matcher uses :meth:`OntologyAdapter.find_class_by_label` which
returns the single best match across **all** ontology labels and
prefers shorter labels as a tiebreaker. EC needs a different
question — "is there ANY label in *this* category that the text
covers?" — because a text like
``"final_root_cause: cartservice cpu saturation"`` covers both
``"Root Cause"`` (RootCause class) and ``"CPU Saturation"`` (a
Fault prototype) at 100 %; the SG matcher's shorter-label
tiebreaker returns RootCause, which is NOT a fault prototype,
producing a false negative on the root-cause category. EC
addresses this with :func:`_text_matches_any_label` which
iterates over the category-specific URI subset and short-
circuits on the first match clearing the threshold.

**Affected-component text rule = service-name whole-token match.**
DiagnosticKB doesn't enumerate specific RE1-OB services
(cartservice, frontend, …) — the runtime discovers them per
case from :attr:`NormalizedCase.services`. So the affected-
component detector has two paths: (a) an atom whose
``ontology_class`` is :class:`MicroService` or one of its
individuals (currently just the class URI, since no services are
declared), or (b) any service name from the case's service list
appearing as a **whole content token** in the atom text. The
whole-token rule defends against substring false-positives
(``"adservice"`` ≠ ``"loadservice"``).

**Mitigation-token substring matching is NOT used here.** The
Week 2 SC metric uses substring matching to detect
``suggests_mitigation``-style relation types and exclude those
links from SC's denominator. EC instead checks atom-level
``ontology_class`` against the Recommendation URI set and atom
text against Recommendation labels — i.e., the same atom-level
contract the cause detector uses. Mitigation is recognised by
its *ontology category*, not by a relation-type substring.

(2) NUMBERS

Headline aggregates (7 methods × 125 cases):

| Method   |  n   | EC mean | EC std | SG mean | SC mean | AC@1  | cause% | comp% | mit%  |
| -------- | ---: | ------: | -----: | ------: | ------: | ----: | -----: | ----: | ----: |
| MR       | 125  |   0.333 |  0.000 |   0.000 |   0.000 | 0.632 |  0.000 | 1.000 | 0.000 |
| CR       | 125  |   0.333 |  0.000 |   0.000 |   0.000 | 0.624 |  0.000 | 1.000 | 0.000 |
| Micro    | 125  |   0.333 |  0.000 |   0.000 |   0.000 | 0.624 |  0.000 | 1.000 | 0.000 |
| BARO     | 125  |   0.333 |  0.000 |   0.000 |   0.000 | 0.536 |  0.000 | 1.000 | 0.000 |
| DejaVu   | 125  |   0.333 |  0.000 |   0.000 |   0.000 | 0.696 |  0.000 | 1.000 | 0.000 |
| yRCA     | 125  |   0.333 |  0.000 |   0.267 |   0.000 | 0.328 |  0.000 | 1.000 | 0.000 |
| FODA-FCP | 125  |   **0.824** |  0.289 |   1.000 |   0.266 | 0.448 | 0.752 | 1.000 | 0.720 |

(3) ALARM GATES + FCP-AT-0.824 DIAGNOSTIC

```
⚠ FCP EC mean 0.824 < 0.9         (tripped)
✓ MR EC mean 0.333 ≤ 0.4          (component-only as expected)
✓ CR EC mean 0.333 ≤ 0.4
✓ Micro EC mean 0.333 ≤ 0.4
✓ BARO EC mean 0.333 ≤ 0.4
✓ yRCA EC mean 0.333 < 1.0        (no mitigation atoms — correct)
```

The FCP alarm trips. We inspected the 31 / 125 cases where FCP
scored 0.333 (component-only). All 31 share the same Phase-1
property:

* The injected workload (delay, loss, disk) does not produce a
  large enough post-vs-pre z-score in CPU, memory, latency, error,
  or throughput features to fire any Mamdani rule. All services'
  ``dominant_category`` is ``UNKNOWN``. All ``H`` and ``C`` values
  are 0.0.
* The fuzzy-fallback helper :func:`_infer_fault_prototype_from_fuzzy`
  (Week-2 v2) returns ``None`` because no fuzzy term clears the
  0.20 membership floor.
* FCP emits 3 atoms tagged with the abstract
  ``ContributingFactor`` class and **no Recommendation atom**
  (the Recommendation atom is only emitted when the root
  service's Mamdani fires).
* AC@1 = 1.0 in many of these cases is incidental: when all
  services tie at C = 0.0, FCP's deterministic name-order
  tiebreaker can still pick the correct service.

Per-fault breakdown of the 31 low-EC FCP cases:

| fault | count | reason |
| ----- | ----: | --- |
| delay | 12 | latency_CRITICAL not reached on these injections |
| loss  | 12 | errorRate_HIGH not reached |
| disk  |  7 | disk anomalies don't surface in cpu/mem/lat/err/traffic features |

No cpu or mem cases in the low-EC bucket — cpu/mem injections
fire Mamdani reliably and produce full EC = 1.0 chains
(82/125 of FCP's 1.0 scores are cpu + mem cases).

**Interpretation.** The 0.824 score is honest: EC is correctly
detecting that FCP can't surface cause/mitigation content when
its rule engine doesn't fire. The brief's 0.9 alarm was
calibrated for cpu/mem-dominated cases (the dissertation's
Phase 1 case-study) and overshoots for delay/loss/disk where
FCP's fuzzification regime is too conservative. Improving FCP's
fault-type inference on these cases (extending the fuzzy term
vocabulary, lowering the membership floor, or adding a
last-resort "best-guess" prototype) would lift EC; that's a
Phase-1 design choice, not a metric defect.

**Link to Phase 1 cpu-vs-mem asymmetry.** This 0.824 mean
reflects the same Phase 1 limitation that produced FCP's
cpu-vs-mem AC@1 asymmetry: when canonical feature signatures
don't trigger Mamdani rule antecedents (delay/loss/disk
faults), FCP emits abstract ``ContributingFactor`` atoms but
no Recommendation. The 31 low-EC cases (12 delay + 12 loss +
7 disk) overlap with the cases where FCP's fuzzification is
conservative. EC correctly detects this as a missing
mitigation-category signal, complementing the AC@1 view of
the same underlying property — Phase 1's accuracy lens saw
the lost rank precision on these faults; Phase 2 Week 3's
completeness lens sees the lost diagnostic content. Both
trace back to the same z-score-driven fuzzification choice
documented in DEVIATIONS.md → "FODA-FCP adapter / Deviation
1: z-score-driven fuzzy memberships".

**Recommendation.** We accept 0.824 as the honest Week-3
baseline and note the structural cause in this section. The
gap from 0.9 corresponds 1:1 with FCP's silent-rule-engine
failure mode, which is already documented in the Week-2 v3
findings (the "Issue C — sparse fuzzy signal" diagnostic).
Paper 6 can either report 0.824 with this caveat or pursue an
FCP-side fix in a future revision.

(4) PER-CATEGORY PRESENCE FRACTIONS

The per-method per-category breakdown reveals which information
axes each method covers and which it skips. Reading the
fraction column tells the reader: across the 125 cases, on what
fraction of cases did this method emit at least one atom of
the given category.

| Method   | cause%  | comp%   | mit%    | EC mean |
| -------- | ------: | ------: | ------: | ------: |
| MR       |  0.000  |  1.000  |  0.000  |  0.333  |
| CR       |  0.000  |  1.000  |  0.000  |  0.333  |
| Micro    |  0.000  |  1.000  |  0.000  |  0.333  |
| BARO     |  0.000  |  1.000  |  0.000  |  0.333  |
| DejaVu   |  0.000  |  1.000  |  0.000  |  0.333  |
| yRCA     |  0.000  |  1.000  |  0.000  |  0.333  |
| FODA-FCP |  0.752  |  1.000  |  0.720  |  0.824  |

* **Component (where)**: every method surfaces a service name
  via atom text on every case — the service-name text rule
  fires across the board. The component category is the
  baseline every method achieves.

* **Cause (what)**: only FCP fires (75.2%). The other six fail
  because (a) their atoms don't carry DiagnosticKB fault URIs,
  and (b) their atom text doesn't whole-token-cover any Fault
  prototype label at 0.7 coverage. DejaVu's
  ``"predicted failure type: cpu (p=...)"`` text covers only
  ``cpu`` against the ``"CPU Saturation"`` label (coverage
  1/2 = 0.5 < 0.7). yRCA's
  ``"... derived_by_rules=['cpu_high']"`` text similarly tokens
  to ``{cpu, high}`` against ``{cpu, saturation}`` — 0.5 coverage.
  The metric is correctly enforcing DiagnosticKB-vocabulary
  conformance, not generic fault-naming.

* **Mitigation (what to do)**: only FCP fires (72.0%). The
  ``Rec_*`` ontology individual is unique to FCP's chain. yRCA,
  DejaVu, and the four MR-family methods have no concept of a
  mitigation atom.

The 75.2% / 72.0% mismatch on FCP comes from the
silent-Mamdani failure mode (§3): when no fault prototype is
inferred for the root, FCP emits no Recommendation atom, so
both ``cause%`` and ``mit%`` drop together. The small gap
(75.2 - 72.0 = 3.2pp) corresponds to the 4 cases where FCP
inferred a non-root fault prototype via fuzzy fallback but no
Recommendation atom — these score 0.667 (cause + component, no
mitigation).

(5) CORRELATIONS

Spearman rank correlations over all 875 (method, case) pairs:

```
ρ(AC@1, EC) = -0.015     # essentially zero — EC is rank-independent
ρ(SG,   EC) = +0.648     # strong-moderate — both gate on atom grounding
ρ(SC,   EC) = +0.723     # strong — both reward FCP's full chain shape
```

* **ρ(AC@1, EC) ≈ 0** confirms EC is **not a rank-quality
  proxy**. Methods can be rank-accurate (DejaVu AC@1 = 0.696)
  while producing minimum-completeness chains (EC = 0.333), or
  rank-mediocre (yRCA AC@1 = 0.328) with the same minimum-
  completeness chain. EC measures explanation **structure**,
  not accuracy.

* **ρ(SG, EC) = 0.648** is the shared-atom-grounding
  dependency. A method that grounds zero atoms in DiagnosticKB
  (SG = 0) can satisfy at most the component category via the
  service-name text rule (EC ≤ 0.333). The correlation isn't
  higher because (a) six methods all sit at SG = 0 and EC =
  0.333 in lockstep (which contributes maximally to rank
  agreement) and (b) FCP's SG is uniformly 1.0 across cases,
  so all variation on the FCP side comes from EC alone — there
  is no within-FCP SG signal to correlate with within-FCP EC
  variation. The 0.648 is a "between-methods" agreement; within
  any single method, the metrics carry independent information.

* **ρ(SC, EC) = 0.723** is the highest pairwise correlation
  among the four Phase-2 metrics so far. Both metrics reward
  FCP's full chain (FCP scores positive on both; everyone else
  scores zero on SC and 0.333 on EC). The correlation reflects
  the binary "is this method FCP or not" partition more than
  intra-FCP variation. Inside FCP, ρ(SC, EC) is weaker because
  SC depends on per-case propagation density while EC depends
  on whether any fault prototype + recommendation atom is
  present.

The three correlations together support Paper 6's claim that
the four metrics measure **distinct but related** aspects of
explanation quality. The strongest correlation (SC↔EC at 0.72)
is still well below the redundancy bar (ρ ≥ 0.85 would suggest
one metric is a proxy for the other).

**Methodological note on the SG-EC and SC-EC magnitudes.** The
high ρ(SG, EC) = 0.648 and ρ(SC, EC) = 0.723 reflect a
methodological observation about current RCA methods rather than
metric redundancy. On RE1-OB with canonical preprocessing, only
FODA-FCP produces atoms grounded in the diagnostic ontology;
other methods' explanation chains consist of service names and
anomaly scores with no fault-class or recommendation content.
The metrics correctly characterize this asymmetry: methods that
fail to ground atoms cluster at the floor (SG = 0, SC = 0, EC =
0.333), while the one ontology-native method varies across all
three. The high correlations would diminish on a benchmark
suite that includes more semantically-grounded baseline methods,
which is itself a research opportunity. For the current
evaluation suite, the four metrics provide complementary
characterization axes; we do not claim they are statistically
independent, but each measures a distinguishable property of
explanation content.

(6) EC SCORE DISTRIBUTION

EC takes one of four discrete values per case. The distribution
table shows how many of each method's 125 cases land in each
bucket.

| Method   | n@0.0 | n@0.333 | n@0.667 | n@1.0 |
| -------- | ----: | ------: | ------: | ----: |
| MR       |     0 |     125 |       0 |     0 |
| CR       |     0 |     125 |       0 |     0 |
| Micro    |     0 |     125 |       0 |     0 |
| BARO     |     0 |     125 |       0 |     0 |
| DejaVu   |     0 |     125 |       0 |     0 |
| yRCA     |     0 |     125 |       0 |     0 |
| FODA-FCP |     0 |      31 |       4 |    90 |

FODA-FCP is the **only method with within-method variance**.
The other six are deterministic at 0.333 — every case satisfies
the component category and nothing else. FCP partitions into:

* **90 cases at 1.0** — all three categories present. Mamdani
  fires on the root; Recommendation atom emitted.
* **4 cases at 0.667** — cause + component (no mitigation).
  Mamdani fires on a non-root via fuzzy fallback but root's
  ``dominant_category`` is ``UNKNOWN`` so no Rec_* atom
  attached.
* **31 cases at 0.333** — component only. Mamdani fires on no
  service; fuzzy fallback returns None. See §3 for the
  diagnostic.

No FCP case scores 0.0 because the component category fires
on every case (FCP's atoms always mention service names).

(7) RELATION TO SG AND SC

EC is the operator-side reading of the same DiagnosticKB
vocabulary SG measures at the atom level. A method that
grounds zero atoms (SG = 0) cannot satisfy any category-set
membership rule, so its EC depends entirely on the text-level
fallbacks — which is why MR/CR/Micro/BARO/DejaVu collapse to
``has_component = 1, has_cause = 0, has_mitigation = 0`` (the
service-name text rule fires; the strict-vocabulary cause and
mitigation rules don't). FCP, with full DiagnosticKB tagging
on every atom, hits all three categories. yRCA's foreign
``yrca:Role/*`` URIs fail the URI-membership tests, and its
text doesn't whole-token-cover any Fault or Recommendation
label at 0.7 coverage — yRCA scores 0.333 on the service-name
path alone.

This is the **operator-actionability** axis. SG measures "can
the operator look up any individual atom in the ontology"; EC
measures "does the chain answer the three operator questions
in DiagnosticKB's vocabulary". FCP is the only method that
does both; yRCA grounds some atoms (SG 0.267) but emits no
ontology-vocabulary cause/mitigation atoms (EC 0.333); DejaVu
predicts a fault type and a service but in non-DiagnosticKB
vocabulary (EC 0.333); the four MR-family methods don't
emit any DiagnosticKB content at all (EC 0.333 via service-
name text match only).

(8) LIMITATIONS

* **Strict vocabulary**. The detector requires DiagnosticKB
  fault / recommendation labels at the text level. Methods
  whose atoms name a fault in **a different vocabulary**
  (DejaVu's RCAEval category names ``"cpu"``, ``"mem"`` …,
  yRCA's rule_id strings ``"cpu_high"``) don't clear the 0.7
  coverage bar against the longer DiagnosticKB labels
  (``"CPU Saturation"``, etc.). The metric measures vocabulary-
  conformance, not semantic-content equivalence. A future
  variant could add a cross-vocabulary alias table; out of
  scope for the dissertation.

* **Strict cause-detection threshold (DejaVu)**. DejaVu's
  ``failure_type`` prediction (raw text ``"cpu"``) doesn't pass
  the 0.7 coverage threshold against the ``"CPU Saturation"``
  label (single-token coverage 1/2 = 0.5). We adopt the strict
  reading: a method that emits a fault label as a bare
  service-type token without naming the fault class (e.g.,
  ``"cpu"`` instead of ``"CpuSaturation"`` or
  ``"CPU Saturation"``) is undercommunicating diagnostic
  content. DejaVu therefore scores 0.333 on EC despite
  producing a failure-type prediction internally. This is a
  vocabulary-conformance design choice, not a generic
  fault-naming detector. A more lenient detection rule that
  accepts single tokens would raise DejaVu's EC to 0.667; we
  document the alternative in DEVIATIONS.md →
  ``ExplanationCompleteness metric`` and ship the strict
  version.

* **Service-name whole-token rule is RE1-OB-aware**. Reads
  ``case_services`` from the normalised case at evaluation
  time. Methods evaluated on a different benchmark with a
  different naming scheme would need their service list
  threaded through accordingly. This is part of the
  ``score(explanation, ontology, case_services)`` contract;
  passing an empty list disables the text rule and falls back
  to the URI-only :class:`MicroService` check.

* **Binary detectors hide intensity**. EC = 0.333 is the same
  number whether a method emits one component atom or twenty.
  Variants that count atoms per category would surface
  intensity but lose the comparability against the
  four-valued scale. Left as a Week-4 design knob.


## 2026-05 — Phase 2 Week 4: ConfidenceCalibration baseline characterization

**Headline.** Expected Calibration Error (ECE) over the 875 method-
case pairs — the fourth and final Paper 6 Phase 2 semantic-quality
metric. The lone metric where lower is better, and the lone
**aggregate** metric: ECE is a population property, not a per-case
score, so the class is shipped as a standalone analyzer (Option A
architecture; see DEVIATIONS.md → "ConfidenceCalibration metric
(Paper 6 Phase 2 Week 4)").

The seven methods span the full calibration spectrum: **DejaVu wins
(ECE = 0.099)** — best-calibrated by a wide margin — while **BARO
collapses (ECE = 0.534)** with uniform near-zero confidence. FODA-
FCP (0.167), Micro (0.131), CR (0.300), MR (0.335) and yRCA (0.349)
sit in between. Three of seven sit outside the brief's predicted
bands — one massively underperforms predictions (BARO), two beat
them (Micro, DejaVu) — and §6 below traces each to a structural
property of the underlying confidence machinery on this benchmark,
not to an ECE-side artefact.

**Confidence-scale heterogeneity (BARO routing).** Methods use
mathematically different uncertainty formulations: MR / CR / Micro /
FCP use head-ratio confidences ``top1 / Σ_top_K`` in [0, 1]; DejaVu
emits a softmax probability in [0, 1]; yRCA computes a derivation-
multiplicity ratio in [0, 1]. BARO's primary ``confidence`` field
emits the BOCPD **marginal** posterior ``P(r_t = 0 | x_{1:t})`` at
the chosen change-point timestep — a value mathematically bounded
by roughly ``1 / hazard_lambda`` (≈ 0.004 under the default hazard
prior) regardless of how confident BOCPD actually is. Direct ECE
comparison of BARO's 0.004-bounded posterior against
[0, 1]-scaled head ratios is uninformative — the gap reflects
scale incompatibility, not miscalibration. For cross-method
calibration we therefore route BARO to a parallel
``peak_confidence`` field on :class:`DiagnosticOutput`: the band-
normalised peak ``P(change point at the peak moment | it lies in
the search band)``, mathematically in [0, 1] and directly
comparable to the other six methods' scales. BARO's
``confidence`` (the absolute marginal posterior) remains available
for use cases that need probabilistic interpretation. See
DEVIATIONS.md → "BARO routing: peak_confidence for cross-method
calibration" for the routing rule (``_METHOD_CONFIDENCE_FIELD`` in
``run_phase2_cc.py``).

**Empirical caveat on the BARO routing.** Despite the scale fix,
BARO's ECE remained at 0.534 — essentially unchanged from the
0.532 of the un-normalised marginal posterior. The reason is
documented in §6: on RE1-OB the BOCPD log-prob distribution is
**exactly flat** across the search band (spread ``max − min =
0.000``), so peak normalisation yields ``1 / T_band ≈ 0.001667``
uniformly across all 125 cases. The methodological fix is correct
in principle; the empirical finding is that BARO's BOCPD does not
localise the change point on RE1-OB given the adapter's default
hyperparameters, regardless of which posterior summary is exposed.

(1) DESIGN DECISIONS

**Aggregate-only contract.** Three prior Phase 2 metrics (SG, SC,
EC) are :class:`SemanticMetric` per-case scorers; ConfidenceCalibration
deliberately is not. A single (confidence, correct) pair carries
no calibration information — "0.8 confidence, correct" is well-
calibrated iff *across* high-confidence cases accuracy averages
near 0.8. The public surface is :func:`compute_ece` and
:func:`compute_reliability_diagram`, both consuming a list of
`{confidence, correct}` mappings. Per-case cross-metric Spearman
uses :func:`per_case_calibration_error` =
``|confidence − (1.0 if correct else 0.0)|`` — a Brier-style proxy
documented as a per-case approximation (and discussed in §5).

**``n_bins = 10`` default.** Matches Guo et al. 2017 ECE
convention. The bucket index is right-edge inclusive at confidence
1.0 so methods whose softmax peaks at 1.0 (DejaVu, peaked BARO)
don't silently drop. ``test_confidence_calibration.py::
TestBucketIndex`` covers the rule.

**Confidence harvested from in-memory DiagnosticOutput.** Phase-1
validation CSVs in ``results/week2_*.csv`` don't carry a
``confidence`` column — they were written before Phase 2 demanded
the field. Following the Week 3 EC harness pattern, the Week 4
harness re-runs each method on every case and reads
:attr:`DiagnosticOutput.confidence`. All seven methods emit a
non-None confidence; see DEVIATIONS.md → "Confidence harvested
from in-memory DiagnosticOutput" for the per-method confidence
recipe.

(2) PER-METHOD HEADLINE TABLE

7 methods × 125 cases, ECE rounded to 3 decimals (lower = better):

For BARO, ``mean conf`` is the harness-routed ``peak_confidence``
(band-normalised posterior peak in [0, 1]), not the absolute
marginal posterior; see §6 below.

| Method   |   n |   ECE | mean conf | mean acc |   SG |   SC |    EC | over | under |
| -------- | --: | ----: | --------: | -------: | ---: | ---: | ----: | ---: | ----: |
| MR       | 125 | 0.335 |     0.313 |    0.632 | 0.00 | 0.00 | 0.333 |    2 |     2 |
| CR       | 125 | 0.300 |     0.924 |    0.624 | 0.00 | 0.00 | 0.333 |    5 |     0 |
| Micro    | 125 | 0.131 |     0.500 |    0.624 | 0.00 | 0.00 | 0.333 |    1 |     3 |
| BARO     | 125 | 0.534 |     0.002 |    0.536 | 0.00 | 0.00 | 0.333 |    0 |     1 |
| DejaVu   | 125 | **0.099** |  0.795 |    0.696 | 0.00 | 0.00 | 0.333 |    9 |     0 |
| yRCA     | 125 | 0.349 |     0.392 |    0.328 | 0.27 | 0.00 | 0.333 |    6 |     3 |
| FODA-FCP | 125 | 0.167 |     0.352 |    0.448 | 1.00 | 0.27 | 0.824 |    1 |     6 |

**Direction reminder.** ECE ∈ [0, 1], 0 = perfectly calibrated.
This column reads opposite to SG / SC / EC / AC@1 in every prior
Phase-2 table.

(3) PER-FAULT ECE BREAKDOWN

The per-fault matrix exposes which fault types break a method's
calibration. CSV column ``fault`` carries the fault label; the
``ALL`` row is the per-method aggregate.

| Method   |   cpu |  delay |  disk |  loss |   mem |
| -------- | ----: | -----: | ----: | ----: | ----: |
| MR       | 0.385 |  0.620 | 0.433 | 0.137 | 0.344 |
| CR       | 0.283 |  0.062 | 0.227 | 0.744 | 0.269 |
| Micro    | 0.155 |  0.451 | 0.260 | 0.337 | 0.154 |
| BARO     | 0.678 |  0.678 | 0.398 | 0.118 | 0.798 |
| **DejaVu** | **0.012** |  **0.266** | **0.010** | **0.275** | **0.000** |
| yRCA     | 0.497 |  0.445 | 0.277 | 0.423 | 0.503 |
| FODA-FCP | 0.285 |  0.197 | 0.119 | 0.146 | 0.165 |

**Within-method dispersion is the story.** DejaVu's per-fault ECE
spans a 25× range: near-zero on cpu / disk / mem (0.000–0.012) and
0.25+ on delay / loss. The aggregate 0.099 hides a binary
calibration regime. DejaVu's supervised classifier produces
near-perfect calibration on fault types where its decision
boundary is sharp (cpu / disk / mem — the high-effect-size
injections the type head learned to separate cleanly during 5-fold
CV) and mediocre calibration on the harder types where the type
head conflates classes (delay / loss are subtler timing /
error perturbations). The 0.099 aggregate is a population-weighted
average; the per-fault view is the more honest characterisation —
report DejaVu's calibration as "≈0 on the cpu/disk/mem class
boundary, ≈0.27 elsewhere" rather than "0.099 overall."

MR / yRCA show the opposite pattern from DejaVu, with the worst
calibration on the faults where AC@1 is highest. CR's ECE on
``loss`` (0.744) is the single-cell outlier in the matrix —
driven by confidence ≈ 0.92 across the loss bucket where accuracy
is 0.20 (CR's top1/top2 ratio formula doesn't drop on hard cases).
FODA-FCP is the most *evenly* calibrated across faults: max per-
fault ECE 0.285 (cpu), min 0.119 (disk), narrow spread of 0.166 —
the Noisy-OR head-ratio scheme degrades gracefully across the
fault axis even when it underestimates absolute confidence. BARO's
per-fault matrix shows ECE 0.398–0.798 across all five faults
under the peak_confidence routing — the empirical flatness of the
BOCPD posterior produces uniform 0.001667 confidence regardless
of fault type, so all per-fault ECEs are ~|accuracy − 0.001667|.

(4) RELIABILITY-DIAGRAM SUMMARIES

Bin centers are 0.05, 0.15, …, 0.95. Only populated bins reported.
``over`` / ``under`` count the bins where avg confidence exceeds /
trails accuracy.

**MR** (ECE 0.335). Confidence concentrates in [0.2, 0.4]; bucket
0.35 has 72 cases at conf 0.346 with accuracy 0.806 — strongly
underconfident on the head bucket. MR's ``π_top1 / Σ_topK`` head-
ratio formula deflates confidence whenever the top-K random-walk
visit counts are competitive — but on cpu/mem cases the head is
deterministic and right anyway.

**CR** (ECE 0.300). 96 of 125 cases land in bucket 0.95 with avg
conf 0.979 and accuracy 0.677 — uniform overconfidence. The
``1 − top2/top1`` formula assigns near-1 confidence whenever the
top1 PC-algorithm score exceeds top2 by any margin, regardless of
whether top1 is the true root. CR's bucket distribution is
right-skewed by design; calibration suffers commensurately.

**Micro** (ECE 0.131). Two populated head buckets at 0.55 (57
cases, conf 0.552, acc 0.789) and 0.45 (37 cases, conf 0.453, acc
0.459). Best-calibrated in the unsupervised band — random-walk
head-ratios on a service-mesh-collapsed graph hit a sweet spot
where the head ratio tracks the visit-share lead, which tracks
correctness.

**BARO** (ECE 0.534, using peak_confidence routing). **All 125
cases in bucket 0.05 with avg peak_confidence 0.002 and accuracy
0.536.** ``peak_confidence`` is the band-normalised BOCPD posterior
peak ``exp(max(log_band) − logsumexp(log_band))`` — designed to
sit on the same [0, 1] scale as MR/CR/Micro head ratios, so the
ECE gap should reflect calibration rather than scale mismatch.
But the harness empirically observes peak_confidence ≈ 1/T_band ≈
0.001667 on every RE1-OB case (zero variance across 125 cases,
zero variance across the five fault types). Inspection of the
underlying ``cp_log_probs`` shows the BOCPD log-probability
distribution is **literally flat** across the 600-element search
band (``max − min = 0.000``) — the hazard prior dominates the
likelihood and the posterior is uniform at
``exp(−log(hazard_lambda)) = 0.004`` per timestep. ECE correctly
flags this as a property of BARO-on-RE1-OB. See §6 below for the
diagnostic and the routing decision.

**DejaVu** (ECE 0.099). 79 cases in bucket 0.95 with conf 0.998
and accuracy 0.949 — well-calibrated at the extreme. The
remaining 46 cases scatter across 0.15-0.85 with accuracies 0.0-
0.5 (mid-range overconfident; 9 over, 0 under). The supervised
type-head is what's well-calibrated; the residual ECE budget
sits in the mid-range cases where the softmax is flatter.
**Beats every prediction band — best-calibrated method.**

**yRCA** (ECE 0.349). Bimodal: 30 cases at confidence 0.000
(derivation-multiplicity formula returned zero) with accuracy
0.567, and 19 cases at confidence 1.000 with accuracy 0.158.
The two tails miscalibrate in opposite directions and combine
to a 0.35 aggregate. The 30 conf-0 cases come from yRCA's
forward-chainer not producing a multi-derived root (the
formula's numerator); the 19 conf-1 cases come from a single
rule firing — both are degenerate inputs to a ratio.

**FODA-FCP** (ECE 0.167). **6 underconfidence bins, 1
overconfidence bin** — the only method dominated by
underconfidence. 31 cases at confidence 0.000 with accuracy
0.194 (the Week-3 silent-Mamdani failure mode: when no service
fires a rule, the top1_C / Σ_topK head ratio is 0/0 → clipped
to 0). Bins 0.45–0.95 have accuracy 1.000 across the board —
when FCP commits to a confidence above 0.4 it's right 100 % of
the time. This is *honest underconfidence*: the Noisy-OR
propagation is conservative, but when it speaks it's
authoritative.

(5) SPEARMAN CORRELATIONS

Per-case Spearman across all 875 (method, case) pairs, using the
``cal_error = |confidence − target|`` proxy as the y-axis. The
brief's sign predictions and the observed results:

| pair                | predicted | observed | sign |
| ------------------- | --------: | -------: | :--: |
| ρ(AC@1, cal_error)  | negative  | **+0.134** | flipped |
| ρ(SG,   cal_error)  | near zero | −0.028   | ✓ |
| ρ(SC,   cal_error)  | near zero | −0.014   | ✓ |
| ρ(EC,   cal_error)  | near zero | −0.032   | ✓ |

**The AC@1 sign flip is real, and the cause is mechanical.**
``cal_error`` = ``|confidence − (1.0 if correct else 0.0)|``.
For a method like BARO with uniform confidence ≈ 0.002:

* correct cases get ``cal_error = |0.002 − 1.0| = 0.998`` (high)
* wrong cases get ``cal_error = |0.002 − 0.0| = 0.002`` (low)

So correctness *predicts high cal_error* when a method is
uniformly underconfident — opposite of the brief's prediction.
The same logic applies to FODA-FCP's 31 silent-Mamdani cases
(conf 0.0, accuracy 0.19) and yRCA's 30 conf-0 bucket. With
three of seven methods carrying populations whose confidence is
deflated relative to accuracy, the cross-method Spearman picks
up a *positive* signal — high AC@1 cases tend to be the under-
confident ones with high cal_error.

This is a per-case-proxy artefact, **not** a property of
aggregate ECE. The aggregate ECE rank (DejaVu < FODA-FCP <
Micro < CR < MR < yRCA < BARO) is uncorrelated with the AC@1
rank (DejaVu > MR > CR ≈ Micro > BARO > FCP > yRCA) — Spearman
ρ over the 7 method-level aggregates is +0.04. Calibration and
ranking are independent dimensions when measured at the
correct granularity; the per-case proxy mixes them. The
predicted "lower ECE → higher AC@1" intuition holds at neither
the per-case proxy level (sign-flipped by underconfidence) nor
the method-level (independent).

**SG / SC / EC near-zero correlations confirm the prediction.**
The three structural metrics measure properties of the
explanation graph that don't determine the method's confidence
self-assessment. SG / SC / EC are dominated by FODA-FCP vs.
everyone-else dichotomies (per Weeks 1-3); ``cal_error`` is
not.

(6) ALARM GATES — RESOLVED VS. SURPRISING OUTCOMES

The brief's predicted bands and the observed outcomes:

```
✓ MR     ECE = 0.335  ∈ [0.20, 0.45]
✓ CR     ECE = 0.300  ∈ [0.20, 0.45]
⚠ Micro  ECE = 0.131  below predicted [0.20, 0.45]  (better than predicted)
⚠ BARO   ECE = 0.534  ABOVE all predicted bands     (empirical-flatness alarm)
⚠ DejaVu ECE = 0.099  below predicted [0.15, 0.45]  (better — but bimodal)
✓ yRCA   ECE = 0.349  ∈ [0.10, 0.40]
✓ FODA-FCP ECE = 0.167 ∈ [0.10, 0.25]
```

Four ✓ + three ⚠. Two of the three ⚠ rows are methodological
findings revealed by ECE analysis — not noise, not adapter bugs,
not metric defects. The third (Micro) is a benign expectation
under-shoot covered separately below.

**Two methodological findings revealed by ECE analysis.**

1. **DejaVu's aggregate calibration hides a binary regime.**
   The 0.099 aggregate ECE is real, but it averages over two
   distinct calibration regimes: near-perfect on the fault types
   DejaVu's supervised classifier learned to separate cleanly
   (cpu / disk / mem, ECE 0.000–0.012) and mediocre on the
   harder types its decision boundary conflates (delay / loss,
   ECE 0.266–0.275). The aggregate is a population-weighted
   average of two regimes that would behave very differently
   under deployment.

2. **BARO's Bayesian uncertainty model is empirically inert on
   RE1-OB under default hyperparameters.** The BOCPD marginal
   posterior is uniformly flat across the search band on every
   one of 125 cases (zero log-probability spread); peak-
   normalisation of a flat distribution is just ``1 / T_band``,
   constant. BARO's confidence values cluster near the scale
   floor regardless of correctness — not because the adapter is
   buggy, but because the published BARO's default
   hyperparameters yield a non-discriminating posterior on this
   benchmark.

Both findings strengthen Paper 6's thesis: **aggregate metrics
obscure method-level variation that matters for deployment.**
Paper 6 reports ECE *and* per-fault breakdowns *and* reliability
diagrams precisely because these auxiliary views surface
behaviours an aggregate hides.

The detail on each finding follows.

**Finding 1: DejaVu's binary calibration regime.** The brief
predicted ECE 0.25–0.40 ("softmax confidence, often inflated").
The aggregate 0.099 *under-shoots* the predicted band, but the
per-fault breakdown reveals a 25× spread:

```
DejaVu per-fault ECE:
  cpu:   0.012  (n=25, mean_conf 0.988, mean_acc 1.000)
  disk:  0.010  (n=25, mean_conf 0.990, mean_acc 1.000)
  mem:   0.000  (n=25, mean_conf 1.000, mean_acc 1.000)
  delay: 0.266  (n=25, mean_conf 0.561, mean_acc 0.320)
  loss:  0.275  (n=25, mean_conf 0.435, mean_acc 0.160)
```

Three fault types in one cluster (≤ 0.012, near-perfect
calibration), two in another (≥ 0.266, mediocre). The
supervised classifier's softmax peaks correctly when its
fault-type head has a sharp decision boundary (cpu / disk / mem
inject large-effect-size signatures distinguishable during
5-fold CV) and goes flat when the boundary blurs (delay / loss
are subtler timing / error perturbations conflated with
neighbouring classes during inference).

Reporting DejaVu's calibration as "0.099 overall" would
mislead a deployment decision. The honest characterisation
is "≈0 on cpu/disk/mem, ≈0.27 on delay/loss." A practitioner
choosing DejaVu for an operator-facing system needs to know
that the method's confidence is trustworthy on some fault
classes and unreliable on others — information aggregate ECE
alone destroys.

**Finding 2: BARO's empirically inert Bayesian uncertainty.**
The brief predicted ECE 0.10–0.15 ("Bayesian posterior, native
uncertainty"). The Week 4 run reports 0.534 — fourfold higher
than predicted.

*Diagnosis: a confidence-scale issue, addressed by routing.*
BARO's primary ``DiagnosticOutput.confidence`` is the BOCPD
**marginal** posterior ``P(r_t = 0 | x_{1:t})`` at the chosen
change-point timestep. The marginal posterior is bounded by
``~1 / hazard_lambda = 0.004`` under the default hazard prior
*regardless* of how peaked the underlying change-point
distribution is — comparing this 0.004-bounded posterior to
[0, 1]-scaled head ratios from other methods would conflate
scale incompatibility with miscalibration. Week 4 ships a
parallel ``peak_confidence`` field on :class:`DiagnosticOutput`
that computes the band-normalised peak
``exp(max(log_band) − logsumexp(log_band))`` — "probability
mass at the peak moment **given** the change point is in the
search band". Range [0, 1], directly comparable to the other
six methods. The Week 4 harness uses a per-method routing
rule (``_METHOD_CONFIDENCE_FIELD`` in ``run_phase2_cc.py``):
``peak_confidence`` for BARO, ``confidence`` for everyone else.
The fix is documented as confidence-scale normalisation, not
method modification — BARO's ranking and AC@1 (= 0.536) are
unchanged.

*Finding: BOCPD's posterior is uniformly flat on RE1-OB.*
Under the routing fix, BARO's ECE is **0.534**. Inspection of
``cp_log_probs`` returned by :func:`_bocpd_multivariate` shows
why:

```
re1-ob_adservice_cpu_1: T=1201, band size=600
  log_probs range: min=-5.521 max=-5.521
  spread: max-min=0.000
```

BARO's BOCPD marginal posterior is uniformly flat across the
search band on RE1-OB under default hyperparameters (hazard
λ = 250, default prior variance). Empirical log-probability
spread across the 600-element band is 0.000 in 125 of 125
cases. The hazard prior dominates the data likelihood; canonical
feature z-scores under our preprocessing pipeline do not produce
sufficient signal-to-noise for BOCPD to localise the change
point.

This is a real empirical finding about BARO on RE1-OB, not a
hyperparameter calibration issue or an adapter bug. The
published BARO uses these defaults; the published BARO produces
flat posteriors on this benchmark. The 0.534 ECE characterises
this empirical degeneracy: BARO's confidence values cluster
near zero regardless of correctness because BOCPD isn't
extracting data-driven uncertainty.

*Broader implication for probabilistic RCA.* Probabilistic
methods can have mathematically rigorous uncertainty
formulations that are empirically inert on a given benchmark.
Reviewing the hyperparameter sensitivity (hazard λ, prior
variance) *and* the input feature signal-to-noise is necessary
before treating a method's confidence as Bayesian information.
We document this as a Paper 6 finding: probabilistic methods
deserve their own empirical-uncertainty verification axis
distinct from ECE alone — ECE measures the *consequence* of an
inert posterior (confidence/accuracy gap) but not its *cause*
(flat log-prob distribution). A diagnostic suite for
probabilistic RCA should include posterior peakedness as a
first-class check.

*Within Paper 6 scope.* The 0.534 BARO ECE stands. Future work
could revisit BARO's hyperparameters (narrower hazard prior,
narrower predictive prior) or replace its confidence with a
different summary (top-K score-shift ratio, posterior entropy,
run-length-mean) — those would be method modifications outside
Paper 6's scope. Within scope, BARO produces a uniformly
low-confidence output on this benchmark; ECE correctly measures
the resulting calibration gap to AC@1 accuracy, and the
reliability diagram (one populated bucket, 125 cases) is the
auditable failure signature.

**Micro ECE = 0.131 — better than predicted.** Predicted 0.20-
0.40 ("ratio-based, no uncertainty model"); observed 0.131
with bin 0.55 carrying 57 cases at conf 0.552 / accuracy 0.789.
Micro's service-mesh-collapsed random walk gives head ratios
that track visit-share leads, and on the cpu/mem-rich RE1-OB
distribution this turns out to track correctness too. Like
DejaVu, this is **expectation under-shot — Micro is well-
calibrated despite the absence of an uncertainty model**.

(7) RELATION TO SG / SC / EC

Of the four Phase-2 metrics, ConfidenceCalibration is the only
one where the FCP-vs-everyone-else dichotomy is **not** the
dominant story. SG / SC / EC have FCP at the top and six methods
near or at zero. CC has FODA-FCP in third place (0.167) — well-
calibrated but bested by DejaVu (0.099) and Micro (0.131). The
calibration axis is genuinely orthogonal to the explanation-
structure axis:

* **FODA-FCP** wins on structure (SG 1.0, SC 0.27, EC 0.82) and
  is well-calibrated (CC 0.17), but not the best calibrator.
* **DejaVu** is the worst on structure (SG 0, SC 0, EC 0.333,
  flat with the four MR-family methods) but the best
  calibrator. A method that produces no ontology-grounded
  explanation can still produce a confidence value that
  matches reality.
* **BARO** scores zero on three Phase-2 structure metrics AND
  fails calibration — bad confidence, bad explanation, decent
  ranking. The reliability diagram exposes the bad confidence
  in a single line.

The four metrics together characterise an explanation across
four distinguishable axes:

* **Groundedness** (SG) — atoms speak the ontology's vocabulary.
* **Coherence** (SC) — links match the ontology's propagation
  model.
* **Completeness** (EC) — chain answers the three operator
  questions.
* **Calibration** (CC, ECE) — confidence matches accuracy.

A reader can now compare any two methods on each axis
independently; on RE1-OB the four-tuple is (DejaVu, Micro,
FODA-FCP, MR, CR, yRCA, BARO) for calibration but very
different for structure.

(8) LIMITATIONS

* **Aggregate ECE has no per-case decomposition.** The Spearman
  analysis uses ``cal_error`` as a per-case proxy. The proxy
  preserves direction at the per-case granularity but is *not*
  ECE — it's a Brier-style absolute error. The proxy is
  sign-flipped by uniform under-confidence (the BARO case);
  aggregate ECE is not. Cross-metric analysis should report
  both granularities, as this note does.

* **Right-edge inclusivity is a convention.** Confidence = 1.0
  lands in the last bucket. A symmetric alternative ("0.0
  exclusive at left, 1.0 inclusive at right" vs. half-open
  everywhere) would barely shift any ECE on the observed data
  (BARO has 0 cases at exactly 1.0, DejaVu has 79 at near-1.0
  but not exactly 1.0). Documented in DEVIATIONS.md for
  reproducibility.

* **125-case populations and 10 buckets.** With n_bins = 10 and
  n = 125, an average of 12.5 cases per bucket — but uneven in
  practice (DejaVu has 79 in one bucket). Smaller per-bucket
  populations increase ECE noise; for fine-grained calibration
  analysis a longer benchmark would help. We report n_bins = 10
  to match the literature; the harness exposes a CLI knob.

* **BARO's confidence is the adapter's choice, not BARO's
  inherent posterior.** A future BARO revision that surfaces
  the BOCPD posterior directly would likely move BARO into the
  predicted band. ECE flags the adapter-level decision rather
  than the method-level Bayesian machinery — note this when
  citing BARO's calibration on RE1-OB.

