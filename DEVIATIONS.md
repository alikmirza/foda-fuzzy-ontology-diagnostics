# DEVIATIONS

This document records every place our implementation of a published
RCA method differs from the original paper, and *why*. Each entry
should be short and concrete enough that a reviewer can decide whether
the deviation invalidates a numerical comparison.

---

## Schema normalization layer

Implementation: `evaluation/extraction/schema_normalizer.py`.
Design doc: `evaluation/extraction/DESIGN_inject_time_removal.md`.

### Deviation N1: `inject_time` is hidden from method-facing surface

Every method in the literature we are porting (MonitorRank, MicroRCA,
CausalRCA, BARO, DejaVu, FODA-FCP) assumes the injection timestamp is
known and uses it as the fencepost between "pre" and "post" windows.
A diagnostic shift on our earlier MonitorRank implementation
confirmed this dependency: shifting `inject_time` by +300 s collapsed
RE1-OB AC@1 from 0.664 to 0.104. A fencepost on a side-channel value
is not deployable in production — no oracle hands the algorithm the
moment the fault began.

**What we changed.** `NormalizedCase` exposes `case_window`,
`window_start/end`, `sampling_dt`, `services`, `schema_summary`. It
does **not** expose `inject_time`; accessing `norm.inject_time` raises
`AttributeError` with a pointer to the side channel. The timestamp
lives on `CaseGroundTruth` (`norm.ground_truth.inject_time`),
accessible only to the evaluation harness.

**Why methods can still work without it.** Each method either does
its own change-point detection on `case_window`
(`evaluation/methods/_onset.detect_onset` is the opt-in reference
implementation) or reformulates around window-aggregate statistics.
MonitorRank uses the former.

**How we know it works.** Two layers:

1. *Static.* The evaluation harness calls
   `evaluation/methods/_protocol.validate_no_ground_truth_peeking`
   before scoring any method. The validator AST-walks
   `type(method).diagnose` (and `.diagnose_normalized` where present)
   and refuses to score any method that references `ground_truth` or
   `CaseGroundTruth`. Test coverage in
   `evaluation/tests/test_protocol.py`.
2. *Empirical.* The harness re-runs each method with the side-channel
   `inject_time` shifted by ±300 s (case_window unchanged) and reports
   `S(M) = mean |AC@1_true − mean(AC@1_shifted)|`. A clean method
   scores `S(M) ≈ 0`; a leaky one approaches its own AC@1. MonitorRank
   currently scores `S = 0.000` overall and per-fault on RE1-OB.

### Deviation N2: window is randomly positioned around `inject_time`

To prevent methods from using the window centre as a proxy for
`inject_time`, the injection point sits at a per-case offset
`u ∈ [25 %, 75 %]` of the window length. The offset is derived from
`sha256(f"{case_id}|{window_seconds}")`, which makes it:

* deterministic across runs (reproducibility),
* stable under dataset growth (adding a new case doesn't move existing
  offsets), and
* re-randomized if the window length changes (preventing methods from
  memoizing the offset for a given case id).

### Deviation N3: regular resampling with linear interpolation

`normalize_case` produces a `case_window` on a regular grid at the
median raw sampling interval. In-range points are linearly
interpolated by index; points past the raw edges are filled by
`ffill`/`bfill`. The normalizer raises `ValueError` when more than
20 % of consecutive raw intervals deviate by more than 50 % from the
median — a hard guard against silently inventing data across long
sampling gaps.

### Deviation N4: spurious `time.1` column dropped

Some RCAEval RE1 cases (the long-window CPU/MEM pipeline) include a
duplicate `time.1` column from an upstream join artifact. The
normalizer drops it before canonicalization so downstream methods see
exactly one time column.

---

## MonitorRank (Kim, Sumbaly, Shah; KDD 2013)

## MonitorRank (Kim, Sumbaly, Shah; KDD 2013)

Implementation: `evaluation/methods/monitorrank.py`. Consumes
`NormalizedCase` from `evaluation/extraction/schema_normalizer.py`
rather than raw RCAEval CSVs.

### Deviation 0: Onset detected from telemetry, not read from inject_time

**Most important deviation.** The 2013 paper assumes ``inject_time``
is known. The original port read ``norm.inject_time`` and split the
window into pre/post halves at that timestamp. Under the new
inject_time-removal contract (Deviation N1 above), `inject_time` is
hidden from the method. MonitorRank now calls
:func:`evaluation.methods._onset.detect_onset` on
``case.case_window`` to find a candidate split point by maximizing
aggregate cross-service z-score in a [25 %, 75 %] pivot band.

**Why this changes the numbers.** The detector lags the true
injection by up to ~30 s on cases where the fault propagates slowly,
which produces a real (and *honest*) AC@1 drop relative to a
fenceposting implementation. The drop is the cost of being
deployable.

**How we know we did not regress.** Per-case AC@1 is identical
between the true run and the ±300 s shifted runs (shift moves only
the side-channel `inject_time`, not `case_window`). The
shift-evaluation protocol reports `S = 0.000` overall and per-fault
on RE1-OB. See `results/week2_monitorrank_validation.csv`.

### Deviation 1: Anomaly-score personalization replaces pattern similarity

The paper builds the personalization vector from *pattern similarity*
`S_i = max |corr(m_i, m_frontend)|` between each service's metric and
the frontend's. We use **per-service z-scores** instead:

```
z_i = max_f |mean(post_f^i) − mean(pre_f^i)| / std(pre_f^i)
```

where `f` ranges over the canonical features emitted by the
normalization layer (`latency`, `traffic`, `error`, `cpu`, `mem`,
`disk`, `net`), and `pre` / `post` split the normalized window at
`inject_time`. The frontend is given personalization weight 0
(consistent with the paper's exclusion); the remaining weights are
normalized to a probability distribution.

**Why:** RCAEval ships symmetric pre/post windows around `inject_time`
(via `schema_normalizer.normalize_case`), so the z-score split is the
direct signal. Pattern similarity to the frontend is a degraded proxy
in this regime — it confounds "service participates in the frontend's
trace" with "service is the cause". For benchmarks like RE1-SS whose
metrics do not name a frontend at all, pattern-similarity is
ill-defined; z-score remains well-defined regardless.

### Deviation 2: Inferred service-call graph replaces a given call graph

The paper assumes the call graph is supplied as input. RCAEval RE1
does not publish per-case topology, and our normalization layer does
not read service-mesh export. We **infer** the graph from feature
co-occurrence in the case itself:

* For each service, pick a "shape" signal — `_traffic` first
  (request rate tracks call topology most directly), then `_latency`,
  then a resource metric as a last resort.
* Add a bidirectional edge `u ⇄ v` whenever `|corr(shape_u, shape_v)|`
  exceeds `corr_threshold` (default 0.3, in `(0, 1)`).
* If any non-frontend service ends up disconnected from the frontend,
  add a fallback bidirectional edge to the frontend with weight equal
  to the threshold so PPR mass can reach every candidate.

**Why:** The walker needs *some* graph to walk. Inferring from
correlations is the obvious data-only stand-in for a missing call
graph, and it preserves the paper's symmetric `caller ↔ callee`
treatment (the paper adds backward edges with weight `ρ`; we just
treat the inferred graph as undirected for the same reason). The
`frontend → disconnected-service` fallback fills the role of the
paper's assumption that the call graph is fully connected — without
it, PPR cannot place mass on a service the walker can never reach.

### Deviation 3: No backward-edge weight `ρ`

The paper defines a directed call graph with backward edges weighted
by `ρ ∈ [0, 1)` (Eq. 6). Our inferred graph is symmetric, so there is
no asymmetry to weight: both directions get the same correlation
weight. The `corr_threshold` parameter takes over the role `ρ` plays
in the paper (controlling how much the walker can deviate from the
"natural" caller→callee direction). The deprecated `rho` kwarg has
been removed from `MonitorRankMethod.__init__` and from
`evaluation.experiments.evaluate_monitorrank`.

### Deviation 4: Pseudo-anomaly clustering (PAC) is not implemented

Section 5.2 of the paper describes an offline component that clusters
historical anomalies by external factors. We implement only the
real-time PPR core. The paper's own ablation (Figure 6, PS+RW vs.
PS+PAC) shows the random-walk core carries the bulk of the lift —
PAC's contribution is small and benchmark-specific.

### Deviation 5: Frontend auto-detection

The paper takes the frontend as a user input (it's where the anomaly
was reported). When `frontend_service` is `None`, we name-match
against a small list of common frontend identifiers (`frontend`,
`front-end`, `fe`, `web`, `ts-ui-dashboard`, …). If no name matches,
we *do not* fall back to picking an arbitrary "noisiest" service —
that heuristic systematically hides the most anomalous service on
benchmarks (e.g. RCAEval RE1-SS) whose metrics do not name a frontend
at all. Instead, no service is excluded from the ranked list.

### Validation against published baselines

Validated via (a) synthetic 3-service and 5-service scenarios with a
single obvious anomaly (see `evaluation/tests/test_monitorrank.py`),
and (b) per-fault-type AC@k on all 125 RE1-OB cases compared to the
MicroCause / MicroRank baselines from RCAEval (Pham et al., WWW 2025)
Table 5. Results live in `results/week2_monitorrank_validation.csv`.
At the time of writing, MonitorRank's AC@1 is comfortably above both
baselines on cpu / mem / disk / delay faults and roughly in line on
loss faults — the gap on the first four is most likely because direct
z-score anomaly detection captures the *injection signature* itself
(stress-ng on cpu directly inflates `cpu`), whereas MicroCause and
MicroRank look for indirect causal propagation and pay an
under-fitting cost on faults that don't propagate clearly. This is a
known qualitative difference between direct-anomaly and
causal-propagation RCA methods, not an implementation bug.

---

## CausalRCA (Xin, Chen, Zhao; JSS vol 203 art 111724, 2023)

Implementation: `evaluation/methods/causalrca.py`. Consumes
`NormalizedCase` from `evaluation/extraction/schema_normalizer.py`
rather than RCAEval's `preprocess(...)` output.

The published CausalRCA learns a structural equation model over every
metric column via a VAE-based NOTEARS continuous optimization, then
ranks candidates by PageRank on the learned adjacency. Our
re-implementation matches the *spirit* — learn a causal graph from
telemetry, infer the root cause from that graph — but parts ways on
several concrete choices documented below.

