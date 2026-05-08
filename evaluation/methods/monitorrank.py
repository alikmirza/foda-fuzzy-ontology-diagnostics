"""MonitorRank baseline (Kim, Sumbaly, Shah; SIGMETRICS 2013).

Clean reimplementation of the random-walk-on-the-call-graph algorithm
described in Section 5.3 of *Root Cause Detection in a Service-Oriented
Architecture*. The implementation follows the paper directly (no
wrapping of an upstream library): build the augmented adjacency
A' (Eq. 6), row-normalize to a transition matrix P (Eq. 7), iterate
the Personalized PageRank update π ← α π P + (1 - α) u (Eq. 8) until
convergence, and rank services by π.

Validation status
-----------------

This implementation is **pending validation against real RCAEval
data**. RCAEval itself does not include MonitorRank in its published
baselines, so there is no exact AC@1 number to reproduce; the
nearest reference points are MicroCause and MicroRank (also
random-walk-style). Run
``python -m evaluation.experiments.evaluate_monitorrank --data ...``
once the RCAEval archive is extracted, and update this note with the
observed AC@1 by fault type.

Pseudo-code::

    # 1. Per-service pattern similarity vs. the frontend
    S[i] = max |pearson_corr(metric_a_of_service_i, metric_b_of_frontend)|

    # 2. Augmented adjacency A' on the service-call graph
    A'[i][j] = S[j]                                if (i → j) ∈ E
    A'[i][j] = ρ * S[i]                            if (j → i) ∈ E and (i → j) ∉ E
    A'[i][i] = max(0, S[i] - max_{(i → k) ∈ E} S[k])  for i ≠ frontend

    # 3. Row-normalize → transition matrix P
    P[i][j] = A'[i][j] / Σ_j A'[i][j]

    # 4. Personalization vector u (the teleport distribution)
    u[i] = S[i] for i ≠ frontend, u[frontend] = 0; renormalize.

    # 5. PPR iteration to fixed point
    π ← α π P + (1 - α) u

    # 6. Rank services by π (excluding the frontend itself)

Deviations from the paper
-------------------------

* **Pseudo-anomaly clustering** (Section 5.2) is not implemented. That
  is the offline external-factor component; this class implements only
  the real-time random-walk core, which the paper's own ablation
  (Figure 6, PS+RW vs. PS+PAC) shows carries the bulk of the lift.

* **Pattern similarity**: paper averages a sliding-window correlation
  (Section 6.1, 60-minute window). We use a single Pearson correlation
  over the whole anomaly window. This drops one hyperparameter and
  makes the method deterministic; on a well-defined anomaly window the
  two are nearly identical.

* **Multi-metric services**: the paper assumes one metric per sensor
  (sensor = ⟨service, API⟩ tuple). Our cases carry several metrics per
  service (cpu, mem, latency, ...). We score a service v_i against the
  frontend by the **max |corr|** over all (service-metric,
  frontend-metric) column pairs, which reduces gracefully to the paper
  formula when each side has one metric.

* **Frontend auto-detection**: the paper takes the frontend as a user
  input (it's where the anomaly was reported). When `frontend_service`
  is not passed and `BenchmarkCase` carries no marker, we name-match
  against a small list of common frontend identifiers, then fall back
  to the service with the largest anomaly magnitude.

* **Topology direction**: Section 6.1 reverses the call graph for
  latency / error metrics so that the walker's "downstream" matches
  fault-propagation. We trust whatever direction the caller passes via
  `BenchmarkCase.system_topology`. When no topology is given we use a
  fully-connected directed graph as a fallback, which makes ρ moot
  and reduces the algorithm to weighted PPR over the similarity vector.

* **Top-level frontend self-loop**: Eq. 6 explicitly excludes a
  self-edge on the frontend (`j = i > 1`). We do the same.
"""

from __future__ import annotations

import time
from collections.abc import Mapping

import networkx as nx
import numpy as np
import pandas as pd

from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
    ExplanationAtom,
)
from .base import RCAMethod


