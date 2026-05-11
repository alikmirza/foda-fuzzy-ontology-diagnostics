"""MonitorRank (Kim, Sumbaly, Shah; KDD 2013), refactored to consume
:class:`evaluation.extraction.schema_normalizer.NormalizedCase`
under the inject_time-removal contract.

The pipeline is unchanged from the previous iteration except for one
load-bearing detail: the pre/post split for anomaly scoring no longer
reads ``inject_time``. Instead it asks the opt-in change-point
detector in :mod:`evaluation.methods._onset` to find the most likely
pivot from telemetry alone. Everything else (z-score personalization,
correlation-inferred call graph, PPR with damping 0.85 and 100 power
iterations, top-3 explanation atoms with dominant feature) is
identical.

Why this matters: the diagnostic that motivated the redesign showed
that shifting ``inject_time`` by ±300 s collapsed AC@1 to chance,
proving the algorithm was fenceposting on a side-channel value. With
onset detected from telemetry, the shift-evaluation protocol
(``evaluation/extraction/DESIGN_inject_time_removal.md`` §5) should
report ``S(M) ≈ 0`` — that's the invariant the next step's harness
will measure.

Deviations from the 2013 paper are recorded in ``DEVIATIONS.md``.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
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


@dataclass
class _ServiceAnomaly:
    score: float = 0.0
    dominant_feature: str | None = None
    per_feature: dict[str, float] = field(default_factory=dict)


class MonitorRankMethod(RCAMethod):
    """MonitorRank random-walk root-cause method on :class:`NormalizedCase`.

    Parameters
    ----------
    alpha:
        PPR damping factor in ``(0, 1)``. Paper-default 0.85.
    n_iters:
        Power iterations for the PPR update. 100 per the paper, fixed
        for determinism.
    top_k:
        Size of the head used for ``confidence = π_top1 / Σ π_topK``.
    frontend_service:
        Entry-point service to exclude from the rank (also gets zero
        personalization mass). ``None`` triggers name-hint
        auto-detection; if no hint matches no service is excluded.
    corr_threshold:
        ``|Pearson|`` cutoff for adding an edge in the inferred call
        graph.
    window_seconds:
        Total window length passed to ``normalize_case``.
    """

    name = "monitorrank"

    def __init__(
        self,
        alpha: float = 0.85,
        n_iters: int = 100,
        top_k: int = 5,
        frontend_service: str | None = None,
        corr_threshold: float = 0.3,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        if n_iters < 1:
            raise ValueError(f"n_iters must be >= 1, got {n_iters}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if not 0.0 <= corr_threshold <= 1.0:
            raise ValueError(
                f"corr_threshold must be in [0, 1], got {corr_threshold}"
            )
        if window_seconds <= 0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        self.alpha = alpha
        self.n_iters = n_iters
        self.top_k = top_k
        self.frontend_service = frontend_service
        self.corr_threshold = corr_threshold
        self.window_seconds = window_seconds

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Same as :meth:`diagnose` but takes a pre-built
        :class:`NormalizedCase`. The shift-evaluation harness calls
        this directly so it can pass a normalized case whose
        ``ground_truth`` has been deliberately shifted, while keeping
        ``case_window`` (the only thing this method actually reads)
        untouched.

        Methods that legitimately should not peek at ``ground_truth``
        are validated by
        :func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
        — this method's body is a witness that it is possible to do
        useful work without that field.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"MonitorRank: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        frontend = self._pick_frontend(norm)
        # Strategy A: detect onset from telemetry alone. This replaces
        # the previous ``norm.inject_time`` access — see DEVIATIONS.md.
        onset_t = detect_onset(norm.case_window, norm.services)

        anomaly = _compute_anomaly(norm, onset_t)
        graph = _infer_call_graph(norm, frontend, self.corr_threshold)
        scores = _personalized_pagerank(
            graph=graph,
            services=norm.services,
            personalization=_personalization_vector(anomaly, frontend),
            alpha=self.alpha,
            n_iters=self.n_iters,
        )

        ranked = sorted(
            ((s, scores[s]) for s in norm.services if s != frontend),
            key=lambda kv: kv[1],
            reverse=True,
        )
        confidence = _derived_confidence(ranked, self.top_k)
        explanation = _build_explanation(ranked, anomaly, top_n=3)

        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=dict(scores),
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )

    # ---- internals ----

    def _pick_frontend(self, norm: NormalizedCase) -> str | None:
        if self.frontend_service is not None:
            if self.frontend_service not in norm.services:
                raise ValueError(
                    f"MonitorRank: frontend_service "
                    f"{self.frontend_service!r} is not in the case's "
                    f"services {norm.services!r}"
                )
            return self.frontend_service
        lowered = {s.lower(): s for s in norm.services}
        for hint in _FRONTEND_NAME_HINTS:
            if hint in lowered:
                return lowered[hint]
        return None


# ---- anomaly scoring ----


def _compute_anomaly(
    norm: NormalizedCase, onset_time: float
) -> dict[str, _ServiceAnomaly]:
    """Z-score of post-onset vs. pre-onset, max across canonical features.

    ``onset_time`` comes from :func:`evaluation.methods._onset.detect_onset`
    — it is **not** ``norm.ground_truth.inject_time``. That side
    channel is invisible to this function.
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
            x_pre = df.loc[pre_mask, col].to_numpy(dtype=float)
            x_post = df.loc[post_mask, col].to_numpy(dtype=float)
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
        out[svc] = a
    return out


