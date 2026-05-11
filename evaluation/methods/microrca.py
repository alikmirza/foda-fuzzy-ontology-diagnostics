"""MicroRCA (Wu, Sun, Wang; NOMS 2020) refactored for the
inject_time-clean :class:`NormalizedCase` contract.

The published MicroRCA builds an **attributed service graph**:

* Nodes are services.
* Directed edges carry an asymmetric weight derived from temporal
  anomaly correlation between source and target service signals
  within the post-onset window. Asymmetry comes from the deployed
  service-mesh's call graph in the original paper; we don't have
  topology in RCAEval, so we substitute **lagged Pearson correlation**
  (``u → v`` uses ``corr(u[t], v[t + lag])``), which captures the
  "u leads v" intuition the topology would otherwise encode.
* Self-loops carry the per-service anomaly z-score, anchoring the
  walk on the services whose own metrics deviated most.

Personalized PageRank (α=0.85, 100 iterations) runs over the graph
with the normalized anomaly vector as personalization. The visit
frequency ranks services as candidate root causes.

Three design departures from the published paper are recorded in
``DEVIATIONS.md``:

1. **Onset detected from telemetry** — the published version assumes
   ``inject_time`` is given. Under the inject_time-removal contract
   that field is hidden; we call
   :func:`evaluation.methods._onset.detect_onset` on ``case_window``.
2. **No service-mesh topology** — RE1 doesn't ship call-graph
   metadata, so we substitute lagged correlation for the
   topology-directional weight.
3. **No BIRCH clustering for anomaly detection** — the paper uses
   BIRCH on per-service metrics; we use the same post-vs-pre z-score
   the other methods compute, for cross-method comparability.

Like CausalRCA, MicroRCA's :class:`CanonicalExplanation` carries
real :class:`CausalLink` edges drawn from the attributed graph
restricted to the top-K nodes. The explanation is the
attributed-graph neighborhood of the rank, not a flat list.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
import pandas as pd

from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    CausalLink,
    DiagnosticOutput,
    ExplanationAtom,
)
from ..extraction.schema_normalizer import (
    DEFAULT_WINDOW_SECONDS,
    NormalizedCase,
    normalize_case,
)
from ._onset import detect_onset
from .base import RCAMethod


_FEATURE_PRIORITY: tuple[str, ...] = (
    "latency",
    "traffic",
    "error",
    "cpu",
    "mem",
    "disk",
    "net",
)


@dataclass
class _ServiceAnomaly:
    """Per-service z-magnitude + dominant feature's full time-series.

    The signal is the column the attributed graph treats as the
    service's value when computing edge weights. Services with no
    usable signal fall back to the first available canonical column
    inside ``_build_attributed_graph``.
    """

    score: float = 0.0
    dominant_feature: str | None = None
    signal: np.ndarray | None = None
    per_feature: dict[str, float] = field(default_factory=dict)


class MicroRCAMethod(RCAMethod):
    """MicroRCA on :class:`NormalizedCase`.

    Parameters
    ----------
    alpha:
        PPR damping factor in ``(0, 1)``. Paper-default 0.85.
    n_iters:
        Power iterations for the PPR update. 100 per the paper, fixed
        for determinism.
    top_k:
        Size of the head used for ``confidence = visit_top1 /
        Σ visit_topK``. Also bounds the explanation atom count.
    lag:
        Sample lag for the asymmetric edge weight. ``lag=1`` is the
        default — large enough to break symmetry on RCAEval's median
        sampling rate, small enough that real lead-lag dynamics
        remain detectable. ``lag=0`` collapses the graph to a
        symmetric one (used by the harness's collapsed-graph
        diagnostic).
    collapsed_graph:
        When ``True``, build a symmetric Pearson-correlation graph
        instead of the asymmetric lagged-correlation one. This is
        the paper-relevant ablation that asks "does the attributed
        graph structure add discriminating power on this dataset, or
        does the per-service anomaly signal carry the entire result?"
    window_seconds:
        Total window length passed to ``normalize_case``.
    """

    name = "microrca"

    def __init__(
        self,
        alpha: float = 0.85,
        n_iters: int = 100,
        top_k: int = 3,
        lag: int = 1,
        collapsed_graph: bool = False,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if n_iters < 1:
            raise ValueError(f"n_iters must be >= 1, got {n_iters}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if lag < 0:
            raise ValueError(f"lag must be >= 0, got {lag}")
        if window_seconds <= 0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        self.alpha = alpha
        self.n_iters = n_iters
        self.top_k = top_k
        self.lag = lag
        self.collapsed_graph = collapsed_graph
        self.window_seconds = window_seconds

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run MicroRCA on a pre-built :class:`NormalizedCase`.

        The harness calls this directly so it can pass a normalized
        case whose ``ground_truth`` has been deliberately shifted —
        that shift must not move the output because we never read
        ``ground_truth`` from inside ``diagnose``. The static witness
        is :mod:`evaluation.methods._protocol`.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"MicroRCA: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        # Strategy A: detect onset from telemetry alone. Documented
        # in DEVIATIONS.md → MicroRCA adapter.
        onset_t = detect_onset(norm.case_window, norm.services)

        anomaly = _compute_anomaly(norm, onset_t)
        services = norm.services

        graph, edge_weights = _build_attributed_graph(
            anomaly=anomaly,
            services=services,
            case_window=norm.case_window,
            onset_time=onset_t,
            lag=self.lag,
            collapsed=self.collapsed_graph,
        )
        scores = _personalized_pagerank(
            graph=graph,
            services=services,
            personalization=_personalization_vector(anomaly),
            alpha=self.alpha,
            n_iters=self.n_iters,
        )

        ranked = sorted(
            ((s, scores[s]) for s in services),
            key=lambda kv: kv[1],
            reverse=True,
        )
        confidence = _derived_confidence(ranked, self.top_k)
        explanation = _build_attributed_explanation(
            ranked=ranked,
            anomaly=anomaly,
            graph=graph,
            edge_weights=edge_weights,
            top_k=self.top_k,
        )

        raw = {
            "anomaly_scores": {s: a.score for s, a in anomaly.items()},
            "dominant_features": {
                s: a.dominant_feature for s, a in anomaly.items()
            },
            "ppr_scores": dict(scores),
            "graph_edges": [
                (u, v, edge_weights.get((u, v), 1.0))
                for u, v in graph.edges()
            ],
            "onset_time": onset_t,
            "collapsed_graph": self.collapsed_graph,
        }

        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=raw,
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )


# ---- anomaly scoring ----


def _compute_anomaly(
    norm: NormalizedCase, onset_time: float
) -> dict[str, _ServiceAnomaly]:
    """Per-service z-magnitude AND the dominant feature's time-series.

    Same shape as the CausalRCA helper — we keep the function local
    so each method's anomaly-scoring policy can evolve independently.
    Currently identical: max |post − pre| / std(pre) across canonical
    features, and the signal of the winning feature.
    """
    df = norm.case_window
    pre_mask = df["time"] < onset_time
    post_mask = df["time"] >= onset_time
    out: dict[str, _ServiceAnomaly] = {}
    for svc in norm.services:
        a = _ServiceAnomaly()
        for feat in _FEATURE_PRIORITY:
            col = f"{svc}_{feat}"
            if col not in df.columns:
                continue
            x_full = df[col].to_numpy(dtype=float)
            x_pre = x_full[pre_mask.to_numpy()]
            x_post = x_full[post_mask.to_numpy()]
            if x_pre.size < 2 or x_post.size < 1:
                continue
            sd = float(x_pre.std())
            if sd == 0.0:
                continue
            z = abs(float(x_post.mean()) - float(x_pre.mean())) / sd
            if not np.isfinite(z):
                continue
            a.per_feature[feat] = z
            if z > a.score:
                a.score = z
                a.dominant_feature = feat
                a.signal = x_full
        out[svc] = a
    return out


# ---- attributed graph ----


def _build_attributed_graph(
    anomaly: dict[str, _ServiceAnomaly],
    services: list[str],
    case_window: pd.DataFrame,
    onset_time: float,
    lag: int,
    collapsed: bool,
) -> tuple[nx.DiGraph, dict[tuple[str, str], float]]:
    """Build the attributed service graph.

    * **Asymmetric mode** (``collapsed=False``): for every ordered
      pair ``(u, v)``, the edge weight is
      ``|corr(u_signal[0:T−lag], v_signal[lag:T])|`` within the
      post-onset window. ``u → v`` and ``v → u`` are different
      correlations because they look at different lagged column
      pairs — that's the asymmetry the published method gets from
      the call graph's direction, expressed here in temporal terms.
    * **Collapsed mode** (``collapsed=True``): symmetric Pearson on
      the post-onset signals, no lag. ``u → v`` and ``v → u`` get
      the same weight. This is the diagnostic ablation that asks
      whether the attributed graph adds discriminating power on the
      dataset; if the collapsed graph scores the same AC@1, it
      doesn't.

    Self-loops carry the per-service anomaly z-score (normalized by
    the max across services so they're comparable to the in-range
    edge weights).
    """
    df = case_window
    post_mask = (df["time"] >= onset_time).to_numpy()
    signals: dict[str, np.ndarray] = {}
    for svc in services:
        sig = anomaly[svc].signal
        if sig is None:
            sig = _fallback_signal(df, svc)
        if sig is None:
            continue
        signals[svc] = sig[post_mask].astype(float)

    graph = nx.DiGraph()
    graph.add_nodes_from(services)
    edge_weights: dict[tuple[str, str], float] = {}

    z_max = max((a.score for a in anomaly.values()), default=0.0) or 1.0
    for svc in services:
        w = anomaly[svc].score / z_max
        if not np.isfinite(w):
            w = 0.0
        if w > 0.0:
            graph.add_edge(svc, svc, weight=w)
            edge_weights[(svc, svc)] = w

    n = len(services)
    for i in range(n):
        u = services[i]
        su = signals.get(u)
        if su is None or su.size < max(lag, 1) + 2:
            continue
        for j in range(n):
            if i == j:
                continue
            v = services[j]
            sv = signals.get(v)
            if sv is None or sv.size < max(lag, 1) + 2:
                continue
            if collapsed or lag == 0:
                # Symmetric Pearson — same value as edge (v, u).
                if i < j or collapsed:
                    w = _corr(su, sv)
                else:
                    w = edge_weights.get((v, u), 0.0)
            else:
                w = _lagged_corr(su, sv, lag)
            if w > 0.0:
                graph.add_edge(u, v, weight=w)
                edge_weights[(u, v)] = w
    return graph, edge_weights


def _fallback_signal(
    case_window: pd.DataFrame, svc: str
) -> np.ndarray | None:
    for feat in _FEATURE_PRIORITY:
        col = f"{svc}_{feat}"
        if col in case_window.columns:
            return case_window[col].to_numpy(dtype=float)
    return None


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return 0.0
    n = min(a.size, b.size)
    a, b = a[:n], b[:n]
    if float(np.std(a)) == 0.0 or float(np.std(b)) == 0.0:
        return 0.0
    r = float(np.corrcoef(a, b)[0, 1])
    if not np.isfinite(r):
        return 0.0
    return max(0.0, min(1.0, abs(r)))


def _lagged_corr(a: np.ndarray, b: np.ndarray, lag: int) -> float:
    """Pearson correlation between ``a[:-lag]`` and ``b[lag:]``.

    Captures the "a leads b by ``lag`` samples" intuition: high values
    of this correlation mean ``a``'s past values predict ``b``'s
    present values. Asymmetric — ``_lagged_corr(b, a, lag)`` looks at
    different column pairs.
    """
    n = min(a.size, b.size)
    if n <= lag + 1:
        return 0.0
    a_head = a[: n - lag]
    b_tail = b[lag : n]
    return _corr(a_head, b_tail)


# ---- personalization ----


def _personalization_vector(
    anomaly: dict[str, _ServiceAnomaly]
) -> dict[str, float]:
    """Normalize anomaly scores to a probability distribution.

    Falls back to uniform when every service has zero anomaly (the
    PPR still runs, ranking by graph structure alone).
    """
    raw = {s: a.score for s, a in anomaly.items()}
    total = sum(raw.values())
    if total <= 0:
        n = len(raw) or 1
        return {s: 1.0 / n for s in raw}
    return {s: v / total for s, v in raw.items()}


# ---- personalized PageRank ----


def _personalized_pagerank(
    graph: nx.DiGraph,
    services: list[str],
    personalization: dict[str, float],
    alpha: float,
    n_iters: int,
) -> dict[str, float]:
    """Power-iteration PPR on the attributed graph.

    Mirrors :mod:`evaluation.methods.monitorrank`'s implementation so
    the two methods are comparable: same damping factor, same
    iteration count, same dangling-node handling (uniform restart on
    a row with no outgoing mass).
    """
    n = len(services)
    if n == 0:
        return {}
    idx = {s: i for i, s in enumerate(services)}

    A = np.zeros((n, n), dtype=float)
    for u, v, data in graph.edges(data=True):
        A[idx[u], idx[v]] = float(data.get("weight", 1.0))

    row_sums = A.sum(axis=1)
    P = np.zeros_like(A)
    for i in range(n):
        if row_sums[i] > 0:
            P[i] = A[i] / row_sums[i]
        else:
            P[i] = np.full(n, 1.0 / n)

    p = np.array([personalization.get(s, 0.0) for s in services], dtype=float)
    s_total = p.sum()
    if s_total <= 0:
        p = np.full(n, 1.0 / n)
    else:
        p = p / s_total

    pi = p.copy()
    for _ in range(n_iters):
        pi = alpha * (pi @ P) + (1.0 - alpha) * p

    return {services[i]: float(pi[i]) for i in range(n)}


# ---- output assembly ----


def _derived_confidence(
    ranked: list[tuple[str, float]], top_k: int
) -> float:
    """``visit_top1 / Σ visit_topK``, clipped to ``[0, 1]``."""
    if not ranked:
        return 0.0
    head = ranked[:top_k]
    total = sum(s for _, s in head)
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, head[0][1] / total))


def _build_attributed_explanation(
    ranked: list[tuple[str, float]],
    anomaly: dict[str, _ServiceAnomaly],
    graph: nx.DiGraph,
    edge_weights: dict[tuple[str, str], float],
    top_k: int,
) -> CanonicalExplanation:
    """Top-K atoms + the induced subgraph of attributed-graph edges
    between them.

    Self-loops are dropped from the explanation graph — they live
    inside the personalization, and rendering them as
    :class:`CausalLink` edges adds visual clutter without information.
    """
    explanation = CanonicalExplanation()
    head = ranked[:top_k]
    if not head:
        return explanation

    pi_max = max((s for _, s in head), default=1.0) or 1.0
    service_to_atom_id: dict[str, str] = {}
    for service, pi in head:
        a = anomaly.get(service)
        feat = a.dominant_feature if a is not None else None
        z = a.score if a is not None else 0.0
        if feat is not None:
            text = (
                f"{service}: anomalous {feat} (z={z:.2f}, π={pi:.4f})"
            )
        else:
            text = f"{service}: π={pi:.4f}"
        atom = ExplanationAtom(
            text=text,
            ontology_class=None,
            fuzzy_membership=max(0.0, min(1.0, pi / pi_max)),
        )
        explanation.add_atom(atom)
        service_to_atom_id[service] = atom.id

    for u, v in graph.edges():
        if u == v:
            continue
        if u in service_to_atom_id and v in service_to_atom_id:
            w = edge_weights.get((u, v), 1.0)
            explanation.add_link(
                CausalLink(
                    source_atom_id=service_to_atom_id[u],
                    target_atom_id=service_to_atom_id[v],
                    weight=max(0.0, min(1.0, float(w))),
                    relation_type="anomaly-correlates-with",
                )
            )
    return explanation