_FRONTEND_NAME_HINTS: tuple[str, ...] = (
    "frontend",
    "front-end",
    "front_end",
    "frontend-service",
    "fe",
    "web",
    "webui",
    "ts-ui-dashboard",
)

_TIME_COLUMN_HINTS: frozenset[str] = frozenset({"time", "timestamp", "ts", "t"})


class MonitorRankMethod(RCAMethod):
    """MonitorRank random-walk root-cause method.

    Parameters
    ----------
    alpha:
        Random-walk continuation probability in (0, 1). The paper sets
        this higher when the call graph is trusted as a true dependency
        graph; we default to 0.85, which is the canonical PageRank
        value and matches what most modern RCA papers use for
        MonitorRank baselines.
    rho:
        Backward-edge weight ρ ∈ [0, 1). Lower ρ lets the walker
        explore more freely against the call direction. Default 0.5.
    top_k:
        Size of the top-K head used for the explanation chain and for
        the derived confidence (top-1 / sum of top-K). Default 5.
    frontend_service:
        Optional name of the frontend / anomaly-seed service. If
        ``None``, auto-detected (see module docstring).
    max_iter, tol:
        Iteration controls for the PPR fixed point.
    """

    name = "monitorrank"

    def __init__(
        self,
        alpha: float = 0.85,
        rho: float = 0.5,
        top_k: int = 5,
        frontend_service: str | None = None,
        max_iter: int = 100,
        tol: float = 1e-8,
    ) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if not (0.0 <= rho < 1.0):
            raise ValueError(f"rho must be in [0, 1), got {rho}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        self.alpha = alpha
        self.rho = rho
        self.top_k = top_k
        self.frontend_service = frontend_service
        self.max_iter = max_iter
        self.tol = tol

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        t0 = time.perf_counter()

        per_service = _extract_per_service_metrics(_metrics_field(case))
        if not per_service:
            raise ValueError(
                f"MonitorRank: case {case.id!r} has no recognizable "
                f"per-service metrics in telemetry['metrics']"
            )
        services = sorted(per_service.keys())
        frontend = self._pick_frontend(services, per_service)
        sim = _pattern_similarity(services, per_service, frontend)
        graph = _build_graph(services, case.system_topology)
        scores = _monitorrank_random_walk(
            services=services,
            frontend=frontend,
            sim=sim,
            graph=graph,
            alpha=self.alpha,
            rho=self.rho,
            max_iter=self.max_iter,
            tol=self.tol,
        )

        # Paper convention: the frontend is the anomaly seed, not a
        # candidate root cause (u_frontend = 0). Drop it from the rank.
        ranked = sorted(
            ((s, float(scores[s])) for s in services if s != frontend),
            key=lambda kv: kv[1],
            reverse=True,
        )
        confidence = _derived_confidence(ranked, self.top_k)
        explanation = _build_explanation(ranked, self.top_k)

        wall_ms = (time.perf_counter() - t0) * 1000.0
        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=dict(scores),
            method_name=self.name,
            wall_time_ms=wall_ms,
        )

    # ---- internals ----

    def _pick_frontend(
        self,
        services: list[str],
        per_service: dict[str, pd.DataFrame],
    ) -> str:
        if self.frontend_service is not None:
            if self.frontend_service not in services:
                raise ValueError(
                    f"MonitorRank: frontend_service "
                    f"{self.frontend_service!r} is not in the case's "
                    f"services {services!r}"
                )
            return self.frontend_service
        lowered = {s.lower(): s for s in services}
        for hint in _FRONTEND_NAME_HINTS:
            if hint in lowered:
                return lowered[hint]
        # No name match — fall back to the noisiest service so at least
        # the algorithm has a well-defined seed.
        return max(
            services,
            key=lambda s: _service_anomaly_magnitude(per_service[s]),
        )


# ---- telemetry plumbing ----


def _metrics_field(case: BenchmarkCase) -> object:
    """Pull ``telemetry['metrics']`` out of a BenchmarkCase, or fail loudly."""
    telem = case.telemetry
    if isinstance(telem, Mapping) and "metrics" in telem:
        return telem["metrics"]
    raise ValueError(
        f"MonitorRank: case {case.id!r} telemetry is missing a "
        f"'metrics' field (got {type(telem).__name__})"
    )