### Deviation 0: Onset detected from telemetry, not read from inject_time

Same shape as MonitorRank's Deviation 0. The published version
fenceposts pre/post windows at `inject_time` (it then aggregates
"normal" and "anomalous" rows separately and feeds the concat into
the VAE). Under the inject_time-removal contract (Deviation N1
above) `inject_time` is hidden, so `CausalRCAMethod.diagnose_normalized`
calls `evaluation.methods._onset.detect_onset` on `case_window` to
find the pre/post pivot from telemetry alone. The pivot is used in
the same place the published method uses `inject_time`: to compute
per-service post-vs-pre z-scores that feed both the anomaly ranking
and the choice of "shape signal" each service contributes to the PC
matrix.

Empirical witness: per-case `AC@1` is bit-identical between the true
run and the ±300 s shifted runs (shift moves only the side-channel
`inject_time`, not `case_window`). `S(M) = 0.000` overall and per-fault
on RE1-OB; see `results/week2_causalrca_validation.csv` and
`evaluation/tests/test_causalrca.py::TestShiftInvariance`.

### Deviation 1: PC algorithm over services, not NOTEARS-VAE over columns

The published method runs a VAE-based NOTEARS continuous structure
learner (an MLP encoder/decoder pair, ~500 epochs × up to 100 outer
iterations) over *every* metric column. We instead:

* Pick one **per-service "shape signal"** — the canonical feature
  whose post-vs-pre z-score is largest for that service. This
  collapses the ~60 service-feature columns into ~10–20 service
  signals.
* Run **causal-learn's PC algorithm** (`fisherz` CI test, `alpha=0.05`)
  on the resulting matrix.

**Why** — the brief explicitly authorizes either PC or NOTEARS and
asks us to document the choice. PC has three advantages here:

1. *Deterministic.* No random initialization, no SGD seed sensitivity.
2. *Auditable.* The CI-test structure means every absent edge has a
   testable reason; the VAE's adjacency is a black box.
3. *Right scale.* The ancestor-analysis step that follows wants a
   DAG **over services** (not over service-feature pairs), so the
   per-service signal collapse is in any case required. Once you've
   collapsed, the variable count (~10–20) is small enough that PC's
   asymptotic cost is irrelevant — every case finishes in well under
   one second.

**What we give up** — the VAE's MLP can capture nonlinear couplings;
PC + Fisher-Z assumes linear Gaussian. On RE1-OB this hasn't shown
up as an AC@1 drop (we're at 0.624 overall versus the published
~0.15), but it would be a real limitation on a benchmark with
heavily nonlinear inter-service dynamics.

### Deviation 2: Ancestor-of-anchor scoring, not PageRank on the adjacency

The published method runs PageRank on `|A|` (`sknetwork.ranking.PageRank`)
and reports the rank order directly. We instead:

* Designate the **anchor** = `argmax_service anomaly_score`.
* For every service `s`, compute
  `score(s) = anomaly_score(s) / (1 + d(s, anchor))`
  where `d` is the shortest directed-path length from `s` to the
  anchor in the learned DAG. Non-ancestors get `score(s) =
  anomaly_score(s) × nonancestor_penalty_floor` (default 0.05) so
  they still rank but are demoted below ancestors.

**Why** — the brief specifies "ancestor analysis" and "(anomaly score
× distance penalty)" explicitly. The structural intuition is that the
most-anomalous service is typically the *manifestation*, not the
cause, and the cause lives upstream. PageRank biases toward
high-degree nodes regardless of whether those nodes are upstream of
the manifestation; ancestor-of-anchor scoring explicitly restricts
the candidate set to the upstream cone of the visible symptom.

### Deviation 3: Undirected-edge orientation by anomaly gradient

PC returns a **CPDAG**: some edges are directed, others are left
undirected because the equivalence class is unidentifiable from
observational data alone. We turn the CPDAG into a DAG by orienting
every undirected edge from the less-anomalous endpoint to the
more-anomalous one — i.e., "anomaly flows downstream".

**Why** — ancestor-of-anchor scoring needs a DAG, and the gradient
orientation is the deterministic tiebreaker most consistent with the
"manifestation is downstream" prior. Random or alphabetic
orientation would be defensible but less informative; an explicit
score-based orientation reads naturally in the explanation graph.

### Deviation 4: Explanation chain carries real causal links

CausalRCA is the first method in the suite that produces a true
causal narrative, not just a ranked list. `CanonicalExplanation` for
this method includes:

* One `ExplanationAtom` per service in the top-K head (default K=5),
  text-tagged with the service's dominant feature and z-magnitude.
* `CausalLink` edges drawn from the learned DAG induced on the
  top-K services. Each link's weight is the absolute Pearson
  correlation between the two services' shape signals (clipped to
  `[0, 1]`).
* The atom corresponding to the anchor is tagged `(anchor)` in its
  text.

MonitorRank emits an empty link set; this method does not. The
ontology-grounded metrics added later in Paper 6 will exploit the
structural information.

### Deviation 5: Confidence = 1 − top2/top1 ratio

The published method reports the PageRank score directly. We
synthesize a `[0, 1]` confidence as `1 − top2_score / top1_score`,
clipped. A clear winner gives confidence near 1; a near-tie gives
confidence near 0. This matches the brief's instruction
("Derive from the top-1 service's anomaly score relative to the
second-ranked service. Calibration will be evaluated separately in
Paper 6's metrics phase").

### Deviation 6: Schema normalization upstream of method input

Same as MonitorRank's analogous point. The method consumes a
`NormalizedCase` (`{service}_{latency, traffic, error, cpu, mem,
disk, net}` canonical schema, bounded `case_window`, randomly
positioned inject point, regular sampling). The published method
ran on RCAEval's `preprocess(...)` output (drop-constant, drop-time,
column rename). The normalization step is *upstream* of the method;
it isn't a deviation from the algorithm itself but it is a
preprocessing difference that affects numerical comparability.

### Validation against published baselines

Validated via (a) synthetic 3-service and 5-service scenarios where
the root cause is known a priori (see
`evaluation/tests/test_causalrca.py`), and (b) per-fault-type AC@k on
all 125 RE1-OB cases. Results in
`results/week2_causalrca_validation.csv`.

**Headline numbers** (RE1-OB, inject-time-clean contract):

| fault   | n  | AC@1  | AC@3  | AC@5  | MRR   | S(M)   | AC@1_random |
|---------|----|-------|-------|-------|-------|--------|-------------|
| cpu     | 25 | 0.680 | 0.960 | 1.000 | 0.810 | 0.000  | 0.400       |
| delay   | 25 | 0.960 | 0.960 | 0.960 | 0.963 | 0.000  | 0.400       |
| disk    | 25 | 0.680 | 0.920 | 0.960 | 0.788 | 0.000  | 0.200       |
| loss    | 25 | 0.120 | 0.560 | 0.680 | 0.356 | 0.000  | 0.080       |
| mem     | 25 | 0.680 | 0.880 | 0.880 | 0.786 | 0.000  | 0.640       |
| overall |125 | 0.624 | 0.856 | 0.896 | 0.741 | 0.000  | 0.344       |

The `AC@1_random` column is the random-onset decomposition probe
(brief §10): re-run with the onset replaced by a uniformly-random
in-band pivot. Substantial gap between `AC@1` and `AC@1_random`
(0.624 → 0.344 overall) means change-point detection contributes
meaningfully on top of the structural step. The structural step
alone, even with a random pivot, still beats the published RCAEval
CausalRCA AC@1 of ~0.15.

**Note on overall AC@1 being above the brief's [0.10, 0.50] band.**
At 0.624 we're well above the brief's expected upper bound and also
well above RCAEval's published CausalRCA AC@1 of ~0.15. `S(M) = 0`
rules out an inject_time leak. The most plausible explanation is
the same effect MonitorRank shows: the `NormalizedCase` layer
exposes per-service canonical features cleanly (`{svc}_cpu`,
`{svc}_latency`, …) and the post-vs-pre z-score on those columns is
a much stronger direct signal than what RCAEval's `preprocess(...)`
produced. CausalRCA's anomaly ranking (which feeds both the anchor
choice and the score) inherits that lift; the ancestor-of-anchor
scoring then preserves it. For comparison, MonitorRank under the
same normalization scores `AC@1 = 0.632` overall — essentially
identical, supporting the "shared upstream cause" interpretation
over either method's structural step being the deciding factor.

---

## MicroRCA (Wu, Sun, Wang; NOMS 2020)

Implementation: `evaluation/methods/microrca.py`. Consumes
`NormalizedCase` from `evaluation/extraction/schema_normalizer.py`.

The published MicroRCA builds an attributed service graph from the
deployed service mesh's call topology, weights edges by anomaly
correlation across services in the post-injection window, and ranks
candidates with personalized PageRank using normalized per-service
anomaly scores as the personalization vector. Our re-implementation
matches the spirit — attributed graph, asymmetric weights,
personalized PageRank — but parts ways on three concrete points:

### Deviation 0: Onset detected from telemetry, not read from inject_time

Same shape as MonitorRank/CausalRCA Deviation 0. Under the
inject_time-removal contract (Deviation N1) the timestamp is hidden;
`MicroRCAMethod.diagnose_normalized` calls
`evaluation.methods._onset.detect_onset` to find the pre/post pivot
from `case_window` alone. The detected pivot is used in two places:
to compute per-service post-vs-pre z-scores (which become both the
anomaly scores and the choice of "shape signal" each service
contributes to the graph), and to bound the window over which
edge-weight correlations are computed.

Empirical witness: per-case `AC@1` is bit-identical between the true
run and the ±300 s shifted runs. `S(M) = 0.000` overall and per-fault
on RE1-OB.

### Deviation 1: No deployed service-mesh topology — lagged correlation in its place

The published method *requires* the call graph as input; edges
between non-adjacent services in the topology simply don't exist.
RE1 does not ship per-case call-graph metadata, and our
normalization layer does not consume Envoy/Istio exports. We
substitute **lagged Pearson correlation** between service shape
signals in the post-onset window:

* For every ordered pair `(u, v)`, the edge `u → v` carries weight
  `|corr(u_signal[0 : T − lag], v_signal[lag : T])|` — i.e., "u
  leads v by `lag` samples". `lag = 1` is the default, large enough
  to break symmetry on RCAEval's median sampling rate, small enough
  that real lead-lag dynamics still register.
* The asymmetry is genuine: `u → v` and `v → u` look at different
  column pairs (one shifted, one not), so they get different values.
  That's the structural property the topology was supplying.
* Self-loops carry the per-service anomaly z-score, normalized by
  the max across services so they're comparable to the in-range
  edge weights. This anchors PPR on the services whose own metrics
  deviated most.

**Why it's defensible without topology.** The deployed call graph
encodes "u can affect v" prior knowledge; lagged correlation
encodes "u empirically did affect v" posterior evidence. The two
are different but compatible substitutes; the lagged form has the
advantage of being recoverable from telemetry alone.

**Where it falls short.** Without topology, the graph is dense (all
service pairs participate, weighted by their lagged correlations).
On RE1-OB the densification doesn't hurt — see the attributed-graph
diagnostic below.

### Deviation 2: Anomaly detection via z-score, not BIRCH clustering

The paper detects anomalous services by online BIRCH clustering on
per-service metric vectors and flagging points that don't fit any
established cluster. We instead reuse the same `(post − pre) / σ_pre`
z-score MonitorRank and CausalRCA compute. This makes the three
methods directly comparable on the anomaly-scoring axis (so any
performance difference is attributable to the *structural* step,
not to a method-specific anomaly detector) and removes BIRCH's
sensitivity to its `threshold` / `branching_factor` hyperparameters,
which the paper does not pin down.

### Deviation 3: Explanation chain carries attributed-graph edges

Like CausalRCA, `CanonicalExplanation` for MicroRCA includes one
`ExplanationAtom` per top-K service plus `CausalLink` edges drawn
from the attributed graph induced on those services. The
``relation_type`` is `"anomaly-correlates-with"`, distinguishing
these edges from CausalRCA's `"causes"` — MicroRCA's edges are
correlational, not causal in the SEM sense. Self-loops are dropped
from the explanation graph because they live inside the
personalization and add visual clutter.

### Deviation 4: Schema normalization upstream of method input

Same as the analogous points for MonitorRank and CausalRCA. The
method consumes a `NormalizedCase`; the preprocessing differs from
the paper's, but is upstream of the algorithm itself.

### Attributed-graph effect diagnostic (brief §9)

The harness emits an extra `AC@1_collapsed` column where MicroRCA
is re-run with `collapsed_graph=True` (edges are symmetric Pearson
on the post-onset signals, no lag). The delta between `AC@1` and
`AC@1_collapsed` is the paper-relevant question: does MicroRCA's
asymmetric edge weighting genuinely add discriminating power on
this dataset?

| fault   | n  | AC@1  | AC@1_collapsed | delta  |
|---------|----|-------|----------------|--------|
| cpu     | 25 | 0.680 | 0.680          | 0.000  |
| delay   | 25 | 0.960 | 0.960          | 0.000  |
| disk    | 25 | 0.720 | 0.720          | 0.000  |
| loss    | 25 | 0.080 | 0.080          | 0.000  |
| mem     | 25 | 0.680 | 0.680          | 0.000  |
| overall |125 | 0.624 | 0.624          | 0.000  |

The delta is exactly zero on every fault. Symmetric correlation
produces the same top-1 service as asymmetric lagged correlation in
every one of the 125 cases. **The asymmetric edge weighting adds no
discriminating power on RE1-OB.** This is the same shape of finding
CausalRCA produced for its PC-algorithm causal-discovery step: the
per-service anomaly signal carries the entire result; whatever
structural step sits on top is structurally underdetermining the
rank.

### Validation against published baselines

Validated via (a) synthetic 3-service and 5-service scenarios with
a clear root cause, plus an asymmetry test that confirms the
attributed graph genuinely puts higher weight on the "leader" of a
constructed lead-lag pair (`evaluation/tests/test_microrca.py`), and
(b) per-fault-type AC@k on all 125 RE1-OB cases. Results live in
`results/week2_microrca_validation.csv`.

**Headline numbers** (RE1-OB, inject-time-clean contract):

| fault   | n  | AC@1  | AC@3  | AC@5  | MRR   | S(M)  | AC@1_random | AC@1_collapsed |
|---------|----|-------|-------|-------|-------|-------|-------------|----------------|
| cpu     | 25 | 0.680 | 0.760 | 0.760 | 0.743 | 0.000 | 0.440       | 0.680          |
| delay   | 25 | 0.960 | 0.960 | 0.960 | 0.964 | 0.000 | 0.400       | 0.960          |
| disk    | 25 | 0.720 | 0.960 | 1.000 | 0.837 | 0.000 | 0.320       | 0.720          |
| loss    | 25 | 0.080 | 0.480 | 0.800 | 0.354 | 0.000 | 0.040       | 0.080          |
| mem     | 25 | 0.680 | 0.720 | 0.720 | 0.722 | 0.000 | 0.680       | 0.680          |
| overall |125 | 0.624 | 0.776 | 0.848 | 0.724 | 0.000 | 0.376       | 0.624          |

**Same dataset-preprocessing advantage observed.** Overall AC@1 =
0.624 sits at the very top of the brief's expanded [0.10, 0.65]
band and is essentially identical to MonitorRank (0.632) and
CausalRCA (0.624) on the same normalized telemetry. The pattern is
now firmly established across three methods with three different
structural foundations (random-walk PageRank, PC-algorithm causal
discovery, attributed-graph PPR): on RE1-OB step-change injections,
the per-service post-vs-pre z-score carries the result.
RCAEval did not publish MicroRCA-specific AC@k numbers we can
directly compare against in the same way Table 5 did for MicroCause
and MicroRank; the inter-method comparison within our suite is the
strongest available reference.

## BARO (Pham, Ha, Zhang; FSE 2024, art. 98)

BARO's core contribution is **multivariate Bayesian Online Change-
Point Detection (BOCPD)** on the metric matrix, followed by per-
service root-cause scoring via a RobustScaler-style post-change-
point shift magnitude. Because BARO does its own change-point
detection from telemetry alone, the inject-time-clean contract is a
natural fit — there is no `inject_time` dependency to remove.

### Deviation 0: Method-internal change-point detector (not the shared one)

The other three method adapters (MonitorRank, CausalRCA, MicroRCA)
all reuse `evaluation.methods._onset.detect_onset` — a z-score-based
pivot search that scans the central 25–75 % band of the case window
for the time that maximises Σ_svc Σ_feat |mean(post) − mean(pre)| /
std(pre). BARO does **not** reuse this utility. Its
`_detect_change_point` is a from-scratch univariate-Gaussian BOCPD
with a diagonal-multivariate predictive (sum of per-dimension log
predictives), applied to the standardized matrix of canonical
service-feature columns.

The rationale is that BARO's change-point detector is its core
contribution. Reusing the shared z-score utility would have made
BARO an indistinguishable variant of the previous three methods —
the cross-method comparison would have degenerated to "which scoring
rule on top of a fixed pivot." The brief makes this point explicit
in §2. The on-by-default detector is BOCPD; the harness exposes
a `--with-zscore-onset` diagnostic flag that swaps BARO's BOCPD for
`detect_onset` and keeps the rest of the scoring pipeline (§9
change-point-detector comparison).

### Deviation 1: Diagonal multivariate predictive (not full covariance)

The published BARO method specifies a **multivariate** BOCPD
predictive. The proper formulation uses a Normal-Inverse-Wishart
conjugate prior with a full posterior covariance over all monitored
dimensions, yielding a Student-t multivariate predictive at each
step. We instead use a diagonal multivariate predictive: the per-
dimension predictive is a univariate Gaussian with a Normal prior on
the mean (known observation variance, estimated from the first
quarter of the window), and the joint log predictive across
dimensions is the sum of per-dimension log predictives.

Two reasons:

1. **No scipy dependency.** The Normal-Inverse-Wishart predictive
   needs the multivariate Student-t density, which needs the gamma
   function. The evaluation package's `pyproject.toml` keeps the
   surface to `numpy / pandas / networkx / owlready2 / pytest`; we
   would have either added a scipy dependency or implemented gamma
   via `math.lgamma` elementwise.
2. **Numerical robustness.** Full multivariate posteriors over
   ~30-dimensional service-feature matrices on 1200-sample windows
   were numerically unstable in early prototyping: the
   posterior precision matrix degenerated under the truncated
   run-length scheme. The diagonal version is well-conditioned
   throughout and aligns with the diagonal-Gaussian assumption that
   most published BOCPD implementations make in practice (e.g.,
   `bayesian-changepoint-detection` on PyPI).

The pure RCAEval reference (`RCAEval/e2e/baro.py`) does **not**
actually implement BOCPD — it takes `inject_time` as input and just
runs a RobustScaler+max-z scoring step. So the diagonal-multivariate
BOCPD here is already strictly more faithful to the BARO paper than
the RCAEval reference.

### Deviation 2: Truncated run-length distribution

Standard Adams & MacKay (2007) BOCPD maintains a run-length
distribution that grows by one entry every sample, giving O(T²)
memory and time per signal. We truncate it at `max_run_length=250`
samples (default), renormalising after each truncation. This is the
standard practical optimisation and is described in the Adams &
MacKay paper itself. It has no effect on the change-point estimate
when the true segment is shorter than the cap (which is always the
case for the RCAEval RE1 injection cadence: roughly one anomalous
segment per 20-minute case).

### Deviation 3: Observation variance estimated, not given a hyperprior

The full BOCPD treatment puts an Inverse-Gamma prior on the
per-dimension observation variance and integrates it out. We instead
estimate the per-dimension observation variance from the first
quarter of the window (treating it as pre-anomaly normal). This is
the same shortcut every paper-grade BOCPD demo we surveyed takes
(including the original Adams & MacKay tech report's reference
notebook). The variance estimate gets a small numerical floor
(`obs_var_floor=1e-6`) so a wholly-flat input doesn't divide by
zero.

### Deviation 4: Detector restricted to the central [25 %, 75 %] band

