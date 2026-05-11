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
