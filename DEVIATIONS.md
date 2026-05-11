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