After running BOCPD over the full window we restrict the argmax to
the central [25 %, 75 %] band of the cp-log-prob trace. The first
and last quarters carry boundary artefacts — the prefix is also
used to estimate `obs_var`, so a "change point" there is degenerate
— and the same band is the band that `evaluation.extraction.
schema_normalizer` uses for the per-case randomised injection
offset. This is identical in spirit to the shared `detect_onset`
utility's pivot band; the difference is purely in *what* statistic
is being maxed inside the band.

### Deviation 5: Per-service aggregation of column-level shifts

The RCAEval reference returns a *metric-level* ranking (column
names, e.g. `cartservice_cpu`). RCAEval RE1's ground truth is
service-level, so the reference's evaluation does a post-hoc string-
match on the column prefix to recover the service. We collapse this
step into the method by aggregating each service's canonical
features (latency / traffic / error / cpu / mem / disk / net) via
`sum` (default) or `max`. This matches the shape every other
adapter in this evaluation package returns and lets BARO go through
the same `accuracy_at_k` metric without a special-case adapter.

### Deviation 6: RobustScaler implemented natively, no sklearn

The RCAEval reference uses `sklearn.preprocessing.RobustScaler`
(median + IQR). We implement the equivalent transformation directly
in numpy (`_robust_z`): subtract the pre-segment median, divide by
the pre-segment IQR, take the max absolute value across the post
segment. Falls back to `std(pre)` when IQR is zero (a wholly-flat
pre-segment otherwise yields `inf`). Avoids the sklearn dependency.

### Deviation 7: Explanation chain is a change-point-rooted tree

BARO's natural explanation shape is "trigger event → set of services
sorted by post-trigger shift." We materialise this as a
`CanonicalExplanation` tree:

* One `ExplanationAtom` for the detected change point (text:
  `change point at t=… (P(r_t=0)=…)`), with `fuzzy_membership = `
  the BOCPD posterior.
* Top-K `ExplanationAtom`s for the highest-scoring services, each
  with `fuzzy_membership = score / score_max`.
* `CausalLink`s from the change-point atom out to each service atom
  with `weight = score / total_head_score` and
  `relation_type="post-change-shift-attribution"`.

This is a different shape from MicroRCA's attributed-graph
explanation, which has links between *services* rather than between
the trigger event and services. The intent matches the cross-method
explanation-fidelity metric: every method's explanation chain
captures the structural shape its underlying algorithm produces;
they are *not* normalised into a common shape.

### Deviation 8: Schema normalization upstream of method input

Same as the analogous point for the other three adapters. BARO
consumes a `NormalizedCase`; the preprocessing differs from the
paper's, but is upstream of the algorithm itself.

### Decomposition diagnostics (brief §8, §9)

The harness emits two BARO-specific diagnostic columns:

* `AC@1_random` — BARO's BOCPD is replaced by a uniformly-random
  in-band pivot. Isolates the contribution of the detector vs. the
  scoring mechanism.
* `AC@1_zscore_onset` — BARO's BOCPD is replaced by the shared
  z-score `detect_onset` utility. Discriminates "Bayesian change-
  point detection" vs. "z-score change-point detection" as a paper
  axis (brief §9).

The `S(BARO) = 0` shift-evaluation result is structural: BARO does
not read `ground_truth` from inside `diagnose`, so the ±300 s ground-
truth offset shift leaves the diagnosis bit-identical. This is
asserted both by `evaluation.methods._protocol.
validate_no_ground_truth_peeking` (static, before iteration) and by
the per-case comparison in the harness output.

### Validation against published baselines

Validated via (a) synthetic 3-service and 5-service scenarios with
a clear root cause, plus a BOCPD-band test that confirms the
detector lands inside the central band on a clear step injection
(`evaluation/tests/test_baro.py`), and (b) per-fault-type AC@k on
all 125 RE1-OB cases via `evaluation/experiments/evaluate_baro.py`.
Results live in `results/week2_baro_validation.csv`.

Headline-number tables and cross-method comparison live in
`paper/notes/findings.md` under "BARO entry" and the cross-method
finding block. The published BARO Avg@5 number is ~0.80 on RE2-TT;
our re-implementation's RE1-OB AC@1 is reported in the findings
note alongside the random-onset and z-score-onset decompositions.

### Headline numbers (committed code, post-fix)

| metric | value |
|--------|-------|
| Native overall AC@1 | **0.536** |
| Per-fault AC@1 | cpu 0.680, mem 0.800, disk 0.400, delay 0.680, loss 0.120 |
| Reference (RCAEval BARO, raw cols + inject_time) | 0.720 |
| Oracle (inject_time given, canonical schema) | 0.600 |
| Canonical-schema preprocessing gap (oracle vs ref) | 12.0 pp |
| BOCPD-vs-oracle gap (native vs oracle) | **6.4 pp** |
| Total reference-to-native gap | 18.4 pp |
| AC@1_random (random pivot) | 0.376 |
| AC@1_zscore_onset (z-score pivot) | 0.568 |
| BOCPD-vs-z-score gap | 3.2 pp (within noise) |
| S(M) | 0.000 (structural) |

**Note on the 0.480 in the original findings entry.** The findings
note committed at `d1eb0e9` quoted overall AC@1 = 0.480 and a
BOCPD-vs-oracle gap of 12 pp. Those numbers came from a pre-commit
dev iteration of `baro.py` and were superseded by a fix that landed
in `c9077b0` itself. The committed code produces 0.536. The
discrepancy was caught by the cross-method edge-shift diagnostic,
which independently re-ran BARO and observed 0.536. Full
investigation: `results/baro_discrepancy_investigation.md`. The
findings entry has been corrected.

## DejaVu (Li, Chen, et al.; FSE 2022)

DejaVu is the first **trained** method in the suite. It learns a small
neural classifier from historical labeled failure cases and predicts
``(failure_unit, failure_type)`` jointly for a new case. The
``RCAMethod`` base class now exposes a default no-op ``train`` that
DejaVu overrides; the AST-based protocol validator inspects only
``diagnose`` (training legitimately reads labels — that is the whole
point of supervised learning), so the train method is exempt by name.

### Deviation 0: Schema normalization upstream of training data

Same as the analogous point for the other four adapters. DejaVu sees
each training and test case as a ``NormalizedCase`` — bounded
``case_window``, canonical service-feature columns, randomized
injection offset. The paper's setting is the A0/A1/A2 cloud-service
benchmark with method-specific feature engineering; we substitute the
canonical schema for cross-method comparability. This is the only
deviation that exists *because* of the evaluation contract rather
than for tractability.

### Deviation 1: Single-head self-attention instead of full GAT

The published method uses a graph attention network over the service-
call graph. Two simplifications:

1. **No call graph** — RE1 doesn't ship one. We substitute a fully-
   connected service graph with mask attention over services-present-
   in-the-case. This collapses the GAT to a single-head scaled-dot-
   product self-attention over service embeddings; equivalent to a GAT
   on a complete graph.
2. **Single head** instead of multi-head. With 12 services and
   ``hidden=32``, multi-head adds ~3× the parameter count without
   measurable head specialisation on RE1-OB.

Total parameter count at the default configuration is ~10 k — well
under the brief's 1 M ceiling. The brief's intent was "small, focused
classifier, not a foundation model"; we are an order of magnitude
under even that.

### Deviation 2: 1D-Conv temporal encoder, not LSTM/Transformer

The published method uses an LSTM-based encoder (with attention) over
the per-service time series. We use two stacked Conv1d layers
(kernel 5, padding 2) followed by adaptive average pooling. Rationale:

* **Permutation invariance over time** — RCAEval's injection times
  are randomised inside the window via ``schema_normalizer``'s
  per-case offset hash. A recurrent encoder would learn to attend
  preferentially to specific window positions, which would not
  generalise. Conv + adaptive pool is shift-invariant by construction.
* **Speed.** CPU forward-pass on a 1200-step window with 12 services
  × 7 features takes ~10 ms; an LSTM over the same window is
  10–100× slower without measurable AC@k benefit on this dataset.

### Deviation 3: No graph-convolution propagation step

The DejaVu paper interleaves attention with graph convolution: the
attention output is fed back into a GCN layer using the call graph,
and the cycle repeats. We omit the GCN step — the attention is
already aware of every other service, and without a call graph the
GCN reduces to "average over neighbours" which the attention already
implements through its keys-and-values.

### Deviation 4: Service vocabulary = union of training-case services

The trained classifier has fixed output cardinality. We take the
service vocabulary as the union of services seen across the training
set. Test cases whose ground-truth service is outside that vocabulary
cannot possibly be ranked top-1 — the head simply does not have a
class for it. We log this as a hard ceiling for the harness's
reported AC@1 (no published equivalent of "vocabulary coverage" is in
the paper; the original DejaVu paper trains and tests within a fixed
A0/A1/A2 service set so this case does not arise there).

### Deviation 5: 5-fold cross-validation, stratified by fault type

The DejaVu paper uses time-based train/test splits on its A0/A1/A2
dataset. RCAEval RE1-OB has no such temporal partition; we use
5-fold cross-validation with stratification by fault type (cpu /
mem / disk / delay / loss). Fold assignment is deterministic via a
SHA-256-of-``case.id`` hash + a per-fault-group starting offset, so
the assignment reproduces exactly across runs and machines.

### Deviation 6: Joint loss with type-loss weight 0.5

The published method has separate failure-unit and failure-type
losses with a balancing weight. We use cross-entropy on both heads
with the type head weighted at 0.5; the primary objective is the
service rank (the AC@k metric scores it directly), so the type head
is held at half weight. Empirically: at 0.5 the model converges on
both heads; at 0.1 the type head underfits; at 1.0 the unit head
underfits.

### Deviation 7: Explanation chain rooted at the predicted failure type

DejaVu's interpretability claim is "attention attribution over
services." We surface this as a ``CanonicalExplanation`` graph:

* One atom for the predicted **failure type** (root, with
  ``ontology_class="foda:FailureType/{type}"``).
* Top-K atoms for the predicted **failure unit** services.
* Per-unit attention attribution: the top-3 most-attended services
  by the model's attention matrix, with
  ``relation_type="neural-attention-attribution"``.

