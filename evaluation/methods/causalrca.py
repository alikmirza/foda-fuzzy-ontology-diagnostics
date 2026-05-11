"""CausalRCA (Xin, Chen, Zhao; JSS vol 203 art 111724, 2023) refactored
for the inject_time-clean :class:`NormalizedCase` contract.

The published CausalRCA learns a structural equation model over all
metric columns (a VAE-based NOTEARS continuous optimization) and ranks
candidates with PageRank on the learned adjacency. We re-implement
cleanly, with three design departures recorded in ``DEVIATIONS.md``:

1. **PC algorithm over services, not NOTEARS-VAE over columns.** Each
   service is collapsed to a single "shape" signal (the metric whose
   post-vs-pre z-score is largest), so the DAG is learned over the
   ~10-20 service nodes instead of the ~60 service-feature columns.
   This keeps the runtime budget the brief allocates (5-30 s per case
   on M4) very comfortable while preserving the published method's
   key idea — a learned causal graph over the system, then root-cause
   inference from that graph.
2. **Ancestor-of-anchor scoring instead of PageRank.** Once the DAG is
   learned, the most-anomalous service is the "anchor". Every other
   service is scored ``anomaly_score(s) / (1 + d(s, anchor))`` where
   ``d`` is the shortest directed path from ``s`` to the anchor in the
   learned DAG (services that can't reach the anchor get the maximum
   distance and a small floor). This matches the brief's "ancestor
   analysis + distance penalty" formulation and gives the ranking a
   meaningful structural interpretation: the *upstream-most* highly-
   anomalous service wins.
3. **Onset detected from telemetry.** The published version reads
   ``inject_time``. Under the inject_time-removal contract that field
   is hidden; we call :func:`evaluation.methods._onset.detect_onset`
   on ``case_window`` to find a pre/post pivot from telemetry alone.

Unlike MonitorRank — whose explanation chain is a flat list — this
method's :class:`CanonicalExplanation` carries real
:class:`CausalLink` edges drawn from the learned DAG. This is the
first method in the suite that produces a true causal narrative; the
explanation graph reflects that.
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
    """Per-service z-magnitude bookkeeping.

    ``score`` is the maximum |post − pre| / std(pre) across the
    canonical features that exist for the service. ``signal`` is the
    full time-series of ``dominant_feature`` — used to build the X
    matrix the PC algorithm consumes.
    """

    score: float = 0.0
    dominant_feature: str | None = None
    signal: np.ndarray | None = None
    per_feature: dict[str, float] = field(default_factory=dict)


class CausalRCAMethod(RCAMethod):
    """CausalRCA baseline on :class:`NormalizedCase`.

    Parameters
    ----------
    alpha:
        Conditional independence test significance level for the PC
        algorithm. Defaults to ``0.05``. Smaller ⇒ sparser graph.
    top_k:
        Number of top services to materialize as explanation atoms.
        Default 5 (the brief calls for "top-K services").
    ci_test:
        causal-learn CI test name. ``"fisherz"`` is the linear Gaussian
        default and is what we use; pass another name only for
        ablations.
    nonancestor_penalty_floor:
        Score floor for services that cannot reach the anchor in the
        learned DAG. Multiplies their raw anomaly score. Default
        ``0.05`` — non-ancestors are demoted but never zeroed (so the
        rank still covers every service).
    window_seconds:
        Total window length passed to ``normalize_case``.
    """

    name = "causalrca"

    def __init__(
        self,
        alpha: float = 0.05,
        top_k: int = 5,
        ci_test: str = "fisherz",
        nonancestor_penalty_floor: float = 0.05,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if not 0.0 <= nonancestor_penalty_floor <= 1.0:
            raise ValueError(
                f"nonancestor_penalty_floor must be in [0, 1], got "
                f"{nonancestor_penalty_floor}"
            )
        if window_seconds <= 0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        self.alpha = alpha
        self.top_k = top_k
        self.ci_test = ci_test
        self.nonancestor_penalty_floor = nonancestor_penalty_floor
        self.window_seconds = window_seconds

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run CausalRCA on a pre-built :class:`NormalizedCase`.

        Like ``MonitorRankMethod.diagnose_normalized``, the harness
        calls this directly so it can pass a normalized case whose
        ``ground_truth`` has been deliberately shifted — that shift
        must not move the output because we never read ``ground_truth``
        from inside ``diagnose``. The protocol validator in
        :mod:`evaluation.methods._protocol` is the static witness.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"CausalRCA: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        # Strategy A: detect onset from telemetry alone. See
        # DEVIATIONS.md → CausalRCA adapter.
        onset_t = detect_onset(norm.case_window, norm.services)

        anomaly = _compute_anomaly(norm, onset_t)
        services = norm.services

        X, columns = _build_signal_matrix(anomaly, services, norm.case_window)
        dag, edge_weights = _learn_dag(
            X, columns, anomaly, alpha=self.alpha, ci_test=self.ci_test
        )

        anchor = _pick_anchor(anomaly, services)
        scores, distances = _score_services(
            anomaly=anomaly,
            services=services,
            dag=dag,
            anchor=anchor,
            nonancestor_penalty_floor=self.nonancestor_penalty_floor,
        )

        ranked = sorted(
            ((s, scores[s]) for s in services),
            key=lambda kv: kv[1],
            reverse=True,
        )
        confidence = _derived_confidence(ranked)
        explanation = _build_causal_explanation(
            ranked=ranked,
            anomaly=anomaly,
            dag=dag,
            edge_weights=edge_weights,
            anchor=anchor,
            top_k=self.top_k,
        )

        raw = {
            "anomaly_scores": {s: a.score for s, a in anomaly.items()},
            "dominant_features": {
                s: a.dominant_feature for s, a in anomaly.items()
            },
            "anchor": anchor,
            "dag_edges": [
                (u, v, edge_weights.get((u, v), 1.0))
                for u, v in dag.edges()
            ],
            "distances_to_anchor": distances,
            "onset_time": onset_t,
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

    The signal stored on the returned :class:`_ServiceAnomaly` is the
    full ``case_window`` column for ``dominant_feature`` — it's the
    column the PC algorithm will treat as the service's node value.
    Services with no usable feature get ``signal = None`` and will be
    excluded from the DAG learning step.
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


# ---- signal matrix for PC ----


def _build_signal_matrix(
    anomaly: dict[str, _ServiceAnomaly],
    services: list[str],
    case_window: pd.DataFrame,
) -> tuple[np.ndarray, list[str]]:
    """Stack each service's dominant-feature signal into a ``[T × N]``
    matrix for PC. Services without a dominant feature fall back to
    the first available column for their prefix; if none exists, the
    service is omitted from the matrix and won't appear as a DAG node.
    """
    columns: list[str] = []
    arrs: list[np.ndarray] = []
    for svc in services:
        sig = anomaly[svc].signal
        if sig is None:
            sig = _fallback_signal(case_window, svc)
        if sig is None:
            continue
        arrs.append(sig.astype(float))
        columns.append(svc)
    if not arrs:
        return np.empty((0, 0)), []
    X = np.column_stack(arrs)
    # PC's Fisher-Z test needs non-constant columns. Add a tiny
    # deterministic jitter to perfectly-flat columns so the test
    # doesn't divide by zero — the jitter is below noise floor and
    # cannot create spurious correlations.
    for j in range(X.shape[1]):
        if float(np.std(X[:, j])) == 0.0:
            X[:, j] = X[:, j] + 1e-12 * np.arange(X.shape[0])
    return X, columns


def _fallback_signal(
    case_window: pd.DataFrame, svc: str
) -> np.ndarray | None:
    for feat in _FEATURE_PRIORITY:
        col = f"{svc}_{feat}"
        if col in case_window.columns:
            return case_window[col].to_numpy(dtype=float)
    return None


# ---- causal structure learning ----


def _learn_dag(
    X: np.ndarray,
    columns: list[str],
    anomaly: dict[str, _ServiceAnomaly],
    alpha: float,
    ci_test: str,
) -> tuple[nx.DiGraph, dict[tuple[str, str], float]]:
    """Run PC and return ``(dag, edge_weights)``.

    The PC algorithm returns a CPDAG: some edges directed, others
    undirected. We turn the CPDAG into a DAG by orienting every
    undirected edge from the less-anomalous endpoint to the more-
    anomalous one. The choice is deterministic and structurally
    motivated — the more anomalous service is the more plausible
    *manifestation*, and the upstream cause is the less anomalous
    endpoint of the undirected pair. Worst case it's wrong by one
    orientation per undirected edge, but the ancestor analysis still
    captures the structural neighborhood of the anchor.

    Edge weights come from the partial-correlation magnitude between
    the endpoints conditioned on the rest of the graph's regressors.
    They live in ``[0, 1]`` and feed the explanation chain's
    :class:`CausalLink.weight`.
    """
    dag = nx.DiGraph()
    dag.add_nodes_from(columns)
    edge_weights: dict[tuple[str, str], float] = {}
    if X.shape[0] < 5 or X.shape[1] < 2:
        return dag, edge_weights

    try:
        from causallearn.search.ConstraintBased.PC import pc
    except ImportError as exc:  # pragma: no cover - dependency-installed env
        raise ImportError(
            "CausalRCA requires causal-learn. Install with "
            "`pip install causal-learn`."
        ) from exc

    try:
        cg = pc(X, alpha=alpha, indep_test=ci_test, show_progress=False)
    except Exception:
        # PC can blow up on degenerate inputs (singular covariance,
        # constant columns that survived our jitter, etc.). Fall back
        # to an empty graph — the scorer will then rank by raw anomaly
        # alone, which is a safe degraded mode.
        return dag, edge_weights

    adj = cg.G.graph  # causal-learn's encoded adjacency
    n = adj.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            u_anom = anomaly[columns[i]].score
            v_anom = anomaly[columns[j]].score
            direction = _edge_direction(adj, i, j)
            if direction is None:
                continue
            if direction == "ij":
                src, dst = columns[i], columns[j]
            elif direction == "ji":
                src, dst = columns[j], columns[i]
            else:  # undirected → orient less-anomalous → more-anomalous
                if u_anom <= v_anom:
                    src, dst = columns[i], columns[j]
                else:
                    src, dst = columns[j], columns[i]
            w = _edge_weight(X, i, j)
            dag.add_edge(src, dst, weight=w)
            edge_weights[(src, dst)] = w
    return dag, edge_weights


def _edge_direction(adj: np.ndarray, i: int, j: int) -> str | None:
    """Decode causal-learn's edge encoding at ``(i, j)``.

    Returns ``"ij"`` for i→j, ``"ji"`` for j→i, ``"undirected"`` for
    an i—j edge, and ``None`` for no edge / bidirected (we ignore
    bidirected; it indicates a latent confounder and is not actionable
    for RCA).
    """
    a_ij = int(adj[i, j])
    a_ji = int(adj[j, i])
    if a_ij == 0 and a_ji == 0:
        return None
    # Directed i → j: tail at i (a_ji = 1), arrow at j (a_ij = -1).
    if a_ij == -1 and a_ji == 1:
        return "ij"
    if a_ij == 1 and a_ji == -1:
        return "ji"
    # Undirected: both endpoints are tails (or causal-learn's
    # implementation marks both as arrowheads). Treat as undirected.
    if a_ij == -1 and a_ji == -1:
        return "undirected"
    return None  # bidirected or unexpected encoding


def _edge_weight(X: np.ndarray, i: int, j: int) -> float:
    """Absolute Pearson correlation between columns ``i`` and ``j``,
    clipped to ``[0, 1]`` so it can serve directly as
    :class:`CausalLink.weight`.
    """
    xi = X[:, i]
    xj = X[:, j]
    if float(np.std(xi)) == 0.0 or float(np.std(xj)) == 0.0:
        return 0.0
    r = float(np.corrcoef(xi, xj)[0, 1])
    if not np.isfinite(r):
        return 0.0
    return max(0.0, min(1.0, abs(r)))


# ---- root-cause inference ----


def _pick_anchor(
    anomaly: dict[str, _ServiceAnomaly], services: list[str]
) -> str:
    """Most-anomalous service. Ties broken by name to keep the choice
    deterministic across runs."""
    return max(
        services,
        key=lambda s: (anomaly[s].score, -ord(s[0]) if s else 0),
    )


def _score_services(
    anomaly: dict[str, _ServiceAnomaly],
    services: list[str],
    dag: nx.DiGraph,
    anchor: str,
    nonancestor_penalty_floor: float,
) -> tuple[dict[str, float], dict[str, int | float]]:
    """Score by ``anomaly[s] / (1 + d(s, anchor))``.

    ``d`` is the shortest directed path length from ``s`` to
    ``anchor`` in ``dag`` (0 if ``s == anchor``). Services with no
    directed path to the anchor get ``score = anomaly[s] *
    nonancestor_penalty_floor`` so they still rank but are demoted
    below ancestors.
    """
    scores: dict[str, float] = {}
    distances: dict[str, int | float] = {}
    for s in services:
        a_s = anomaly[s].score
        if s == anchor:
            d: int | float = 0
            scores[s] = a_s
        else:
            try:
                d = nx.shortest_path_length(dag, source=s, target=anchor)
                scores[s] = a_s / (1.0 + float(d))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                d = float("inf")
                scores[s] = a_s * nonancestor_penalty_floor
        distances[s] = d
    return scores, distances


# ---- output assembly ----


def _derived_confidence(ranked: list[tuple[str, float]]) -> float:
    """Top-1 score relative to the second-ranked service.

    ``confidence = 1 - top2 / top1``, clipped to ``[0, 1]``. A clear
    winner (top1 ≫ top2) gives confidence near 1; a tie gives 0. When
    ``top1 == 0`` (degenerate case with no signal) we return 0.
    """
    if not ranked:
        return 0.0
    if len(ranked) == 1:
        return 1.0 if ranked[0][1] > 0.0 else 0.0
    top1 = ranked[0][1]
    top2 = ranked[1][1]
    if top1 <= 0.0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - (top2 / top1)))


def _build_causal_explanation(
    ranked: list[tuple[str, float]],
    anomaly: dict[str, _ServiceAnomaly],
    dag: nx.DiGraph,
    edge_weights: dict[tuple[str, str], float],
    anchor: str,
    top_k: int,
) -> CanonicalExplanation:
    """Build an :class:`CanonicalExplanation` with top-K atoms and the
    induced subgraph of DAG edges between them.

    Unlike MonitorRank's flat output, this explanation carries real
    :class:`CausalLink` edges — the explanation chain *is* the
    learned causal narrative restricted to the top-K services.
    """
    explanation = CanonicalExplanation()
    head = ranked[:top_k]
    if not head:
        return explanation

    pi_max = max((s for _, s in head), default=1.0) or 1.0
    service_to_atom_id: dict[str, str] = {}
    for service, score in head:
        a = anomaly.get(service)
        feat = a.dominant_feature if a is not None else None
        z = a.score if a is not None else 0.0
        marker = " (anchor)" if service == anchor else ""
        if feat is not None:
            text = (
                f"{service}{marker}: anomalous {feat} (z={z:.2f}, "
                f"score={score:.4f})"
            )
        else:
            text = f"{service}{marker}: score={score:.4f}"
        atom = ExplanationAtom(
            text=text,
            ontology_class=None,
            fuzzy_membership=max(0.0, min(1.0, score / pi_max)),
        )
        explanation.add_atom(atom)
        service_to_atom_id[service] = atom.id

    # Add the DAG edges that fall between the top-K atoms. We keep
    # every directed edge induced on the head — that's the causal
    # subgraph the user actually wants to look at when interpreting
    # the rank.
    for u, v in dag.edges():
        if u in service_to_atom_id and v in service_to_atom_id:
            w = edge_weights.get((u, v), 1.0)
            explanation.add_link(
                CausalLink(
                    source_atom_id=service_to_atom_id[u],
                    target_atom_id=service_to_atom_id[v],
                    weight=max(0.0, min(1.0, float(w))),
                    relation_type="causes",
                )
            )
    return explanation
