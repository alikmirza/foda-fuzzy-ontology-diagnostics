"""FODA-FCP (Fuzzy Contribution Propagation) — the dissertation's
centerpiece method, ported from the Java reference in
``fuzzy-rca-engine`` to the inject_time-clean
:class:`NormalizedCase` contract.

The five-phase pipeline mirrors
``fuzzy-rca-engine/src/main/java/com/foda/rca/core/FuzzyRcaEngineImpl.java``:

1. **Fuzzification.** Per-service canonical-feature post-vs-pre
   z-scores are mapped onto LOW / MEDIUM / HIGH (CPU, memory), NORMAL
   / ELEVATED / CRITICAL (latency), NONE / LOW / ELEVATED / HIGH
   (errorRate), LOW / NORMAL (throughput) via trapezoidal / triangular
   membership functions. The Java reference uses crisp SLO thresholds
   (e.g. ``cpu > 65 % ⇒ HIGH``); we substitute z-magnitudes against
   the pre-onset baseline because (a) the canonical schema is unit-
   agnostic and (b) the AICT paper's thresholds were calibrated for a
   different telemetry pipeline. The membership-function shape and
   the **interpretation** of LOW / MEDIUM / HIGH are preserved.
   Documented in DEVIATIONS.md → "FODA-FCP adapter".

2. **Mamdani fault inference.** The 16-rule expert rule base from
   ``MamdaniFuzzyRuleEngine.buildDefaultRuleBase()`` is ported
   verbatim (rule labels, antecedents, certainty factors). For each
   service we compute per-rule firing strengths ``α = CF × min{μ}``
   and aggregate per fault category via ``max``. The dominant
   category's strength is the service's local confidence ``H(s)``.

3. **Damped Noisy-OR confidence propagation.** Equation 4 from the
   AICT paper, ported faithfully::

       P(s) = 1 − ∏_{t ∈ callees(s)} (1 − C(t) · w(s,t) · δ)
       C(s) = 1 − (1 − H(s)) · (1 − P(s))

   with δ = 0.85 by default. The service dependency graph is
   inferred from lagged Pearson correlation between services'
   dominant-anomaly features (same convention as MicroRCA / yRCA;
   documented in DEVIATIONS.md) because RCAEval RE1-OB ships no
   topology metadata. Cyclic graphs fall back to a Jacobi iteration
   to fixed point (Eq. 5).

4. **Top-K ranking.** Services sorted by final confidence ``C(s)``
   in descending order; ties broken by ``H(s)`` then by service
   name (deterministic).

5. **Ontology-grounded explanation.** This is the part FODA-FCP
   uniquely contributes. The CanonicalExplanation captures the full
   FCP reasoning chain in a form Paper 6's SemanticGroundedness
   metrics can inspect:

   * One :class:`ExplanationAtom` per service in the top-K, tagged
     with its predicted ContributingFactor / Fault ontology class
     (full URI, e.g. ``http://foda.com/ontology/diagnostic#CpuSaturation``)
     pulled from ``ontology/DiagnosticKB.owl`` via the same vocabulary
     map ``OntologyGroundedExplanationBuilder.CATEGORY_TO_FAULT_LOCAL_NAME``
     uses on the Java side.
   * One additional Recommendation atom for the predicted root cause
     (e.g. ``http://foda.com/ontology/diagnostic#Rec_CpuSaturation``)
     with the same fuzzy membership as the root atom.
   * :class:`CausalLink` edges:

     - ``relation_type="suggests_mitigation"`` from every
       ContributingFactor atom to the Recommendation atom, weighted
       by that atom's fuzzy membership.
     - ``relation_type="contributes_to"`` from every non-root
       ContributingFactor atom to the root atom, weighted by the FCP
       propagation contribution ``C(t) · w(root,t) · δ``.
     - Each link's ``rule_id`` (encoded in the relation_type suffix
       after a colon) documents the FCP sub-process that derived it:
       ``mamdani:R03`` for Mamdani-fired rules,
       ``propagation:noisy_or`` for propagation contributions, and
       ``recommendation:fault_prototype`` for mitigation suggestions.

Confidence is computed as ``top1_C / sum(C over top-K)`` — the
relative concentration of fuzzy contribution mass on the top-1
service. Documented as the FODA-FCP adapter's choice (the Java
reference reports the absolute ``finalConfidence`` of the top-1
RankedCause; we normalize to ``[0, 1]`` for cross-method
comparability with the harness's per-method confidence column).

Deviations from the AICT 2026 paper live in DEVIATIONS.md under
"FODA-FCP adapter".
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass

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


# ---- ontology vocabulary ---------------------------------------------------

#: ``DiagnosticKB.owl`` namespace. Atoms emit full URIs so the Paper 6
#: SemanticGroundedness metrics can join them to the OWL graph.
ONTOLOGY_NS: str = "http://foda.com/ontology/diagnostic#"

#: Mamdani fault category → DiagnosticKB fault-prototype local name.
#: Mirrors :class:`OntologyGroundedExplanationBuilder.CATEGORY_TO_FAULT_LOCAL_NAME`
#: in ``fuzzy-rca-engine`` so the Python adapter agrees with the Java
#: reference's vocabulary mapping. CASCADING_FAILURE has no dedicated
#: ontology counterpart; the Java reference maps it to
#: ``ResourceContention``, and we follow that convention.
CATEGORY_TO_FAULT: dict[str, str] = {
    "CPU_SATURATION":     "CpuSaturation",
    "MEMORY_PRESSURE":    "MemoryLeak",
    "SERVICE_ERROR":      "HighErrorRate",
    "LATENCY_ANOMALY":    "LatencySpike",
    "RESOURCE_CONTENTION": "ResourceContention",
    "CASCADING_FAILURE":  "ResourceContention",
}

#: Highest-membership fuzzy term → DiagnosticKB fault-prototype local
#: name. Used as a soft fallback for atoms whose Mamdani dominant
#: category is ``UNKNOWN`` (no rule fired, but the service still has
#: appreciable fuzzy signal): instead of tagging them with the abstract
#: ``ContributingFactor`` class — which the propagation table has no
#: opinion about and which therefore drags SemanticCoherence down —
#: we map the strongest term to the fault prototype it points at.
#: This keeps the semantic intent (a service whose memory term is
#: elevated **looks like** a MemoryLeak contributor, even though it
#: didn't fire enough corroborating signal for a full rule) while
#: preserving the fault-prototype contract that SC scores against.
_TERM_TO_FAULT_PROTOTYPE: dict[str, str] = {
    "cpu_HIGH":          "CpuSaturation",
    "cpu_MEDIUM":        "CpuSaturation",
    "memory_HIGH":       "MemoryLeak",
    "memory_MEDIUM":     "MemoryLeak",
    "latency_CRITICAL":  "LatencySpike",
    "latency_ELEVATED":  "LatencySpike",
    "errorRate_HIGH":    "HighErrorRate",
    "errorRate_ELEVATED": "HighErrorRate",
    "throughput_LOW":    "ThroughputDegradation",
}

#: Membership floor below which we don't infer a fault prototype.
#: Anything weaker is genuine noise and stays unmapped (atoms get the
#: abstract ContributingFactor class and SC counts them as out-of-scope
#: links rather than incoherent ones).
_FALLBACK_MEMBERSHIP_FLOOR: float = 0.20


def _infer_fault_prototype_from_fuzzy(
    fv: _ServiceFuzzyVector,
) -> str | None:
    """Pick the highest-membership term among
    :data:`_TERM_TO_FAULT_PROTOTYPE`'s keys, and return its fault
    prototype local name (e.g. ``"CpuSaturation"``). Returns ``None``
    if no term clears :data:`_FALLBACK_MEMBERSHIP_FLOOR` — in that
    case the service has nothing to say about which fault prototype
    it contributes to.
    """
    best_term: str | None = None
    best_mu = _FALLBACK_MEMBERSHIP_FLOOR
    for term, _fault in _TERM_TO_FAULT_PROTOTYPE.items():
        mu = fv.memberships.get(term, 0.0)
        if mu > best_mu:
            best_mu = mu
            best_term = term
    if best_term is None:
        return None
    return _TERM_TO_FAULT_PROTOTYPE[best_term]


#: Fault prototype → its ``Rec_*`` Recommendation individual in
#: ``DiagnosticKB.owl``. Lifted from the ``hasRecommendation`` object
#: properties on each fault prototype individual.
FAULT_TO_RECOMMENDATION: dict[str, str] = {
    "CpuSaturation":      "Rec_CpuSaturation",
    "MemoryLeak":         "Rec_MemoryLeak",
    "LatencySpike":       "Rec_LatencySpike",
    "HighErrorRate":      "Rec_HighErrorRate",
    "ResourceContention": "Rec_ResourceContention",
    "NetworkCongestion":  "Rec_NetworkCongestion",
    "ThroughputDegradation": "Rec_ThroughputDegradation",
    "DiskIoBottleneck":   "Rec_DiskIoBottleneck",
}


def _ontology_uri(local_name: str) -> str:
    return f"{ONTOLOGY_NS}{local_name}"


# ---- Mamdani rule base -----------------------------------------------------


@dataclass(frozen=True)
class _Rule:
    """One row of the Mamdani rule base.

    Faithful port of ``MamdaniFuzzyRuleEngine.buildDefaultRuleBase()``
    in ``fuzzy-rca-engine``. ``label`` is preserved so the explanation
    chain can name the rule that fired (Paper 6's case-study figure
    consumes this).
    """

    rule_id: str
    label: str
    antecedents: tuple[str, ...]
    consequent: str
    cf: float


#: The 16-rule expert base from the Java reference. Order preserved.
RULE_BASE: tuple[_Rule, ...] = (
    _Rule("R01", "IF cpu_HIGH AND latency_ELEVATED THEN CPU_SATURATION",
          ("cpu_HIGH", "latency_ELEVATED"), "CPU_SATURATION", 0.85),
    _Rule("R02", "IF cpu_HIGH AND throughput_LOW THEN CPU_SATURATION",
          ("cpu_HIGH", "throughput_LOW"), "CPU_SATURATION", 0.80),
    _Rule("R03", "IF cpu_HIGH AND latency_CRITICAL THEN CPU_SATURATION",
          ("cpu_HIGH", "latency_CRITICAL"), "CPU_SATURATION", 0.92),
    _Rule("R04", "IF memory_HIGH AND throughput_LOW THEN MEMORY_PRESSURE",
          ("memory_HIGH", "throughput_LOW"), "MEMORY_PRESSURE", 0.80),
    _Rule("R05", "IF memory_HIGH AND latency_ELEVATED THEN MEMORY_PRESSURE",
          ("memory_HIGH", "latency_ELEVATED"), "MEMORY_PRESSURE", 0.75),
    _Rule("R06", "IF memory_HIGH AND cpu_MEDIUM THEN MEMORY_PRESSURE",
          ("memory_HIGH", "cpu_MEDIUM"), "MEMORY_PRESSURE", 0.70),
    _Rule("R07", "IF errorRate_HIGH THEN SERVICE_ERROR",
          ("errorRate_HIGH",), "SERVICE_ERROR", 0.90),
    _Rule("R08", "IF errorRate_ELEVATED AND latency_ELEVATED THEN SERVICE_ERROR",
          ("errorRate_ELEVATED", "latency_ELEVATED"), "SERVICE_ERROR", 0.78),
    _Rule("R09", "IF errorRate_ELEVATED AND cpu_HIGH THEN SERVICE_ERROR",
          ("errorRate_ELEVATED", "cpu_HIGH"), "SERVICE_ERROR", 0.72),
    _Rule("R10", "IF latency_CRITICAL THEN LATENCY_ANOMALY",
          ("latency_CRITICAL",), "LATENCY_ANOMALY", 0.88),
    _Rule("R11", "IF latency_ELEVATED AND throughput_LOW THEN LATENCY_ANOMALY",
          ("latency_ELEVATED", "throughput_LOW"), "LATENCY_ANOMALY", 0.74),
    _Rule("R12", "IF cpu_HIGH AND errorRate_ELEVATED AND latency_ELEVATED THEN CASCADING_FAILURE",
          ("cpu_HIGH", "errorRate_ELEVATED", "latency_ELEVATED"),
          "CASCADING_FAILURE", 0.92),
    _Rule("R13", "IF memory_HIGH AND errorRate_HIGH THEN CASCADING_FAILURE",
          ("memory_HIGH", "errorRate_HIGH"), "CASCADING_FAILURE", 0.87),
    _Rule("R14", "IF cpu_HIGH AND memory_HIGH AND latency_CRITICAL THEN CASCADING_FAILURE",
          ("cpu_HIGH", "memory_HIGH", "latency_CRITICAL"),
          "CASCADING_FAILURE", 0.95),
    _Rule("R15", "IF cpu_HIGH AND memory_HIGH THEN RESOURCE_CONTENTION",
          ("cpu_HIGH", "memory_HIGH"), "RESOURCE_CONTENTION", 0.82),
    _Rule("R16", "IF cpu_MEDIUM AND memory_HIGH AND throughput_LOW THEN RESOURCE_CONTENTION",
          ("cpu_MEDIUM", "memory_HIGH", "throughput_LOW"),
          "RESOURCE_CONTENTION", 0.68),
)


# ---- z-score-driven fuzzy memberships --------------------------------------


def _trap(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal MF with shoulders at ``[a, b]`` and ``[c, d]``."""
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)