This shape differs from BARO's "change-point → service" tree and
MicroRCA's "service ↔ service" attributed graph; the intent is to
preserve each method's own interpretability claim faithfully.

### Decomposition diagnostics (brief §8, §9)

The harness emits two DejaVu-specific diagnostics:

* **Training-size ablation** — train on ``N ∈ {25, 50, 75, 100}``
  cases and test on a fixed 25-case held-out fold-0. Isolates how
  much of DejaVu's AC@1 comes from training-data size vs.
  architecture: a flat ablation curve means the architecture is
  doing the work; a monotonically-growing curve means training data
  is contributing real signal.
* **Attention-sample dump** — 5 correct-prediction + 5 incorrect-
  prediction cases written to ``results/dejavu_attention_samples.json``
  with their full ``(S × S)`` attention matrices and service vocab.
  Material for Paper 6's SemanticGroundedness inspection.

### Validation against published baselines

The DejaVu paper reports AC@1 ≈ 0.50–0.65 on A0/A1/A2. RCAEval does
not publish DejaVu numbers. Our RE1-OB result is reported in
``paper/notes/findings.md`` under "DejaVu entry" alongside the
training-size ablation and the cross-method finding block.


## yRCA (Soldani, Bono, Brogi; Software: Practice and Experience 2022/2025)

The published yRCA is a Java/Prolog tool that turns a stream of typed
log events into an explanation graph by forward-chaining a Prolog
ruleset over a topology model. Its contribution is the **rule-based
causal-inference approach to explanation**, not the specific Prolog
engine; this adapter captures the methodology in pure Python on the
inject_time-clean :class:`NormalizedCase` contract.

Reference code: https://github.com/di-unipi-socc/yRCA.

### Deviation 1: Synthetic events synthesised from metrics, not logs

RCAEval RE1-OB ships metric-only telemetry; the published yRCA
consumes parsed application logs. We synthesise a discrete event
stream by running the shared
:func:`evaluation.methods._onset.detect_onset` to find an onset
pivot and emitting one event per ``(service, canonical feature)``
pair whose post-vs-pre z-score magnitude exceeds
``severity_threshold`` (default 3.0):

* ``z >= +severity_threshold`` ⇒ ``anomaly_high(service, feature)``
* ``z <= -severity_threshold`` ⇒ ``anomaly_low(service, feature)``
* ``|z| <= 1`` ⇒ ``normal(service, feature)`` (only when
  ``emit_normal_events=True``; optional baseline)

All events are timestamped at the detected onset, mirroring the
"each log line has a timestamp" property the published method
exploits. Because RE1-OB has no logs, **direct number comparison
with the published yRCA evaluation is not meaningful** — the
synthetic-event regime fundamentally restricts the rule engine to
window-level evidence (one event per service-feature pair),
whereas the original log-based regime sees many events per
service over time. We report yRCA's numbers as a comparison point
within this Paper 6's suite, not as a reproduction of the
published evaluation.

### Deviation 2: Pure-Python forward chaining instead of Prolog

The Prolog engine is replaced by an explicit forward-chaining loop
over a Python fact database. Each rule (R1–R5) is encoded as a
function; the engine iterates until no new facts are added or
``max_iterations`` is reached. Termination is guaranteed because
every rule strictly adds facts and the fact space is bounded by
``|services|² × |relations|``. The iteration count is exposed in
``raw_output`` for diagnostic visibility.

Five-rule core (faithful to the published reasoning logic; the
Prolog ruleset is richer in edge cases that don't fire under the
synthetic-event regime):

* **R1** — ``anomaly_high(s, f, t)`` or ``anomaly_low(s, f, t)``
  ⇒ ``potential_root_cause(s, f)``.
* **R2** — topology edge ``cause → dep`` AND ``cause`` has a
  potential_root_cause AND ``dep`` has its own anomaly with
  ``t_dep ≥ t_cause`` ⇒ ``explained_by(dep, cause)``.
* **R3** — ``potential_root_cause(s)`` AND no ``explained_by(s, _)``
  ⇒ ``final_root_cause(s)``.
* **R4** — retry cascade: upstream ``latency``/``error`` anomaly +
  downstream ``traffic`` anomaly along a topology edge ⇒
  ``explained_by(dep, cause)`` derived under rule_id ``R4_retry``.
* **R5** — timeout propagation: upstream ``latency`` anomaly +
  downstream ``latency`` anomaly along a topology edge ⇒
  ``explained_by(dep, cause)`` derived under rule_id ``R5_timeout``.

Dedup is on ``(relation, args, rule_id)``, not ``(relation, args)``,
so the same ``explained_by`` edge can be independently derived by
R2, R4, and R5; the multi-rule-derivation count drives the
confidence metric.

### Deviation 3: Topology inferred from feature correlations

The published yRCA reads an explicit topology from the system
specification. RCAEval has no call-graph metadata, so we infer
topology the same way MicroRCA does: directed edge ``u → v`` when
``|corr(u_signal[:T-lag], v_signal[lag:])|`` exceeds
``topology_threshold`` (default 0.5) AND that direction's lagged
correlation outranks the reverse. Self-loops are excluded; one
service representative signal is the dominant-anomaly feature
where present, otherwise the canonical-feature-priority order.

### Deviation 4: Derivation-multiplicity confidence

Native yRCA outputs a binary explanation (the chain exists or it
doesn't); a confidence score is not part of the published method.
We derive one: the fraction of ``final_root_cause`` services that
were independently supported by ≥ 2 distinct rule paths. A case
with one unambiguously over-derived root has high confidence;
multiple tied single-derivation candidates has low.

### Onset detection: shared utility

yRCA's event timestamps are anchored at the
:func:`evaluation.methods._onset.detect_onset` pivot. This is the
same opt-in shared utility that MonitorRank, CausalRCA, and
MicroRCA reuse. The adapter therefore inherits the detector's
edge-fragility under canonical preprocessing — see the cross-
method offset-robustness diagnostic in ``paper/notes/findings.md``.

### Decomposition diagnostics (brief §8, §9, Paper 6 §4)

The harness ``evaluate_yrca.py`` emits two yRCA-specific
diagnostic axes:

* **``--with-random-onset``** — replace
  :func:`detect_onset` with a uniformly-random in-band pivot.
  Detector-vs-rule-engine decomposition: how much of yRCA's AC@1
  comes from getting the onset right vs. from the rule reasoning
  over the synthesised events?
* **``--with-offset-robustness``** — re-normalize each case with
  the inject offset placed at the per-case hashed default,
  5 %, 95 %, and 50 % of the window. Reports the five offset-
  robustness columns (``a_standard``, ``b_edge_left``,
  ``b_edge_right``, ``b_edges_mean``, ``c_centered``) on the
  Paper 6 §4 standard reporting axis. yRCA inherits the shared
  ``_onset.detect_onset`` utility's [25 %, 75 %] search band
  constraint and is therefore expected to fragilise at edges
  similarly to MonitorRank / CausalRCA / MicroRCA.

### Validation against published baselines

The published yRCA evaluation uses a log-based microservice
dataset (Sock Shop with injected faults) and reports
explanation-correctness as the primary metric. Direct number
comparison against our RE1-OB run is not meaningful (see
Deviation 1). Our RE1-OB result is reported in
``paper/notes/findings.md`` under "yRCA entry" alongside the
cross-method offset-robustness update.

---

## FODA-FCP (Fuzzy Contribution Propagation; dissertation centerpiece, AICT 2026)

Implementation: ``evaluation/methods/foda_fcp.py``. Reference Java
implementation: ``fuzzy-rca-engine/src/main/java/com/foda/rca/``
(``FuzzyRcaEngineImpl``, ``FaultFuzzifierImpl``,
``MamdaniFuzzyRuleEngine``, ``DampedConfidencePropagator``,
``OntologyGroundedExplanationBuilder``). The Python adapter is a
faithful re-implementation of the AICT 2026 paper's five-phase
pipeline on the inject_time-clean :class:`NormalizedCase` contract.

The Mamdani rule base (16 rules, six fault categories, certainty
factors) and the damped Noisy-OR propagation equation (δ = 0.85
default, Eq. 4) are ported verbatim. The OWL vocabulary mapping
agrees with the Java reference's
``OntologyGroundedExplanationBuilder.CATEGORY_TO_FAULT_LOCAL_NAME``
table. Three substantive deviations follow.

### Deviation 0: Onset detected from telemetry, not read from inject_time

Same shape as MonitorRank / CausalRCA / MicroRCA / yRCA Deviation 0.
The AICT paper assumes the diagnostic engine is called at the moment
the fault is reported — i.e. a tooling layer hands FCP the
``ServiceMetrics`` snapshot for "now". Under the inject_time-removal
contract (Deviation N1 above), no such oracle exists; the adapter
calls :func:`evaluation.methods._onset.detect_onset` on
``case.case_window`` to pick a pre/post pivot. The pivot is used to
compute post-vs-pre z-scores that feed the fuzzifier.

Empirical witness: per-case ``AC@1`` is bit-identical between the
true run and the ±300 s shifted runs (shift moves only the side-
channel ``inject_time``, not ``case_window``). ``S(FODA-FCP) = 0.000``
overall and per-fault on RE1-OB; see
``results/week2_foda_fcp_validation.csv`` and
``evaluation/tests/test_foda_fcp.py::TestShiftInvariance``.

### Deviation 1: z-score-driven fuzzy memberships, not SLO-calibrated crisp thresholds

The Java fuzzifier (``FaultFuzzifierImpl``) uses SLO-calibrated
crisp thresholds in raw metric units:

| Term            | Threshold (raw units) |
|-----------------|-----------------------|
| ``cpu_HIGH``    | ≥ 85 %                |
| ``cpu_MEDIUM``  | 30–80 %               |
| ``latency_CRITICAL`` | ≥ 600 ms         |
| ``memory_HIGH`` | ≥ 90 %                |
| ``errorRate_HIGH``  | ≥ 15 %            |
| ``throughput_LOW`` | < 30 % of baseline |

These thresholds were calibrated for a specific deployment
environment (foda-fuzzy-ontology-diagnostics microservices). RCAEval
RE1-OB's canonical-schema ``{service}_{cpu, mem, latency, error,
traffic}`` columns are emitted on **different scales** per case (cpu
in [0, 1] as a fraction in some cases, raw counter values in
others; latency in seconds vs. milliseconds; traffic in req/min
vs. req/s; …). Applying the Java thresholds directly would
misclassify nearly every case.