def _extract_per_service_metrics(metrics: object) -> dict[str, pd.DataFrame]:
    """Normalize ``telemetry['metrics']`` to ``{service: DataFrame}``.

    Two on-disk shapes appear in our benchmarks:

    * ``dict[str, DataFrame]`` (FODA-12) — keys are service names.
    * ``DataFrame`` with columns ``<service>_<metric>`` (RCAEval /
      Online Boutique). We split on the *last* underscore so that
      services with hyphens (``front-end``, ``ts-ui-dashboard``) work,
      but service names containing literal underscores will be
      mis-split. RCAEval cases use hyphenated service names, so this
      heuristic suffices in practice.
    """
    if isinstance(metrics, Mapping):
        return {
            str(k): v
            for k, v in metrics.items()
            if isinstance(v, pd.DataFrame)
        }
    if isinstance(metrics, pd.DataFrame):
        return _split_flat_dataframe(metrics)
    raise TypeError(
        f"telemetry['metrics'] must be a dict[str, DataFrame] or a "
        f"DataFrame, got {type(metrics).__name__}"
    )


def _split_flat_dataframe(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    by_service: dict[str, dict[str, pd.Series]] = {}
    for col in df.columns:
        if str(col).lower() in _TIME_COLUMN_HINTS:
            continue
        if "_" not in str(col):
            continue
        service, metric = str(col).rsplit("_", 1)
        by_service.setdefault(service, {})[metric] = df[col]
    return {svc: pd.DataFrame(cols) for svc, cols in by_service.items()}


def _service_anomaly_magnitude(df: pd.DataFrame) -> float:
    """Tie-breaker score for picking a frontend when no name matches.

    Returns the max coefficient-of-variation across the service's
    metric columns — "the noisiest service" wins. Pure heuristic; only
    used when name-matching fails.
    """
    out = 0.0
    for col in df.columns:
        x = df[col].astype(float).to_numpy()
        x = x[~np.isnan(x)]
        if x.size < 2:
            continue
        mu = float(np.mean(np.abs(x)))
        sd = float(np.std(x))
        out = max(out, sd / mu if mu > 0 else sd)
    return out


# ---- pattern similarity ----


def _pattern_similarity(
    services: list[str],
    per_service: dict[str, pd.DataFrame],
    frontend: str,
) -> dict[str, float]:
    """S_i = max |Pearson(m_i^a, m_fe^b)| across metric column pairs.

    Returned values lie in [0, 1]. The frontend gets S_frontend = 1.0;
    it is needed in adjacency rows but is excluded from the
    personalization vector (see the random-walk routine).
    """
    fe_df = per_service[frontend]
    sim: dict[str, float] = {}
    for s in services:
        if s == frontend:
            sim[s] = 1.0
            continue
        sim[s] = _max_abs_corr(per_service[s], fe_df)
    return sim


def _max_abs_corr(svc_df: pd.DataFrame, fe_df: pd.DataFrame) -> float:
    best = 0.0
    fe_cols = [
        (fc, fe_df[fc].astype(float).to_numpy()) for fc in fe_df.columns
    ]
    for sc in svc_df.columns:
        a = svc_df[sc].astype(float).to_numpy()
        for _, b in fe_cols:
            n = min(a.size, b.size)
            if n < 2:
                continue
            x, y = a[-n:], b[-n:]
            mask = ~(np.isnan(x) | np.isnan(y))
            if mask.sum() < 2:
                continue
            xm, ym = x[mask], y[mask]
            if xm.std() == 0 or ym.std() == 0:
                continue
            r = float(np.corrcoef(xm, ym)[0, 1])
            if not np.isnan(r):
                best = max(best, abs(r))
    return best


# ---- topology graph ----


def _build_graph(services: list[str], topology: object) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_nodes_from(services)
    if topology is None:
        # Fully-connected fallback: u → v for every u ≠ v. This makes
        # backward edges vacuous (forward edges already cover every
        # pair) and turns the algorithm into similarity-weighted PPR.
        for u in services:
            for v in services:
                if u != v:
                    g.add_edge(u, v)
        return g
    if isinstance(topology, nx.DiGraph):
        for u, v in topology.edges():
            if u in g and v in g:
                g.add_edge(u, v)
        return g
    if isinstance(topology, Mapping):
        for u, neighbors in topology.items():
            if u not in g:
                continue
            for v in neighbors or []:
                if v in g:
                    g.add_edge(u, v)
        return g
    raise TypeError(
        f"system_topology must be a dict[str, list[str]], a DiGraph, "
        f"or None — got {type(topology).__name__}"
    )


# ---- random walk ----


def _monitorrank_random_walk(
    services: list[str],
    frontend: str,
    sim: dict[str, float],
    graph: nx.DiGraph,
    alpha: float,
    rho: float,
    max_iter: int,
    tol: float,
) -> dict[str, float]:
    n = len(services)
    idx = {s: i for i, s in enumerate(services)}
    fe_idx = idx[frontend]

    # Eq. 6: build A' on G with forward, backward, and self edges.
    A = np.zeros((n, n), dtype=float)
    for i, u in enumerate(services):
        max_child_sim = 0.0
        for v in graph.successors(u):
            j = idx[v]
            A[i, j] = sim[v]                 # forward edge
            if sim[v] > max_child_sim:
                max_child_sim = sim[v]
        for v in graph.predecessors(u):
            if not graph.has_edge(u, v):
                A[i, idx[v]] = rho * sim[u]  # backward edge
        if i != fe_idx:
            A[i, i] = max(0.0, sim[u] - max_child_sim)  # self edge

    # Eq. 7: row-normalize to a transition matrix.
    P = np.zeros_like(A)
    row_sums = A.sum(axis=1)
    for i in range(n):
        if row_sums[i] > 0:
            P[i] = A[i] / row_sums[i]
        else:
            # Stuck row (all zeros): jump uniformly to other nodes so
            # the chain stays ergodic and PageRank mass conserves.
            mask = np.ones(n, dtype=float)
            mask[i] = 0.0
            P[i] = mask / max(1, n - 1)

    # Personalization vector u: u_i = S_i for i ≠ fe, u_fe = 0; renormalize.
    u = np.array([sim[s] for s in services], dtype=float)
    u[fe_idx] = 0.0
    if u.sum() <= 0:
        # Degenerate: no anomaly signal. Spread teleports uniformly
        # over non-frontend nodes so we still get a meaningful rank.
        u = np.ones(n, dtype=float)
        u[fe_idx] = 0.0
    u = u / u.sum()

    # Eq. 8: π ← α π P + (1 - α) u.
    pi = u.copy()
    for _ in range(max_iter):
        nxt = alpha * (pi @ P) + (1.0 - alpha) * u
        if np.linalg.norm(nxt - pi, ord=1) < tol:
            pi = nxt
            break
        pi = nxt

    return {services[i]: float(pi[i]) for i in range(n)}


# ---- output assembly ----


def _derived_confidence(
    ranked: list[tuple[str, float]], top_k: int
) -> float:
    """Top-1 / sum-of-top-K, clamped to [0, 1].

    Returns 1/k for a perfectly flat top-k (no signal) and 1.0 when
    the top entry dominates. 0.0 only if every score is non-positive
    (e.g. no anomaly was detected anywhere).
    """
    if not ranked:
        return 0.0
    head = ranked[:top_k]
    total = sum(s for _, s in head)
    if total <= 0:
        return 0.0
    return head[0][1] / total


def _build_explanation(
    ranked: list[tuple[str, float]], top_k: int
) -> CanonicalExplanation:
    explanation = CanonicalExplanation()
    head = ranked[:top_k]
    if not head:
        return explanation
    max_score = max(s for _, s in head) or 1.0
    for service, score in head:
        membership = max(0.0, min(1.0, score / max_score))
        explanation.add_atom(
            ExplanationAtom(
                text=f"{service} has anomaly score {score:.4f}",
                ontology_class=None,
                fuzzy_membership=membership,
            )
        )
    return explanation