def _tri(x: float, a: float, b: float, c: float) -> float:
    """Triangular MF with peak at ``b``."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)


@dataclass(frozen=True)
class _ServiceFuzzyVector:
    """Per-service fuzzy memberships in the canonical Mamdani term set.

    Mirrors the structure that :class:`FuzzyVector` carries on the Java
    side (a ``Map<String, Double>`` of ``"<metric>_<TERM>"`` keys), but
    stored as named fields for clarity in the rule-firing code.
    """

    service: str
    memberships: dict[str, float]
    z_signed: dict[str, float]  # per-feature signed z-score, for diagnostics


def _zscore(
    case_window: pd.DataFrame,
    service: str,
    feature: str,
    onset_time: float,
) -> float:
    """Signed post-vs-pre z-score for ``{service}_{feature}``.

    ``0.0`` when the column is missing or the pre-onset slice has zero
    variance — the fuzzy-membership code interprets that as "no
    deviation from baseline", which is the correct semantic on a
    constant column.
    """
    col = f"{service}_{feature}"
    if col not in case_window.columns:
        return 0.0
    arr = case_window[col].to_numpy(dtype=float)
    times = case_window["time"].to_numpy(dtype=float)
    pre = arr[times < onset_time]
    post = arr[times >= onset_time]
    if pre.size < 2 or post.size < 1:
        return 0.0
    sd = float(pre.std())
    if sd == 0.0:
        return 0.0
    z = (float(post.mean()) - float(pre.mean())) / sd
    if not np.isfinite(z):
        return 0.0
    return z


def _fuzzify_service(
    case_window: pd.DataFrame,
    service: str,
    onset_time: float,
) -> _ServiceFuzzyVector:
    """Produce the ``cpu_HIGH``/``latency_ELEVATED``/… membership vector
    that the Mamdani rule base consumes.

    The Java fuzzifier uses SLO-calibrated crisp thresholds against raw
    metric values (``cpu > 65 % ⇒ HIGH``); we substitute z-magnitudes
    against the pre-onset baseline so the same membership-function
    shape applies regardless of telemetry units. See module docstring
    + DEVIATIONS.md for the rationale.
    """
    z = {
        feat: _zscore(case_window, service, feat, onset_time)
        for feat in ("cpu", "mem", "latency", "error", "traffic")
    }

    # CPU: |z| as the magnitude of "elevation" relative to baseline.
    cpu_mag = abs(z["cpu"])
    cpu_low    = _trap(cpu_mag, 0.0, 0.0, 0.5, 1.0)
    cpu_medium = _tri(cpu_mag, 0.5, 1.5, 3.0)
    cpu_high   = _trap(cpu_mag, 1.0, 3.0, 1e9, 1e9)

    # Memory: same shape (mem_LOW / MEDIUM / HIGH).
    mem_mag = abs(z["mem"])
    mem_low    = _trap(mem_mag, 0.0, 0.0, 0.5, 1.0)
    mem_medium = _tri(mem_mag, 0.5, 1.5, 3.0)
    mem_high   = _trap(mem_mag, 1.0, 3.0, 1e9, 1e9)

    # Latency: signed (only positive z is "elevated"; negative latency
    # z just means the service got faster, which is not an anomaly
    # FCP's latency rules fire on).
    lat = z["latency"] if z["latency"] > 0 else 0.0
    lat_normal   = _trap(lat, 0.0, 0.0, 0.5, 1.0)
    lat_elevated = _tri(lat, 0.5, 2.0, 4.0)
    lat_critical = _trap(lat, 2.0, 4.0, 1e9, 1e9)

    # Error rate: same shape as latency (only the positive direction
    # is anomalous — errors rising above baseline).
    err = z["error"] if z["error"] > 0 else 0.0
    err_none     = _trap(err, 0.0, 0.0, 0.3, 0.8)
    err_low      = _tri(err, 0.3, 1.0, 2.0)
    err_elevated = _tri(err, 1.0, 2.0, 4.0)
    err_high     = _trap(err, 2.0, 4.0, 1e9, 1e9)

    # Throughput: the Java fuzzifier names LOW (= traffic dropped) and
    # NORMAL (= traffic at or above baseline). We map negative z to LOW
    # and positive-or-zero z to NORMAL.
    if z["traffic"] < 0.0:
        tr_low = _trap(-z["traffic"], 0.5, 2.0, 1e9, 1e9)
        tr_normal = max(0.0, 1.0 - tr_low)
    else:
        tr_low = 0.0
        tr_normal = 1.0

    memberships = {
        "cpu_LOW": cpu_low, "cpu_MEDIUM": cpu_medium, "cpu_HIGH": cpu_high,
        "memory_LOW": mem_low, "memory_MEDIUM": mem_medium, "memory_HIGH": mem_high,
        "latency_NORMAL": lat_normal, "latency_ELEVATED": lat_elevated,
        "latency_CRITICAL": lat_critical,
        "errorRate_NONE": err_none, "errorRate_LOW": err_low,
        "errorRate_ELEVATED": err_elevated, "errorRate_HIGH": err_high,
        "throughput_LOW": tr_low, "throughput_NORMAL": tr_normal,
    }
    return _ServiceFuzzyVector(
        service=service, memberships=memberships, z_signed=z,
    )


# ---- Mamdani rule firing ---------------------------------------------------


@dataclass(frozen=True)
class _FaultHypothesis:
    """Result of running the rule base on one service's fuzzy vector.

    Mirrors :class:`com.foda.rca.model.FaultHypothesis` from the Java
    reference. ``local_confidence`` is what FCP calls ``H(s)``; the
    propagator's job is to fold it into a global ``C(s)``.
    """

    service: str
    local_confidence: float
    dominant_category: str
    fired_rules: tuple[str, ...]
    rule_fire_strengths: dict[str, float]


def _infer_hypothesis(fv: _ServiceFuzzyVector) -> _FaultHypothesis:
    """Run the 16-rule Mamdani base on ``fv`` and return the dominant
    fault hypothesis. Step-for-step port of
    :meth:`MamdaniFuzzyRuleEngine.infer`.
    """
    fire: dict[str, float] = {}
    for rule in RULE_BASE:
        mu_min = min(fv.memberships.get(a, 0.0) for a in rule.antecedents)
        alpha = rule.cf * mu_min
        if alpha > 0.0:
            fire[rule.rule_id] = alpha

    if not fire:
        return _FaultHypothesis(
            service=fv.service, local_confidence=0.0,
            dominant_category="UNKNOWN",
            fired_rules=(), rule_fire_strengths={},
        )

    # Aggregate per category by max (Mamdani max-aggregation).
    by_cat: dict[str, float] = defaultdict(float)
    for rule in RULE_BASE:
        if rule.rule_id in fire:
            by_cat[rule.consequent] = max(by_cat[rule.consequent], fire[rule.rule_id])

    dominant = max(by_cat.items(), key=lambda kv: kv[1])
    return _FaultHypothesis(
        service=fv.service,
        local_confidence=float(dominant[1]),
        dominant_category=dominant[0],
        fired_rules=tuple(sorted(fire.keys())),
        rule_fire_strengths=dict(sorted(fire.items())),
    )


# ---- topology inference (shared shape with MicroRCA / yRCA) ----------------


def _infer_topology(
    case_window: pd.DataFrame,
    services: list[str],
    hypotheses: dict[str, _FaultHypothesis],
    onset_time: float,
    threshold: float,
    lag: int,
) -> dict[tuple[str, str], float]:
    """Directed edge ``u → v`` with weight ``|lagged_corr(u, v)|``
    where ``|lagged_corr| ≥ threshold`` and ``u`` leads ``v`` by
    ``lag`` samples in the post-onset window.

    Mirrors :func:`evaluation.methods.yrca._infer_topology` so the
    three topology-inference adapters (MicroRCA, yRCA, FODA-FCP)
    share an edge-construction convention. Documented in
    DEVIATIONS.md → "FODA-FCP adapter".
    """
    times = case_window["time"].to_numpy(dtype=float)
    post_mask = times >= onset_time

    # Per service: pick the highest-|z| canonical feature as the
    # service's representative signal. Ties / no-deviation cases fall
    # back to the first canonical feature actually present.
    dominant: dict[str, str] = {}
    for svc in services:
        z = {
            feat: abs(_zscore(case_window, svc, feat, onset_time))
            for feat in ("cpu", "mem", "latency", "error", "traffic")
        }
        best_feat = max(z.items(), key=lambda kv: kv[1])[0]
        if z[best_feat] == 0.0:
            for feat in ("latency", "traffic", "cpu", "mem", "error"):
                if f"{svc}_{feat}" in case_window.columns:
                    best_feat = feat
                    break
        dominant[svc] = best_feat

    signals: dict[str, np.ndarray] = {}
    for svc, feat in dominant.items():
        col = f"{svc}_{feat}"
        if col not in case_window.columns:
            continue
        arr = case_window[col].to_numpy(dtype=float)[post_mask]
        if arr.size > max(lag, 1) + 1:
            signals[svc] = arr.astype(float)

    edges: dict[tuple[str, str], float] = {}
    for u in services:
        su = signals.get(u)
        if su is None:
            continue
        for v in services:
            if u == v:
                continue
            sv = signals.get(v)
            if sv is None:
                continue
            w_uv = _lagged_corr(su, sv, lag) if lag > 0 else _corr(su, sv)
            w_vu = _lagged_corr(sv, su, lag) if lag > 0 else w_uv
            if w_uv < threshold:
                continue
            if lag > 0 and w_uv < w_vu:
                continue
            edges[(u, v)] = float(w_uv)
    return edges


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
    n = min(a.size, b.size)
    if n <= lag + 1:
        return 0.0
    return _corr(a[: n - lag], b[lag:n])


# ---- damped Noisy-OR confidence propagation --------------------------------


def _has_cycle(services: list[str],
               edges: dict[tuple[str, str], float]) -> bool:
    """DFS cycle check; mirrors :meth:`ServiceDependencyGraph.hasCycle`."""
    out: dict[str, list[str]] = defaultdict(list)
    for (u, v) in edges:
        out[u].append(v)
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {s: WHITE for s in services}

    def visit(node: str) -> bool:
        color[node] = GREY
        for w in out.get(node, []):
            if color.get(w, WHITE) == GREY:
                return True
            if color.get(w, WHITE) == WHITE and visit(w):
                return True
        color[node] = BLACK
        return False

    return any(color[s] == WHITE and visit(s) for s in services)


def _reverse_topo_order(services: list[str],
                        edges: dict[tuple[str, str], float]) -> list[str]:
    """Kahn's algorithm → topological order, then reverse it. Mirrors
    :meth:`DampedConfidencePropagator.reversedTopologicalOrder`."""
    in_deg: dict[str, int] = {s: 0 for s in services}
    out: dict[str, list[str]] = defaultdict(list)
    for (u, v) in edges:
        if v not in in_deg:
            in_deg[v] = 0
        if u not in in_deg:
            in_deg[u] = 0
        in_deg[v] += 1
        out[u].append(v)
    queue = deque(sorted([s for s, d in in_deg.items() if d == 0]))
    order: list[str] = []
    in_deg_w = dict(in_deg)
    while queue:
        s = queue.popleft()
        order.append(s)
        for w in out.get(s, []):
            in_deg_w[w] -= 1
            if in_deg_w[w] == 0:
                queue.append(w)
    # Append any service we missed (shouldn't happen on acyclic input,
    # but be defensive — Kahn drops nodes that participate in a cycle).
    for s in services:
        if s not in order:
            order.append(s)
    order.reverse()
    return order


def _propagate_damped(
    hypotheses: dict[str, _FaultHypothesis],
    services: list[str],
    edges: dict[tuple[str, str], float],
    delta: float,
) -> dict[str, float]:
    """Eq. 4 — damped Noisy-OR propagation in reverse-topological
    order. Faithful port of :class:`DampedConfidencePropagator`."""
    out: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (u, v), w in edges.items():
        out[u].append((v, w))

    C: dict[str, float] = {
        s: hypotheses[s].local_confidence if s in hypotheses else 0.0
        for s in services
    }
    for s in _reverse_topo_order(services, edges):
        callees = out.get(s, [])
        if not callees:
            continue
        comp = 1.0
        for (t, w) in callees:
            ct = C.get(t, 0.0)
            comp *= 1.0 - ct * w * delta
        p = 1.0 - comp
        hs = C[s]
        C[s] = max(0.0, min(1.0, 1.0 - (1.0 - hs) * (1.0 - p)))
    return C


def _propagate_iterative(
    hypotheses: dict[str, _FaultHypothesis],
    services: list[str],
    edges: dict[tuple[str, str], float],
    delta: float,
    epsilon: float = 1e-6,
    max_iter: int = 100,
) -> dict[str, float]:
    """Eq. 5 — Jacobi fixed-point iteration for cyclic dependency
    graphs. Port of :class:`IterativeConfidencePropagator`. Banach
    convergence is guaranteed for ``δ < 1``; for ``δ == 1`` the
    iteration may not converge, in which case we return the last
    iterate after ``max_iter`` rounds."""
    out: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (u, v), w in edges.items():
        out[u].append((v, w))

    H = {s: hypotheses[s].local_confidence if s in hypotheses else 0.0
         for s in services}
    C = dict(H)
    for _ in range(max_iter):
        C_next: dict[str, float] = {}
        for s in services:
            callees = out.get(s, [])
            comp = 1.0
            for (t, w) in callees:
                ct = C.get(t, 0.0)
                comp *= 1.0 - ct * w * delta
            p = 1.0 - comp
            C_next[s] = max(0.0, min(1.0, 1.0 - (1.0 - H[s]) * (1.0 - p)))
        if max(abs(C_next[s] - C[s]) for s in services) < epsilon:
            C = C_next
            break
        C = C_next
    return C


# ---- explanation assembly --------------------------------------------------


# Which fuzzy-membership keys participate in evidence for each fault
# category. Used to surface the "contributing factor" features in the
# atom text so the case-study figure shows what the rule engine saw.
_CATEGORY_EVIDENCE_KEYS: dict[str, tuple[str, ...]] = {
    "CPU_SATURATION":     ("cpu_HIGH", "latency_ELEVATED", "latency_CRITICAL", "throughput_LOW"),
    "MEMORY_PRESSURE":    ("memory_HIGH", "throughput_LOW", "latency_ELEVATED", "cpu_MEDIUM"),
    "SERVICE_ERROR":      ("errorRate_HIGH", "errorRate_ELEVATED", "latency_ELEVATED", "cpu_HIGH"),
    "LATENCY_ANOMALY":    ("latency_CRITICAL", "latency_ELEVATED", "throughput_LOW"),
    "CASCADING_FAILURE":  ("cpu_HIGH", "memory_HIGH", "latency_CRITICAL",
                           "errorRate_ELEVATED", "errorRate_HIGH"),
    "RESOURCE_CONTENTION": ("cpu_HIGH", "memory_HIGH", "throughput_LOW", "cpu_MEDIUM"),
}


def _atom_text(
    rank: int,
    service: str,
    hyp: _FaultHypothesis,
    final_confidence: float,
    fault_local_name: str,
    fv: _ServiceFuzzyVector,
) -> str:
    """Human-readable atom text. Mentions the predicted fault category
    AND the ontology class name so the case-study figure shows the
    semantic link without needing to load the OWL graph."""
    ev_keys = _CATEGORY_EVIDENCE_KEYS.get(hyp.dominant_category, ())
    evidence = [
        f"{k}(μ={fv.memberships.get(k, 0.0):.2f})"
        for k in ev_keys if fv.memberships.get(k, 0.0) >= 0.10
    ]
    ev_text = ", ".join(evidence) if evidence else "no strong fuzzy evidence"
    return (
        f"#{rank} {service} → {fault_local_name} "
        f"(H={hyp.local_confidence:.3f}, C={final_confidence:.3f}, "
        f"rules={list(hyp.fired_rules)}, evidence=[{ev_text}])"
    )


def _build_explanation(
    services_ranked: list[tuple[str, float]],
    hypotheses: dict[str, _FaultHypothesis],
    fuzzy_vectors: dict[str, _ServiceFuzzyVector],
    edges: dict[tuple[str, str], float],
    delta: float,
    top_k: int,
) -> CanonicalExplanation:
    """Assemble the FODA-FCP CanonicalExplanation per the Paper 6
    contract (see module docstring, §"Ontology-grounded explanation")."""
    explanation = CanonicalExplanation()
    head = services_ranked[:top_k]
    if not head:
        return explanation

    sum_head = sum(c for _, c in head) or 1.0

    atom_by_service: dict[str, ExplanationAtom] = {}
    root_service, root_C = head[0]
    root_hyp = hypotheses[root_service]
    root_fault = CATEGORY_TO_FAULT.get(root_hyp.dominant_category)

    for rank, (svc, C) in enumerate(head, start=1):
        hyp = hypotheses[svc]
        fault_local = CATEGORY_TO_FAULT.get(hyp.dominant_category)
        if fault_local is None:
            # No Mamdani rule fired — try a soft fallback that maps the
            # service's strongest fuzzy term onto a fault prototype.
            # Atoms that still can't be mapped fall back to the abstract
            # ContributingFactor class (out-of-scope for SC, but still
            # in the ontology graph so SG can ground them).
            inferred = _infer_fault_prototype_from_fuzzy(fuzzy_vectors[svc])
            if inferred is not None:
                ontology_class = _ontology_uri(inferred)
                fault_local_for_text = f"{inferred} (fuzzy-inferred)"
            else:
                ontology_class = _ontology_uri("ContributingFactor")
                fault_local_for_text = "ContributingFactor (unmapped category)"
        else:
            ontology_class = _ontology_uri(fault_local)
            fault_local_for_text = fault_local
        membership = float(np.clip(C / sum_head, 0.0, 1.0))
        atom = ExplanationAtom(
            text=_atom_text(rank, svc, hyp, C, fault_local_for_text,
                            fuzzy_vectors[svc]),
            ontology_class=ontology_class,
            fuzzy_membership=membership,
        )
        explanation.add_atom(atom)
        atom_by_service[svc] = atom

    # Recommendation atom — ONLY for the predicted root cause, tagged
    # with the Rec_* individual associated with the root's fault
    # prototype. Same fuzzy membership as the root atom (i.e., the
    # confidence with which we recommend the mitigation matches the
    # confidence in the diagnosis).
    rec_atom: ExplanationAtom | None = None
    if root_fault is not None:
        rec_local = FAULT_TO_RECOMMENDATION.get(root_fault)
        if rec_local is not None:
            rec_atom = ExplanationAtom(
                text=(
                    f"Recommendation for {root_service}: {rec_local} "
                    f"(suggests_mitigation, derived from "
                    f"{root_fault} prototype)"
                ),
                ontology_class=_ontology_uri(rec_local),
                fuzzy_membership=atom_by_service[root_service].fuzzy_membership,
            )
            explanation.add_atom(rec_atom)

    # Links — three relation_types as documented in the module docstring.
    # ``contributes_to`` from non-root atoms to the root, weighted by the
    # FCP propagation contribution C(t) · w(root, t) · δ. The rule_id is
    # encoded as the relation_type suffix after the colon so it survives
    # CanonicalExplanation's flat (source, target, weight, type) edge
    # storage.
    for svc, atom in atom_by_service.items():
        if svc == root_service:
            continue
        # The FCP noisy-OR contribution into the root's confidence is
        # ``C(t) · w(root, t) · δ`` for each callee ``t`` of the root
        # (Eq. 4 in the AICT paper). The non-root's atom membership
        # already encodes ``C(t)`` (normalized by sum_head), so the
        # propagation weight on the edge is ``edges[(root, t)] · δ``
        # when the topology has a directed edge from root to non-root;
        # otherwise zero. We multiply by the source atom's fuzzy
        # membership so the rendered ``weight`` is the full noisy-OR
        # contribution term, matching the brief's "FCP propagation
        # weight" semantics.
        edge_w = edges.get((root_service, svc), 0.0)
        contrib = float(np.clip(
            (atom.fuzzy_membership or 0.0) * edge_w * delta, 0.0, 1.0,
        ))
        explanation.add_link(CausalLink(
            source_atom_id=atom.id,
            target_atom_id=atom_by_service[root_service].id,
            weight=contrib,
            relation_type="contributes_to:propagation:noisy_or",
        ))

    # ``suggests_mitigation`` from every ContributingFactor atom to the
    # Recommendation atom. Weight = source atom's fuzzy_membership.
    if rec_atom is not None:
        for svc, atom in atom_by_service.items():
            mu = atom.fuzzy_membership or 0.0
            explanation.add_link(CausalLink(
                source_atom_id=atom.id,
                target_atom_id=rec_atom.id,
                weight=float(np.clip(mu, 0.0, 1.0)),
                relation_type="suggests_mitigation:recommendation:fault_prototype",
            ))

    return explanation


# ---- ranking helper --------------------------------------------------------


def _rank(
    confidence: dict[str, float],
    hypotheses: dict[str, _FaultHypothesis],
    services: list[str],
) -> list[tuple[str, float]]:
    """Sort by ``C(s)`` desc; break ties by ``H(s)`` desc, then by
    service name asc for determinism."""
    def key(svc: str) -> tuple[float, float, str]:
        c = confidence.get(svc, 0.0)
        h = hypotheses[svc].local_confidence if svc in hypotheses else 0.0
        return (-c, -h, svc)
    return [(svc, confidence.get(svc, 0.0)) for svc in sorted(services, key=key)]


# ---- public method ---------------------------------------------------------


class FodaFCPMethod(RCAMethod):
    """FODA-FCP on :class:`NormalizedCase`.

    Parameters
    ----------
    damping_factor:
        Per-hop damping coefficient ``δ`` in Eq. 4. The AICT paper's
        recommended setting is ``0.85``; ``1.0`` degenerates to
        undamped noisy-OR. Must be in ``(0, 1]``.
    topology_threshold:
        ``|Pearson|`` cutoff for inferring a dependency edge between
        two services' representative signals. ``0.5`` aligns with the
        MicroRCA / yRCA convention on RE1-OB.
    lag:
        Sample lag for the asymmetric edge-orientation step (mirrors
        MicroRCA). ``lag=0`` collapses to symmetric Pearson and loses
        directionality.
    top_k:
        Length of the ranked head surfaced in the explanation.
    window_seconds:
        Total window length forwarded to :func:`normalize_case`.
    max_iterations:
        Iteration cap for the cyclic-graph fixed-point fallback.
        Ignored on acyclic graphs (the damped propagator is exact in
        one reverse-topological pass).
    """

    name = "foda-fcp"

    def __init__(
        self,
        damping_factor: float = 0.85,
        topology_threshold: float = 0.5,
        lag: int = 1,
        top_k: int = 3,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        max_iterations: int = 100,
    ) -> None:
        if not 0.0 < damping_factor <= 1.0:
            raise ValueError(
                f"damping_factor must be in (0, 1], got {damping_factor}"
            )
        if not 0.0 <= topology_threshold <= 1.0:
            raise ValueError(
                f"topology_threshold must be in [0, 1], got {topology_threshold}"
            )
        if lag < 0:
            raise ValueError(f"lag must be >= 0, got {lag}")
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if window_seconds <= 0.0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        if max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >= 1, got {max_iterations}"
            )
        self.damping_factor = damping_factor
        self.topology_threshold = topology_threshold
        self.lag = lag
        self.top_k = top_k
        self.window_seconds = window_seconds
        self.max_iterations = max_iterations

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run the five-phase FCP pipeline on a pre-built
        :class:`NormalizedCase`. The harness calls this directly so it
        can pass a normalized case whose ``ground_truth`` was
        deliberately shifted — the shift must not move the output
        because we never read ``ground_truth`` from inside
        ``diagnose``. The static witness is
        :mod:`evaluation.methods._protocol`.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"FODA-FCP: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        # Phase 0 — onset (shared utility; replaces FCP's inject_time
        # fencepost, which is hidden under the NormalizedCase contract).
        onset_t = detect_onset(norm.case_window, norm.services)

        # Phase 1 — fuzzification (per-service membership vectors).
        fuzzy_vectors: dict[str, _ServiceFuzzyVector] = {
            svc: _fuzzify_service(norm.case_window, svc, onset_t)
            for svc in norm.services
        }

        # Phase 2 — Mamdani fault inference.
        hypotheses: dict[str, _FaultHypothesis] = {
            svc: _infer_hypothesis(fv) for svc, fv in fuzzy_vectors.items()
        }

        # Phase 3a — infer the dependency graph (no RE1 topology).
        edges = _infer_topology(
            case_window=norm.case_window,
            services=norm.services,
            hypotheses=hypotheses,
            onset_time=onset_t,
            threshold=self.topology_threshold,
            lag=self.lag,
        )

        # Phase 3b — damped Noisy-OR propagation (adaptive: acyclic → Eq. 4,
        # cyclic → Eq. 5).
        if _has_cycle(norm.services, edges):
            confidence_map = _propagate_iterative(
                hypotheses=hypotheses,
                services=norm.services,
                edges=edges,
                delta=self.damping_factor,
                max_iter=self.max_iterations,
            )
            propagator_kind = "iterative"
        else:
            confidence_map = _propagate_damped(
                hypotheses=hypotheses,
                services=norm.services,
                edges=edges,
                delta=self.damping_factor,
            )
            propagator_kind = "damped"

        # Phase 4 — rank.
        ranked = _rank(confidence_map, hypotheses, norm.services)

        # Phase 5 — explanation.
        explanation = _build_explanation(
            services_ranked=ranked,
            hypotheses=hypotheses,
            fuzzy_vectors=fuzzy_vectors,
            edges=edges,
            delta=self.damping_factor,
            top_k=self.top_k,
        )

        # Confidence — concentration of fuzzy contribution mass on top-1
        # relative to the top-K head (see module docstring).
        head = ranked[: self.top_k]
        head_sum = sum(c for _, c in head)
        top1_C = head[0][1] if head else 0.0
        if head_sum > 0.0:
            confidence_value = float(np.clip(top1_C / head_sum, 0.0, 1.0))
        else:
            confidence_value = 0.0

        raw = {
            "onset_time": onset_t,
            "propagator_kind": propagator_kind,
            "damping_factor": self.damping_factor,
            "topology_edges": [(u, v) for (u, v) in edges.keys()],
            "topology_n_edges": len(edges),
            "local_confidence_H": {
                svc: hypotheses[svc].local_confidence for svc in norm.services
            },
            "final_confidence_C": dict(confidence_map),
            "dominant_category": {
                svc: hypotheses[svc].dominant_category for svc in norm.services
            },
            "fired_rules": {
                svc: list(hypotheses[svc].fired_rules) for svc in norm.services
            },
            "predicted_fault_local_name": CATEGORY_TO_FAULT.get(
                hypotheses[ranked[0][0]].dominant_category
            ) if ranked else None,
        }

        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence_value,
            raw_output=raw,
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )


# Backwards-compatible alias for the previous stub class name. The brief
# spells the public class ``FODAFCPMethod`` / ``FodaFCPMethod``; older
# call sites used ``FodaFCP``. Keep both pointed at the same
# implementation so existing tests that import either continue to work.
FodaFCP = FodaFCPMethod