The adapter substitutes a **z-score-driven fuzzification** that
preserves the LOW / MEDIUM / HIGH (and ELEVATED / CRITICAL / etc.)
shape of the Java fuzzifier but reads its input as post-vs-pre
z-magnitudes against the pre-onset baseline:

* ``HIGH`` = trap(|z|; 1, 3, ∞, ∞)
* ``MEDIUM`` = tri(|z|; 0.5, 1.5, 3)
* ``LOW`` = trap(|z|; 0, 0, 0.5, 1)
* ``CRITICAL`` = trap(z; 2, 4, ∞, ∞)   (signed: positive z only)
* ``ELEVATED`` = tri(z; 0.5, 2, 4)     (signed: positive z only)
* ``throughput_LOW`` = trap(−z; 0.5, 2, ∞, ∞)
  (i.e. high LOW membership when z is very negative, meaning the
  service's traffic dropped relative to baseline)

**Why** — the canonical-schema preprocessing in
``schema_normalizer`` is unit-agnostic by design (different RCAEval
benchmarks emit different units for the same canonical feature);
hardcoded raw-unit thresholds are incompatible. The z-score-driven
shape preserves the rule base's semantic intent (``cpu_HIGH`` =
"this service's CPU is anomalously high relative to its own
baseline") while being robust to unit changes.

**What we give up** — the rule base's certainty factors were
calibrated against the crisp threshold distribution. Under the
z-score regime the firing-strength distribution is different, so
the per-category aggregation magnitudes are not numerically
comparable to the Java reference. The qualitative ordering ("which
category wins for a CPU-saturated service") is preserved; the
absolute confidence value is not.

### Deviation 2: No deployed service-mesh topology — lagged correlation in its place

The AICT paper's FCP requires a service dependency graph (the
``ServiceDependencyGraph`` input to ``FuzzyRcaEngine.diagnose``).
RCAEval RE1 does not ship per-case topology metadata. We substitute
**lagged Pearson correlation** between services' representative
signals in the post-onset window, the same convention MicroRCA and
yRCA use:

* For each service, pick the canonical feature with the highest
  |z| as its representative signal (latency / traffic / cpu / mem /
  error). Fall back to the first available canonical feature when
  every feature is flat.
* For every ordered pair ``(u, v)``, add an edge ``u → v`` with
  weight ``|corr(u_signal[: T − lag], v_signal[lag:])|`` when (a)
  that weight exceeds ``topology_threshold`` (default 0.5) and (b)
  the forward direction's lagged correlation outranks the reverse.
* Self-loops excluded.

The damped Noisy-OR propagator (``_propagate_damped``) is a
faithful port of ``DampedConfidencePropagator``: reverse-
topological pass with ``P(s) = 1 − ∏(1 − C(t) · w · δ)`` and
``C(s) = 1 − (1 − H(s)) · (1 − P(s))``. On cyclic graphs (which
the inferred correlation graph can produce) the adapter falls
back to a Jacobi fixed-point iteration (``_propagate_iterative``),
faithful port of ``IterativeConfidencePropagator``.

### Deviation 3: Adapter-level explanation expansion (Recommendation atom + suggests_mitigation links)

The Java ``OntologyGroundedExplanationBuilder`` produces a
**six-paragraph natural-language string** with embedded
ContributingFactor and Recommendation enrichment from the OWL
graph. Paper 6 needs a **structured** CanonicalExplanation graph
whose nodes and edges can be inspected by the SemanticGroundedness
metrics phase (atoms with ontology classes, links with relation
types and weights). The adapter therefore expands the Java
output into:

* One :class:`ExplanationAtom` per service in the top-K head,
  tagged with the predicted Mamdani category's DiagnosticKB fault
  prototype as a **full URI**
  (``http://foda.com/ontology/diagnostic#CpuSaturation`` etc.).
  ``fuzzy_membership`` is the service's final confidence ``C(s)``
  normalized by the sum across the top-K head.
* One additional Recommendation atom for the predicted root cause,
  tagged with the ``Rec_*`` individual associated with the root's
  fault prototype (e.g. ``Rec_CpuSaturation``). Same fuzzy
  membership as the root atom.
* :class:`CausalLink` edges in three relation types:
  - ``contributes_to:propagation:noisy_or`` from every non-root
    ContributingFactor atom to the root atom, weighted by the FCP
    propagation contribution ``C(t) · w(root, t) · δ``.
  - ``suggests_mitigation:recommendation:fault_prototype`` from
    every ContributingFactor atom to the Recommendation atom,
    weighted by the source atom's fuzzy membership.
  - The relation_type suffix after the first colon documents the
    FCP sub-process that derived the link (``propagation:noisy_or``
    for Eq. 4 contributions, ``recommendation:fault_prototype`` for
    OWL-derived mitigation suggestions).

The natural-language string is **not** emitted — the structured
graph carries the same information in a form Paper 6's metrics
can consume directly. The atom text still mentions the ontology
class name and the fired Mamdani rules so a human can read the
chain without loading the OWL graph.

### Deviation 4: Confidence = top1_C / sum(C over top-K), not raw final_confidence

The Java reference reports ``RankedCause.finalConfidence`` (i.e.
``C(s)``) directly as the diagnostic confidence. The harness's
``DiagnosticOutput.confidence`` column is a cross-method-
comparable scalar in [0, 1] interpreted as "how concentrated is
the diagnosis on the top-1 candidate". The adapter therefore
synthesizes confidence as the relative concentration of fuzzy
contribution mass on the top-1 service within the top-K head:

```
confidence = top1_C / sum(C over top-K)
```

clipped to [0, 1]. A unique winner with much higher C than the
runners-up gives confidence near 1; a near-tie gives confidence
near 1/K. Mirrors the convention adopted by the other six
adapters (MR's ``1 − top2/top1``, CR's ``1 − top2/top1``, etc.)
so cross-method calibration analysis is meaningful.

### Onset detection: shared utility

FODA-FCP's pre/post split for fuzzifier z-score computation is
anchored at the :func:`evaluation.methods._onset.detect_onset`
pivot. This is the same opt-in shared utility that MonitorRank,
CausalRCA, MicroRCA, and yRCA reuse. The adapter therefore
inherits the detector's edge-fragility under canonical
preprocessing — see the cross-method offset-robustness diagnostic
in ``paper/notes/findings.md`` (FODA-FCP entry).

### Decomposition diagnostics (brief §8, §9, Paper 6 §4)

The harness ``evaluate_foda_fcp.py`` emits two FODA-FCP-specific
diagnostic axes:

* **``--with-random-onset``** — replace
  :func:`detect_onset` with a uniformly-random in-band pivot.
  Detector-vs-rule-engine decomposition.
* **``--with-offset-robustness``** — re-normalize each case at the
  per-case hashed default, 5 %, 95 %, and 50 % of the window.
  Reports the five offset-robustness columns
  (``a_standard``, ``b_edge_left``, ``b_edge_right``,
  ``b_edges_mean``, ``c_centered``) on the Paper 6 §4 standard
  reporting axis. FODA-FCP inherits the shared
  ``_onset.detect_onset`` utility's [25 %, 75 %] search band
  constraint and is therefore expected to fragilise at edges
  similarly to MonitorRank / CausalRCA / MicroRCA / yRCA. The
  ``--append-offset-diagnostic`` flag appends per-case rows to
  the shared cross-method diagnostic CSV
  (``results/cross_method_offset_diagnostic.csv``) under
  ``method="FODA-FCP"``.

### Validation against published baselines

Validated via (a) synthetic 3-service and 5-service scenarios
with a clear root cause, plus the explanation-shape tests in
``evaluation/tests/test_foda_fcp.py::TestOntologyGroundedExplanation``
that assert atoms carry full DiagnosticKB URIs and that exactly
one Recommendation atom is emitted for the predicted root cause,
and (b) per-fault-type AC@k on all 125 RE1-OB cases via
``evaluation/experiments/evaluate_foda_fcp.py``. Results live in
``results/week2_foda_fcp_validation.csv``. Headline numbers and
cross-method comparison live in ``paper/notes/findings.md`` under
"FODA-FCP entry" and the final cross-method finding block.

The AICT 2026 paper's evaluation used a different
benchmark / deployment environment with calibrated SLO thresholds;
direct number comparison against the published AC@k figures is
not meaningful under canonical-schema preprocessing
(Deviation 1). FODA-FCP's value within Paper 6 is the
ontology-grounded **explanation chain** (Recommendation atom,
suggests_mitigation links, full DiagnosticKB URIs) that Paper 6
Phase 2's SemanticGroundedness metrics will measure against the
other six methods' chains.


## SemanticCoherence metric (Paper 6 Phase 2 Week 2)

### Design history: v1 → v2 → variant 4

SemanticCoherence (SC) scores each :class:`CausalLink` in an
explanation against the propagation patterns encoded in
``ontology/DiagnosticKB.owl``'s ``Propagation`` table (22
typical-propagation individuals; strengths ``ω ∈ {0.5, 1.0}``).
The metric went through two redesigns before reaching its final
form; both prior versions are documented here as deviations from
the brief's initial specification because the v2 / variant-4
choice materially changes what SC measures.

**v1 (initial brief).** Lookup ``(source_class, target_class)``
literal; coherent ⇒ subscore ``1 − |ω − link.weight|``;
incoherent (ω == 0) ⇒ subscore 0.0; unmapped (endpoint URI
unknown) ⇒ subscore 0.0. The brief proposed an alarm at FCP
SC ≥ 0.50.

* Observed v1 result on RE1-OB: FCP SC = 0.006 (alarm tripped).
* Diagnosed three issues:
  1. Direction mismatch — FCP's ``contributes_to`` runs
     effect→cause (Noisy-OR back-flow); v1 looked up the literal
     pair and counted every contributes_to link as incoherent.
  2. Non-Fault endpoints — ``suggests_mitigation`` links target
     ``Rec_*`` individuals and FCP's no-rule-fired non-roots
     target the abstract ``ContributingFactor`` class; v1
     counted these as incoherent rather than out-of-scope.
  3. Weight-vs-strength mismatch — FCP's link ``weight`` is the
     Noisy-OR contribution ``μ × Pearson × δ`` (mean ≈ 0.05,
     median 0.000), not a propagation typicality (≈ 0.8). The
     formula ``1 − |ω − w|`` punished every direction-correct
     link by ~0.74 on average.

**v2 (intermediate).** Added back-flow direction swap for
``contributes_to`` / ``explained_by``; introduced fault-prototype
filtering (non-Fault endpoints ⇒ ``unmapped`` not incoherent);
kept the weight-consistency formula. Lifted FCP SC from 0.006 to
0.037 — still below the 0.50 alarm.

A diagnostic counter (see ``paper/notes/findings.md`` §
"Phase 2 Week 2 v3 — SC alarm investigation") then quantified
the residual issues:

* 31.7 % of FCP links ARE Fault → Fault (165 / 520) — well
  above the 10 % structural bar; FCP is generating the right
  link shape.
* 51 % of those Fault→Fault links are direction-coherent against
  the ontology (84 / 165).
* But coherent-link weight distribution: mean 0.053, median
  0.000, max 0.277. Ontology strengths: mean 0.792.
  Mean ``|ω − w|`` = 0.738.

The weight-consistency formula was the dominant penalty. It
asked FCP's noisy-OR-attenuated contribution magnitudes to match
ontology typicalities — two quantities that aren't commensurable.

**Variant 4 (final).** Three changes from v2:

1. **Drop the weight-consistency penalty entirely.** A coherent
   link's subscore is simply ``ω`` — the ontology's typicality
   strength. Direction-correct, typicality-aware: a typical
   propagation (1.0) outscores a conditional one (0.5), and the
   link weight is informational only.

2. **Restrict scoring to propagation-relation links.** Only
   links whose ``relation_type`` starts with a prefix in
   :data:`PROPAGATION_RELATIONS` (``contributes_to``,
   ``explained_by``, ``caused_by``, ``causes``, ``propagates_to``,
   ``leads_to``) are scored. Mitigation links (relation_type
   contains ``"mitigation"``, ``"recommend"``, or
   ``"suggests"``) are **excluded from the denominator** —
   classification ``"excluded_mitigation"``. Other relation
   types (``None``, ``"anomaly-correlates-with"``,
   ``"rule_derived_explanation"``) are ``unmapped``.

3. **Add the ``excluded_mitigation_links`` and
   ``scored_link_count`` fields** to
   :meth:`SemanticCoherence.score_with_breakdown` so callers
   can see what was excluded and the denominator that produced
   the overall score.

The v1 weight-consistency formula and v2 mixed scoring/filtering
are no longer reachable — variant 4 is the metric's canonical
implementation.

### Rationale for the variant-4 design choice

The diagnostic in §"Phase 2 Week 2 v3" of findings.md confirmed
two structural facts:

* FCP's link weight ``μ × Pearson × δ`` is a **damped Noisy-OR
  contribution magnitude**, NOT a propagation typicality
  estimate. The two quantities measure different things;
  forcing them to match was the v2 design's error.
* FCP's ``suggests_mitigation`` links account for 48.1 % of
  all emitted links and are structurally never coherent
  (Recommendation isn't a fault prototype). Including them in
  SC's denominator was punishing FCP for surfacing operator-
  actionable mitigation suggestions — the opposite of the
  desired incentive.

The variant-4 choice is the smallest defensible change that
preserves SC's intent ("does the explanation respect the
ontology's propagation patterns?") while removing the two
non-features that were dragging the score.

### Cross-method properties under variant 4

* FCP SC ≈ 0.27 (was 0.037 under v2). Per-fault: cpu 0.380,
  mem 0.460, disk 0.280, loss 0.160, delay 0.050.
* yRCA SC ≈ 0.000 — yRCA's atoms carry ``yrca:Role/*``
  foreign-namespace URIs, so every link is unmapped regardless
  of relation type.
* MR / CR / Micro / BARO / DejaVu SC = 0.000 — atoms lack
  DiagnosticKB ontology classes; every link unmapped.
* ρ(AC@1, SC) and ρ(SG, SC) under variant 4 — see findings.md
  for the numbers and the ≤ 0.5 orthogonality property.

### Knobs exposed for future use

* :data:`PROPAGATION_RELATIONS` — extend if a future adapter
  emits a custom propagation shape (e.g. ``"derived_from"``).
* :data:`_BACK_FLOW_RELATIONS` — the subset whose direction is
  reversed before the ontology lookup.
* :data:`_MITIGATION_TOKENS` — substrings whose presence in a
  ``relation_type`` triggers mitigation exclusion. ``"suggests"``
  and ``"recommend"`` and ``"mitigation"`` cover all current
  adapters.

The propagation strengths themselves live in the ontology, not in
the metric module. Calibrating SC to a different deployment's
fault-propagation regime means editing
``ontology/DiagnosticKB.owl``, not the metric.


## ExplanationCompleteness metric (Paper 6 Phase 2 Week 3)

### Three-category contract

EC scores three binary detectors (root cause type, affected
component, mitigation recommendation) and reports their fraction
in ``{0.0, 0.333, 0.667, 1.0}``. Each detector accepts an atom
either via its ``ontology_class`` URI membership in a
category-specific DiagnosticKB set or via a token-aligned label
match against the same category's labels at coverage ≥ 0.7
(SG's threshold). The component detector additionally accepts a
whole-token match against the case's ``services`` list — needed
because DiagnosticKB doesn't enumerate specific microservices.

### Strict cause-detection threshold (design choice)

The text-level cause detector uses the **same 0.7 coverage
threshold as Week 1's SG**. This is a deliberate choice with
trade-offs on cross-method comparability:

* **Strict reading (shipped).** A method that emits a fault
  label as a bare service-type token (DejaVu's ``"predicted
  failure type: cpu"`` → bare token ``"cpu"``) does **not**
  whole-token-cover the DiagnosticKB label ``"CPU Saturation"``
  at 0.7 (coverage is 1/2 = 0.5). Result: DejaVu's failure-
  type atom does **not** trigger ``has_cause``; DejaVu's EC on
  RE1-OB is 0.333 (component only).

  The rationale: a method that names a fault as ``"cpu"``
  without naming the fault class
  (``"CpuSaturation"`` / ``"CPU Saturation"`` / equivalent) is
  undercommunicating diagnostic content. The operator reading
  ``"predicted failure type: cpu"`` learns *which kind of
  symptom* but not *which fault prototype the explanation
  asserts*. EC's strict reading enforces conformance to
  DiagnosticKB's vocabulary as a precondition for the cause
  credit, the same way SG's atom-level grounding enforces it
  for atom-level credit.

* **Lenient alternative (NOT shipped).** A variant that accepts
  single-token matches against single-token Fault labels (e.g.,
  ``"cpu"`` against ``"CpuSaturation"`` after dropping the
  ``"saturation"`` portion, or against a ``label_aliases`` list
  including ``"cpu"`` as a synonym) would raise DejaVu's EC to
  ``0.667`` (cause + component, no mitigation). yRCA's
  ``"derived_by_rules=['cpu_high']"`` text, similarly tokenised
  to ``{cpu, high}``, would still need the alias table.

  Trade-off: the lenient rule increases EC values for non-
  DiagnosticKB-vocabulary methods at the cost of letting any
  text containing ``"cpu"`` count as a cause claim — including
  free-text atoms like ``"cpu_usage spiked at t=42"`` that name
  the *metric* not the *fault prototype*. We judge this too
  permissive for Paper 6's "structured explanation" axis.

* **Cross-vocabulary alias table (future work).** A more
  defensible loosening would maintain an explicit
  ``{benchmark_category: ontology_fault_uri}`` map (e.g.,
  RCAEval ``"cpu"`` → DiagnosticKB ``"#CpuSaturation"``) and
  consult it before falling back to the token-coverage rule.
  This is out of scope for the dissertation but a natural
  Week-5+ extension if Paper 6 wants to credit benchmark-
  vocabulary fault names without weakening the strict rule.

The strict choice means **the 0.333 floor that MR / CR / Micro /
BARO / DejaVu / yRCA all hit is a structural property of the
metric**, not a measurement defect. It says "these methods do
not produce DiagnosticKB-vocabulary fault-type content"; the
service-name text rule still credits the component category for
all of them, so they don't collapse to zero. FCP's 0.824 mean
reflects the only method that surfaces DiagnosticKB
fault/recommendation atoms across the case suite.

### Mitigation detector

Symmetric to the cause detector: accepts atoms whose
``ontology_class`` is in the Recommendation URI set, or whose
text whole-token-covers a Recommendation label at 0.7. No
single-token or lenient variant shipped. Only FCP currently
emits ``Rec_*`` atoms; the strict rule is consistent with the
cause detector's design.

### Affected-component detector

Asymmetric to the other two: in addition to ontology-side URI
membership (``MicroService`` class), it accepts a **whole content
token** match against the case's ``services`` list. Whole-token
match defends against substring artifacts
(``"adservice"`` ∉ ``"loadservice"`` tokenisation). The
service-name path is what lifts every method's EC off zero —
all six non-FCP methods produce atoms naming the affected
service in text.

### Knobs exposed for future use

* :data:`_TEXT_MATCH_THRESHOLD` (= 0.7) — coverage cutoff,
  matched to Week 1 SG.
* :data:`_MIN_TOKEN_LEN` (= 3) — content-token minimum length.
* :data:`PROPAGATION_RELATIONS` is **not** used by EC (only by
  SC); EC's category sets come from the OntologyAdapter
  helpers added in Week 3 (``list_fault_prototypes``,
  ``list_recommendations``, ``list_microservices``).

### Cross-method properties on RE1-OB

* FCP EC = 0.824 — driven by 90 / 125 cases scoring 1.0 (full
  three-category chain). 31 cases score 0.333 (silent Mamdani
  + silent fuzzy fallback) and 4 score 0.667 (cause but no
  mitigation). The 0.824 ≠ 0.9 gap is the same Phase-1 cpu-
  vs-mem asymmetry projected onto the completeness axis.
* yRCA / DejaVu / MR / CR / Micro / BARO EC = 0.333 — all hit
  the floor under the strict reading; service-name text
  match fires, cause and mitigation detectors do not.
* ρ(SG, EC) and ρ(SC, EC) — see findings.md for the numbers
  and the "high correlations reflect the lack of
  ontology-grounded baselines" caveat.

### Why we ship strict

The strict reading makes EC's claim auditable: a method's
``has_cause = 1`` IS a claim about that method's DiagnosticKB-
vocabulary conformance, full stop. Loosening it via single-
token matches or aliases changes that claim ("the method
**may** be referring to a DiagnosticKB fault prototype") and
introduces tuning surface area that's bad for cross-paper
comparability. The strict rule is conservative; readers can
infer "method X surfaces a fault type in some vocabulary"
from AC@1 + the per-method explanation snippets, without
needing EC to credit it implicitly.


## ConfidenceCalibration metric (Paper 6 Phase 2 Week 4)

### Aggregate-only contract (Option A architecture)

Weeks 1–3 of Phase 2 shipped three **per-case** semantic-quality
metrics (SG, SC, EC) that subclass :class:`SemanticMetric` and
reduce a ``(CanonicalExplanation, OntologyAdapter)`` pair to a
scalar score. ConfidenceCalibration deliberately breaks this
contract: ECE is the average across buckets of
``|mean(confidence) − mean(accuracy)|``, and a single
(confidence, correct) pair carries **no** calibration information
— "0.8 confidence, correct" is well-calibrated iff *across* high-
confidence cases the empirical accuracy averages near 0.8.

We considered two designs:

* **Option A (shipped)** — :class:`ConfidenceCalibration` is a
  standalone analyzer; the public surface is
  ``compute_ece(case_results, n_bins) -> float`` and
  ``compute_reliability_diagram(case_results, n_bins) -> dict``.
  No :class:`SemanticMetric` subclass, no ``score(explanation,
  ontology) -> float`` signature.

* Option B — Force a fictional per-case "calibration
  contribution" that sums to ECE in aggregate. Rejected: ECE is
  not naturally decomposable, and a fabricated per-case score
  would either misrepresent the metric or duplicate the Brier-
  style ``|confidence − target|`` proxy.

The Option-A asymmetry is the price of keeping ECE
mathematically honest. Three of the four Phase-2 metrics share
the per-case contract; the fourth complements them by reporting
an explicitly aggregate property — *does the method know when
it's right?* — that no per-case lens can answer.

### Per-case proxy for cross-metric Spearman

ECE itself can't enter the per-case Spearman analysis the Phase
2 harnesses already report (ρ across all 875 method-case pairs).
For the Week 4 correlations against AC@1 / SG / SC / EC we ship
:func:`per_case_calibration_error`:

    cal_error = |confidence − (1.0 if correct else 0.0)|

Brier-style absolute error. Zero when confidence and correctness
agree (high-conf + correct, or low-conf + wrong), large when
they mismatch. **Not** identical to ECE — the bucketed averaging
is what makes ECE a calibration metric rather than a scoring
rule — but it preserves the directionally-relevant signal
required for the per-case ρ. Both readings ship: aggregate ECE
in the CSV, ``cal_error`` for the per-case correlations.

### Default ``n_bins = 10``

Ten equal-width buckets across [0, 1] is the convention in Guo
et al. 2017 ("On Calibration of Modern Neural Networks") and
matches the reliability-diagram resolution that lets us call out
mid-range vs. tail miscalibration without overfitting to small-
bucket noise on 125-case populations. The argument is exposed
on :class:`ConfidenceCalibration` and the harness CLI for ablation.

### Right-edge inclusivity at confidence 1.0

A confidence of exactly 1.0 lands in the **last** bucket (index
``n_bins - 1``), not in a non-existent ``n_bins``-th bucket.
Without this, BARO and DejaVu cases at confidence 1.0 (top1
posterior, peaked softmax) would silently drop from ECE. The
matching ``_bucket_index`` helper documents the rule and is
covered by ``test_confidence_calibration.py::TestBucketIndex``.

### Confidence harvested from in-memory DiagnosticOutput, not CSV

The Phase-1 per-method validation CSVs in ``results/week2_*.csv``
**do not** contain a ``confidence`` column — they were written
before Paper 6 Phase 2 needed the field. Rather than re-write
seven CSVs (and risk drift between persisted and re-run values),
the Week 4 harness reads :attr:`DiagnosticOutput.confidence` at
runtime by calling ``method.diagnose_normalized`` over the 125
RE1-OB cases, exactly as the Week 3 EC harness does. All seven
methods emit a non-None confidence today:

* **BARO** — BOCPD marginal posterior ``P(r_t = 0 | x_{1:t})`` at
  the detected change-point timestep (``baro.py:_confidence``).
  The head-ratio ``top1 / (top1 + top2)`` is the **fallback** path
  used only when the posterior is non-finite (under diagnostic
  monkey-patch variants such as ``--with-zscore-onset``). On RE1-OB
  the BOCPD-posterior path always runs, and Week 4 reads
  ``peak_confidence`` instead — see the BARO routing subsection
  below.
* **CausalRCA** — derived top1/top2 ratio: ``1 − top2/top1``,
  clipped to [0, 1] (``causalrca.py:_derived_confidence``).
* **MonitorRank / MicroRCA** — ``π_top1 / Σ_{i ∈ top_K} π_i``
  head ratio (``{monitorrank,microrca}.py:_derived_confidence``).
* **DejaVu** — softmax probability of the top-1 service after
  the joint type-and-instance head (``dejavu.py:460``).
* **yRCA** — derivation multiplicity:
  ``#multi_derived / #total_final_root_cause`` over the rule
  forward-chaining trace (``yrca.py:_derivation_multiplicity_
  confidence``).
* **FODA-FCP** — ``top1_C / Σ_{i ∈ top_K} C_i`` over the
  Noisy-OR propagation values, matching the harness's convention
  of head-normalised confidence (``foda_fcp.py:999``).

If a future method emits ``DiagnosticOutput.confidence = None``,
the harness raises immediately at row construction — a silent
None would corrupt ECE without a visible failure.

### BARO routing: peak_confidence for cross-method calibration

Six of seven methods (CR, MR, Micro, DejaVu, yRCA, FCP) emit a
confidence value on the [0, 1] head-ratio / softmax scale: a sharp
top-1 lead yields a confidence near 1, a flat ranking yields a
confidence near 0. BARO's primary ``DiagnosticOutput.confidence``
emits something else — the BOCPD **marginal** posterior
``P(r_t = 0 | x_{1:t})`` at the chosen change-point timestep —
which is bounded by roughly ``1 / hazard_lambda`` (≈ 0.004 under
the default hazard prior) regardless of how peaked the change-
point distribution actually is. Comparing BARO's 0.004-bounded
posterior to MR/CR/Micro's [0, 1] head ratios on the same
calibration axis is uninformative; the gap between mean
confidence and accuracy reflects scale incompatibility, not
miscalibration.

The Week 4 fix adds a parallel ``peak_confidence`` field on
:class:`DiagnosticOutput`. For BARO, this is the band-normalised
posterior peak::

    peak_confidence = exp(max(log_band) − logsumexp(log_band))

— i.e., "probability mass at the peak moment **given** the change
point is in the central 25–75 % search band." Range [0, 1],
directly comparable to other methods' head-ratio / softmax scales.
Implemented as ``_compute_peak_confidence`` in ``baro.py``; the
primary ``confidence`` field is unchanged so callers that depend
on the absolute probabilistic interpretation are unaffected.

The Week 4 harness applies a single routing rule
(``_METHOD_CONFIDENCE_FIELD`` in ``run_phase2_cc.py``):

* For BARO: read ``DiagnosticOutput.peak_confidence``.
* For every other method: read ``DiagnosticOutput.confidence``.

This is the only method-specific routing in the harness; the
choice is a confidence-scale normalisation, not a method
modification. BARO's ranking and AC@1 (= 0.536) are unaffected.

**Empirical caveat (RE1-OB).** Despite the scale normalisation,
BARO's ECE on RE1-OB remained at 0.534 after the routing change.
The smoke-test inspection in Week 4's findings note (§6) revealed
that the BOCPD log-prob distribution on RE1-OB is **exactly flat**
across the search band: every timestep in the band has
``log_prob ≈ log(1 / hazard_lambda) ≈ -5.521``, with spread
``max − min = 0.000``. The hazard prior dominates the data
likelihood, so no peak emerges. ``peak_confidence`` is therefore
``1 / T_band ≈ 0.001667`` uniformly across all 125 cases. The
methodological fix to expose a [0, 1]-scaled BOCPD confidence is
correct in principle; the empirical observation on this benchmark
is that BARO's BOCPD does not localise the change point given the
adapter's default hyperparameters. ECE flags this as a property
of BARO-on-RE1-OB, not as a metric defect. Future revisions
(narrower hazard prior, narrower ``prior_var``, or a different
posterior summary such as ``top1 / Σ_topK`` over the score
shifts) could surface a discriminating confidence signal; that's
a Phase-1 design decision left out of Paper 6.

### Lower scores are better — the one direction-flipped metric

ECE ∈ [0, 1], with 0 = perfect calibration. This is the only
metric in the Phase 2 suite where the direction is **down**.
Findings tables flag this explicitly so a reader scanning the
SG/SC/EC/CC column row doesn't pattern-match "high = good"
across the four metrics. The harness ``print_summary`` also
flags it via the alarm-gate band labels.

### Why CC is the right metric for explanation-quality

A method's confidence is the diagnostic explanation's
*self-assessment*. ECE measures whether that self-assessment
tracks reality. A poorly-calibrated method that says "95 %
confident" while being right 30 % of the time produces an
explanation an operator cannot act on — the chain is structured
(SG, SC, EC may all be high) but the confidence signal is
unreliable. The four Phase-2 metrics together characterise:

* **SG** — atom-level groundedness (the explanation's
  vocabulary is the ontology's).
* **SC** — link-level coherence (the chain's propagation
  directions match the ontology's causal model).
* **EC** — operator-actionability (the chain answers the three
  operator questions).
* **CC (ECE)** — confidence-accuracy alignment (the
  explanation's stated certainty matches its empirical
  accuracy).