def _personalization_vector(
    anomaly: Mapping[str, _ServiceAnomaly], frontend: str | None
) -> dict[str, float]:
    raw = {s: a.score for s, a in anomaly.items()}
    if frontend in raw:
        raw[frontend] = 0.0
    total = sum(raw.values())
    if total <= 0:
        candidates = [s for s in raw if s != frontend]
        if not candidates:
            return {s: 1.0 / len(raw) for s in raw}
        share = 1.0 / len(candidates)
        return {s: (0.0 if s == frontend else share) for s in raw}
    return {s: raw[s] / total for s in raw}


# ---- graph inference ----


def _infer_call_graph(
    norm: NormalizedCase, frontend: str | None, threshold: float
) -> nx.DiGraph:
    df = norm.case_window
    services = norm.services
    g = nx.DiGraph()
    g.add_nodes_from(services)

    signal: dict[str, np.ndarray] = {}
    for svc in services:
        s = _pick_signal(df, svc)
        if s is not None:
            signal[svc] = s

    for i, u in enumerate(services):
        for j in range(i + 1, len(services)):
            v = services[j]
            su, sv = signal.get(u), signal.get(v)
            if su is None or sv is None:
                continue
            if float(np.nanstd(su)) == 0.0 or float(np.nanstd(sv)) == 0.0:
                continue
            r = float(np.corrcoef(su, sv)[0, 1])
            if not np.isfinite(r):
                continue
            if abs(r) >= threshold:
                w = abs(r)
                g.add_edge(u, v, weight=w)
                g.add_edge(v, u, weight=w)

    if frontend in services:
        und = g.to_undirected()
        for s in services:
            if s == frontend:
                continue
            if not nx.has_path(und, frontend, s):
                g.add_edge(frontend, s, weight=threshold)
                g.add_edge(s, frontend, weight=threshold)
    return g


def _pick_signal(df, svc: str):
    for feat in ("traffic", "latency", "cpu", "mem", "error"):
        col = f"{svc}_{feat}"
        if col in df.columns:
            return df[col].to_numpy(dtype=float)
    return None


# ---- personalized PageRank ----


def _personalized_pagerank(
    graph: nx.DiGraph,
    services: list[str],
    personalization: Mapping[str, float],
    alpha: float,
    n_iters: int,
) -> dict[str, float]:
    n = len(services)
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
            P[i] = np.full(n, 1.0 / n if n > 0 else 0.0)

    p = np.array([personalization.get(s, 0.0) for s in services], dtype=float)
    s_total = p.sum()
    if s_total <= 0:
        p = np.full(n, 1.0 / n) if n > 0 else p
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
    if not ranked:
        return 0.0
    head = ranked[:top_k]
    total = sum(s for _, s in head)
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, head[0][1] / total))


def _build_explanation(
    ranked: list[tuple[str, float]],
    anomaly: Mapping[str, _ServiceAnomaly],
    top_n: int = 3,
) -> CanonicalExplanation:
    explanation = CanonicalExplanation()
    head = ranked[:top_n]
    if not head:
        return explanation
    pi_max = max(s for _, s in head) or 1.0
    for service, score in head:
        a = anomaly.get(service)
        feat = a.dominant_feature if a is not None else None
        z = a.score if a is not None else 0.0
        if feat is not None:
            text = f"{service}: anomalous {feat} (z={z:.2f}, π={score:.4f})"
        else:
            text = f"{service}: π={score:.4f}"
        explanation.add_atom(
            ExplanationAtom(
                text=text,
                ontology_class=None,
                fuzzy_membership=max(0.0, min(1.0, score / pi_max)),
            )
        )
    return explanation
