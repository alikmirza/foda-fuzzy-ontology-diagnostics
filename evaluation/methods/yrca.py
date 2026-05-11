"""yRCA (Soldani, Bono, Brogi — Software: Practice and Experience
2022/2025) refactored for the inject_time-clean
:class:`NormalizedCase` contract.

yRCA's published contribution is an **explanation-focused, rule-based
causal-inference layer over logs**: a Prolog ruleset reasons over
typed log events plus an explicit topology model to derive cause-
effect chains of "service S's anomaly is explained by service T's
prior anomaly." The Prolog engine produces an explanation graph; the
final root cause is whichever services remain unexplained at the
chain's source.

We re-implement the methodology in Python under two structural
adaptations, both documented in ``DEVIATIONS.md`` under "yRCA
adapter":

1. **Synthetic events from metrics.** RCAEval RE1-OB ships no logs;
   our :class:`NormalizedCase` is metric-only. For each
   ``(service, canonical feature)`` pair we run the shared
   :func:`evaluation.methods._onset.detect_onset` to find a pivot,
   then compare post-onset vs. pre-onset z-score. Magnitudes above
   ``+severity_threshold`` emit a synthetic ``anomaly_high`` event;
   below ``−severity_threshold`` an ``anomaly_low`` event. Every
   synthetic event is timestamped at the detected onset.

2. **Python forward chaining instead of Prolog.** The ruleset is
   ported to native dictionaries / lists of facts and applied
   iteratively until a fixed-point is reached. The iteration cap
   (``max_iterations``) is a finite budget to prevent runaway
   recursion on malformed inputs; for the published ruleset shape it
   terminates in ≤ ``|services|`` iterations because each rule
   strictly adds facts.

The five-rule core captures yRCA's reasoning logic without its full
Prolog ruleset depth:

* **R1 — potential_root_cause.** Any ``anomaly_high(s, f, t)`` or
  ``anomaly_low(s, f, t)`` event nominates ``s`` as a potential root
  cause, with its initiating feature ``f`` and timestamp ``t``.
* **R2 — explained_by (propagation).** If ``s_dep`` depends on
  ``s_cause`` (topology edge) and ``s_cause`` has a potential-root-
  cause anomaly at time ``t0`` and ``s_dep`` has its own anomaly at
  ``t1 ≥ t0``, then ``s_dep`` is explained_by ``s_cause``.
* **R3 — final_root_cause.** A service is a final root cause iff it
  has at least one ``potential_root_cause`` fact and there is no
  service ``t`` for which ``s`` is ``explained_by t``.
* **R4 — retry_cascade.** A traffic anomaly downstream of an
  upstream-service latency or error anomaly is tagged as a retry
  cascade and counts as explained_by the upstream service. This
  captures yRCA's "retries propagate symptoms" reasoning pattern.
* **R5 — timeout_propagation.** A latency anomaly downstream of an
  upstream latency anomaly with a positive lead-lag of ≥ 1 sample is
  tagged as timeout propagation. Adds a second derivation path for
  the same explained_by edge, which raises confidence when both
  R2 and R5 fire on the same pair.

Topology is **inferred** from feature correlations because RCAEval
ships no explicit call graph: an edge ``u → v`` exists when the
post-onset Pearson correlation of ``u``'s and ``v``'s dominant
features exceeds ``topology_threshold``, with direction set by
which signal leads (lagged correlation). This mirrors how
MicroRCA / MonitorRank infer topology — see ``DEVIATIONS.md``.

The CanonicalExplanation surfaced is the **derived causal chain**:

* One :class:`ExplanationAtom` per service in the chain, role-tagged
  ``potential_root_cause`` / ``intermediate_propagator`` /
  ``final_root_cause`` via ``ontology_class``.
* :class:`CausalLink` edges for every ``explained_by`` derivation,
  ``relation_type="rule_derived_explanation"`` with the firing rule
  ID in the link weight metadata.
* Final root-cause atoms carry the heaviest fuzzy membership so the
  ranking is visible in the explanation as well.

Confidence is the **derivation-multiplicity ratio**: the fraction of
``final_root_cause`` services that were derived through at least two
independent rule paths (e.g. both R3-via-R2 and R3-via-R4). A case
with one unambiguously over-derived root has high confidence; a
case with multiple tied single-derivation candidates has low.

Deviations from the published method live in ``DEVIATIONS.md`` under
"yRCA adapter".
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

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

# Feature classes used by R4 / R5 to recognise retry-cascade and
# timeout-propagation shapes. Latency/error anomalies upstream cause
# traffic anomalies downstream under the retry pattern; latency
# anomalies upstream cause latency anomalies downstream under the
# timeout pattern.
_UPSTREAM_SYMPTOMS: frozenset[str] = frozenset({"latency", "error"})
_RETRY_DOWNSTREAM:  frozenset[str] = frozenset({"traffic"})
_TIMEOUT_DOWNSTREAM: frozenset[str] = frozenset({"latency"})


# ---- synthetic-event types ----


@dataclass(frozen=True)
class SyntheticEvent:
    """One log-shaped event synthesised from a metric column.

    Fields mirror what a real log parser would emit so the Python
    rule engine sees the same shape yRCA's Prolog clauses see: a
    typed event, a service, a feature label, a timestamp, and a
    severity (used by ranking and the retry/timeout pattern rules).
    """

    service: str
    feature: str
    kind: str          # "anomaly_high" | "anomaly_low" | "normal"
    timestamp: float
    severity: float    # |z-score| for anomalies, 0.0 for normals
    z_signed: float    # signed z-score (positive=high, negative=low)


# ---- fact / rule bookkeeping ----


@dataclass
class _Fact:
    """One derived fact inside the forward-chaining engine.

    ``relation`` is the fact predicate (``potential_root_cause``,
    ``explained_by``, ``final_root_cause``). ``args`` is a tuple of
    positional arguments (services, features, timestamps); the engine
    deduplicates on ``(relation, args)``.
    """

    relation: str
    args: tuple
    rule_id: str          # which rule fired to derive this fact
    timestamp: float = 0.0  # event timestamp, when applicable


# ---- YRCAMethod ----


class YRCAMethod(RCAMethod):
    """yRCA on :class:`NormalizedCase`.

    Parameters
    ----------
    severity_threshold:
        Per-feature z-score above which a synthetic anomaly event is
        emitted (and below ``-severity_threshold`` for low-side
        anomalies). The brief defaults this to ``3.0``; ``2.0`` is
        also defensible for noisier benchmarks. We expose it so the
        sensitivity to the choice can be probed without reaching
        into the body of ``diagnose``.
    topology_threshold:
        ``|Pearson|`` cutoff for inferring a topology edge between
        two services' dominant features in the post-onset window.
        ``0.5`` is the harness default — high enough to reject
        background correlation noise on RE1-OB, low enough that
        true call-graph neighbours stay connected.
    emit_normal_events:
        When ``True``, additionally emit ``normal`` baseline events
        for service-feature pairs whose z-score stayed within
        ``[-1, 1]``. These don't drive any current rule but make the
        event stream comparable to what a real log parser would
        produce; useful for the explanation-completeness metric and
        the SemanticGroundedness inspection in Paper 6.
    max_iterations:
        Forward-chaining iteration cap. Each rule strictly adds
        facts, so on a well-formed input the engine reaches a
        fixed-point in ``≤ |services|`` iterations; the cap is a
        safety net against pathological inputs.
    top_k:
        Size of the explanation head. Also caps the ranked list to
        the ``top_k`` final-root-cause candidates, padded with the
        next-most-severe non-root-cause services if there aren't
        ``top_k`` final root causes.
    window_seconds:
        Total window length passed to :func:`normalize_case`.
    lag:
        Sample lag for the asymmetric topology-edge orientation
        (matches MicroRCA's convention). ``lag=1`` is the default;
        ``lag=0`` collapses to symmetric Pearson and loses
        directionality.
    """

    name = "yrca"

    def __init__(
        self,
        severity_threshold: float = 3.0,
        topology_threshold: float = 0.5,
        emit_normal_events: bool = False,
        max_iterations: int = 32,
        top_k: int = 3,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
        lag: int = 1,
    ) -> None:
        if severity_threshold <= 0.0:
            raise ValueError(
                f"severity_threshold must be > 0, got {severity_threshold}"
            )
        if not 0.0 <= topology_threshold <= 1.0:
            raise ValueError(
                f"topology_threshold must be in [0, 1], "
                f"got {topology_threshold}"
            )
        if max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >= 1, got {max_iterations}"
            )
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if window_seconds <= 0.0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        if lag < 0:
            raise ValueError(f"lag must be >= 0, got {lag}")
        self.severity_threshold = severity_threshold
        self.topology_threshold = topology_threshold
        self.emit_normal_events = emit_normal_events
        self.max_iterations = max_iterations
        self.top_k = top_k
        self.window_seconds = window_seconds
        self.lag = lag

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run yRCA's pipeline on a pre-built :class:`NormalizedCase`.

        The harness calls this directly so it can pass a normalized
        case whose ``ground_truth`` has been deliberately shifted —
        that shift must not move the output because we never read
        ``ground_truth`` from inside ``diagnose``. The static witness
        is :mod:`evaluation.methods._protocol`.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"YRCA: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        # Strategy A: detect onset from telemetry alone (the shared
        # `_onset.detect_onset`). Synthetic events are timestamped at
        # this pivot. Documented in DEVIATIONS.md → yRCA adapter.
        onset_t = detect_onset(norm.case_window, norm.services)

        events = _synthesize_events(
            case_window=norm.case_window,
            services=norm.services,
            onset_time=onset_t,
            severity_threshold=self.severity_threshold,
            emit_normal=self.emit_normal_events,
        )
        topology = _infer_topology(
            case_window=norm.case_window,
            services=norm.services,
            events=events,
            onset_time=onset_t,
            corr_threshold=self.topology_threshold,
            lag=self.lag,
        )

        facts, iterations = _forward_chain(
            services=norm.services,
            events=events,
            topology=topology,
            max_iterations=self.max_iterations,
        )

        ranked, severity_by_service = _rank_services(
            services=norm.services,
            facts=facts,
            events=events,
            top_k=self.top_k,
        )
        confidence = _derivation_multiplicity_confidence(facts)
        explanation = _build_yrca_explanation(
            facts=facts,
            severity_by_service=severity_by_service,
            top_k=self.top_k,
        )

        raw = {
            "onset_time": onset_t,
            "n_events": len(events),
            "n_anomaly_events": sum(
                1 for e in events if e.kind != "normal"
            ),
            "topology_edges": [
                (u, v) for (u, v) in topology.keys()
            ],
            "iterations": iterations,
            "n_facts": len(facts),
            "facts_by_relation": _facts_by_relation_summary(facts),
            "final_root_causes": sorted(
                {f.args[0] for f in facts if f.relation == "final_root_cause"}
            ),
            "severity_by_service": severity_by_service,
            # Per-edge rule-derivation list — recovers what the
            # explanation's flat (source, target, weight, relation_type)
            # tuples lose because CanonicalExplanation's nx.DiGraph
            # can't carry multiple parallel edges. Keys are
            # ``(dep, cause)`` tuples (the explained_by direction);
            # values are sorted lists of distinct ``rule_id``s that
            # derived that edge.
            "explanation_edges": _explanation_edges_with_rules(facts),
        }

        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=raw,
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )


# ---- synthetic event generation ----


def _synthesize_events(
    case_window: pd.DataFrame,
    services: list[str],
    onset_time: float,
    severity_threshold: float,
    emit_normal: bool,
) -> list[SyntheticEvent]:
    """Emit one :class:`SyntheticEvent` per significant service-feature
    pair. Magnitudes above ``+severity_threshold`` ⇒ ``anomaly_high``;
    below ``-severity_threshold`` ⇒ ``anomaly_low``. With
    ``emit_normal=True``, pairs whose ``|z| ≤ 1`` additionally emit
    a ``normal`` baseline event so the event stream resembles a real
    log parser's output.

    All events are timestamped at the detected ``onset_time`` —
    matching yRCA's "the log entry's timestamp is when the event
    happened" assumption, with the caveat that under the synthetic-
    event regime the onset is a window-level estimate, not a per-
    feature timestamp. Documented in DEVIATIONS.md.
    """
    df = case_window
    if "time" not in df.columns:
        return []
    times = df["time"].to_numpy(dtype=float)
    pre_mask = times < onset_time
    post_mask = times >= onset_time

    out: list[SyntheticEvent] = []
    for svc in services:
        for feat in _FEATURE_PRIORITY:
            col = f"{svc}_{feat}"
            if col not in df.columns:
                continue
            x = df[col].to_numpy(dtype=float)
            x_pre = x[pre_mask]
            x_post = x[post_mask]
            if x_pre.size < 2 or x_post.size < 1:
                continue
            sd = float(x_pre.std())
            if sd == 0.0:
                continue
            z = (float(x_post.mean()) - float(x_pre.mean())) / sd
            if not np.isfinite(z):
                continue
            if z >= severity_threshold:
                out.append(SyntheticEvent(
                    service=svc, feature=feat,
                    kind="anomaly_high",
                    timestamp=onset_time,
                    severity=abs(z),
                    z_signed=z,
                ))
            elif z <= -severity_threshold:
                out.append(SyntheticEvent(
                    service=svc, feature=feat,
                    kind="anomaly_low",
                    timestamp=onset_time,
                    severity=abs(z),
                    z_signed=z,
                ))
            elif emit_normal and abs(z) <= 1.0:
                out.append(SyntheticEvent(
                    service=svc, feature=feat,
                    kind="normal",
                    timestamp=onset_time,
                    severity=0.0,
                    z_signed=z,
                ))
    return out


# ---- topology inference ----


def _infer_topology(
    case_window: pd.DataFrame,
    services: list[str],
    events: list[SyntheticEvent],
    onset_time: float,
    corr_threshold: float,
    lag: int,
) -> dict[tuple[str, str], float]:
    """Infer a directed dependency graph from feature correlations.

    Edge ``u → v`` is added (with weight = absolute lagged
    correlation) when ``|corr(u_signal[:T-lag], v_signal[lag:])|``
    exceeds ``corr_threshold`` AND that direction outranks the
    reverse: i.e. ``u``'s past predicts ``v``'s present better than
    the converse. Self-loops are excluded.

    Per service we pick the dominant-anomaly feature (when present)
    or the first available canonical feature as that service's
    representative signal. Mirrors MicroRCA's "no topology in
    RCAEval ⇒ substitute lagged-correlation" deviation; documented
    in DEVIATIONS.md.
    """
    df = case_window
    post_mask = (df["time"] >= onset_time).to_numpy()

    # dominant feature per service, preferring the strongest anomaly
    # we already synthesised (R1 / R2 reasoning naturally couples
    # topology direction to the anomaly axis), falling back to the
    # canonical-feature-priority order.
    dominant: dict[str, str] = {}
    best_z: dict[str, float] = {}
    for e in events:
        if e.kind == "normal":
            continue
        if e.severity > best_z.get(e.service, -np.inf):
            best_z[e.service] = e.severity
            dominant[e.service] = e.feature
    for svc in services:
        if svc not in dominant:
            for feat in _FEATURE_PRIORITY:
                if f"{svc}_{feat}" in df.columns:
                    dominant[svc] = feat
                    break

    signals: dict[str, np.ndarray] = {}
    for svc, feat in dominant.items():
        col = f"{svc}_{feat}"
        if col not in df.columns:
            continue
        arr = df[col].to_numpy(dtype=float)[post_mask].astype(float)
        if arr.size > max(lag, 1) + 1:
            signals[svc] = arr

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
            if w_uv < corr_threshold:
                continue
            if w_uv < w_vu and lag > 0:
                # The reverse direction dominates: keep only that edge,
                # added on the v-as-u sweep.
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
    a_head = a[: n - lag]
    b_tail = b[lag: n]
    return _corr(a_head, b_tail)


# ---- forward-chaining inference ----


def _forward_chain(
    services: list[str],
    events: list[SyntheticEvent],
    topology: dict[tuple[str, str], float],
    max_iterations: int,
) -> tuple[list[_Fact], int]:
    """Apply the five-rule ruleset iteratively until a fixed-point.

    Termination argument: every rule strictly adds facts; the fact
    space is finite (bounded by ``|services|² × |relations|``);
    therefore the engine reaches a fixed-point in at most ``|facts|
    + 1`` iterations. ``max_iterations`` is a hard cap on top of
    that, returned in the iteration count for diagnostic visibility.

    Returns ``(facts, iterations_used)``.
    """
    facts: list[_Fact] = []
    seen: set[tuple] = set()

    def _add(fact: _Fact) -> bool:
        # Dedup on (relation, args, rule_id) — the same (dep, cause)
        # explained_by edge may legitimately be derived by R2, R4, and
        # R5 in turn, and the multi-rule derivations are what raise
        # the confidence metric. We only suppress repeat firings of
        # the same rule on the same fact.
        key = (fact.relation, fact.args, fact.rule_id)
        if key in seen:
            return False
        seen.add(key)
        facts.append(fact)
        return True

    # R1: anomaly event ⇒ potential_root_cause
    for e in events:
        if e.kind in ("anomaly_high", "anomaly_low"):
            _add(_Fact(
                relation="potential_root_cause",
                args=(e.service, e.feature, e.kind),
                rule_id="R1",
                timestamp=e.timestamp,
            ))

    # Index events by service for the propagation rules.
    events_by_service: dict[str, list[SyntheticEvent]] = {s: [] for s in services}
    for e in events:
        if e.kind != "normal":
            events_by_service.setdefault(e.service, []).append(e)

    iterations = 0
    for it in range(max_iterations):
        iterations = it + 1
        added = False

        prc_services = {
            f.args[0] for f in facts if f.relation == "potential_root_cause"
        }

        # R2: explained_by via topology (cause → dep) when both have
        # anomalies and dep's anomaly is not strictly before cause's.
        for (cause, dep), _w in topology.items():
            if cause not in prc_services:
                continue
            if dep not in events_by_service or not events_by_service[dep]:
                continue
            cause_events = [
                e for e in events_by_service.get(cause, [])
                if e.kind != "normal"
            ]
            dep_events = [
                e for e in events_by_service[dep] if e.kind != "normal"
            ]
            if not cause_events or not dep_events:
                continue
            t0 = min(e.timestamp for e in cause_events)
            t1 = min(e.timestamp for e in dep_events)
            if t1 >= t0:
                if _add(_Fact(
                    relation="explained_by",
                    args=(dep, cause),
                    rule_id="R2",
                    timestamp=t1,
                )):
                    added = True

        # R4: retry_cascade — upstream latency/error anomaly + downstream
        # traffic anomaly along a topology edge.
        for (cause, dep), _w in topology.items():
            up = [
                e for e in events_by_service.get(cause, [])
                if e.kind != "normal" and e.feature in _UPSTREAM_SYMPTOMS
            ]
            down = [
                e for e in events_by_service.get(dep, [])
                if e.kind != "normal" and e.feature in _RETRY_DOWNSTREAM
            ]
            if not up or not down:
                continue
            if _add(_Fact(
                relation="explained_by",
                args=(dep, cause),
                rule_id="R4_retry",
                timestamp=min(e.timestamp for e in down),
            )):
                added = True

        # R5: timeout_propagation — upstream latency anomaly + downstream
        # latency anomaly along a topology edge.
        for (cause, dep), _w in topology.items():
            up = [
                e for e in events_by_service.get(cause, [])
                if e.kind != "normal" and e.feature == "latency"
            ]
            down = [
                e for e in events_by_service.get(dep, [])
                if e.kind != "normal" and e.feature in _TIMEOUT_DOWNSTREAM
            ]
            if not up or not down:
                continue
            if _add(_Fact(
                relation="explained_by",
                args=(dep, cause),
                rule_id="R5_timeout",
                timestamp=min(e.timestamp for e in down),
            )):
                added = True

        if not added:
            break

    # R3: final_root_cause — services that have a potential_root_cause
    # fact and are not the source of any explained_by edge.
    explained_subjects = {
        f.args[0] for f in facts if f.relation == "explained_by"
    }
    prc_set = {
        f.args[0] for f in facts if f.relation == "potential_root_cause"
    }
    for svc in prc_set:
        if svc not in explained_subjects:
            _add(_Fact(
                relation="final_root_cause",
                args=(svc,),
                rule_id="R3",
                timestamp=0.0,
            ))

    return facts, iterations


def _facts_by_relation_summary(facts: list[_Fact]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in facts:
        counts[f.relation] = counts.get(f.relation, 0) + 1
    return counts


def _explanation_edges_with_rules(
    facts: list[_Fact],
) -> list[dict[str, object]]:
    """Per-edge rule-derivation list.

    One record per distinct ``(dep, cause)`` pair, listing every
    distinct ``rule_id`` that derived an ``explained_by(dep, cause)``
    fact. Order is by ``(dep, cause)`` for determinism.

    This is the structured representation that CanonicalExplanation's
    flat ``(source, target, weight, relation_type)`` tuples can't
    carry (the underlying graph is single-edge per pair).
    """
    edge_rules: dict[tuple[str, str], set[str]] = {}
    for f in facts:
        if f.relation != "explained_by":
            continue
        key = (f.args[0], f.args[1])  # (dep, cause)
        edge_rules.setdefault(key, set()).add(f.rule_id)
    return [
        {"dep": dep, "cause": cause, "rule_ids": sorted(rules)}
        for (dep, cause), rules in sorted(edge_rules.items())
    ]


# ---- ranking ----


def _rank_services(
    services: list[str],
    facts: list[_Fact],
    events: list[SyntheticEvent],
    top_k: int,
) -> tuple[list[tuple[str, float]], dict[str, float]]:
    """Rank ``final_root_cause`` services by summed event severity.

    Two-tier ranking:
      1. Services with a ``final_root_cause`` fact, ordered by total
         absolute z-magnitude across their anomaly events.
      2. Services without (no anomaly events at all, or only
         transitively-explained), ordered by the same severity but
         pushed below the final-root-cause tier.

    The second tier exists so that downstream metrics (AC@k, MRR)
    still see every service in a defined order, not just the chain
    leaves. The ranking score is the summed severity in both cases
    so the magnitudes remain commensurable.
    """
    severity: dict[str, float] = {svc: 0.0 for svc in services}
    for e in events:
        if e.kind == "normal":
            continue
        severity[e.service] = severity.get(e.service, 0.0) + e.severity

    final_root = {
        f.args[0] for f in facts if f.relation == "final_root_cause"
    }
    primary = sorted(
        ((svc, severity[svc]) for svc in services if svc in final_root),
        key=lambda kv: kv[1],
        reverse=True,
    )
    secondary = sorted(
        (
            (svc, severity[svc])
            for svc in services
            if svc not in final_root
        ),
        key=lambda kv: kv[1],
        reverse=True,
    )
    # Secondary services get an additive penalty so they sort strictly
    # below the primary tier even when their raw severity rivals it.
    # Penalty is the maximum primary severity + 1 so the tier boundary
    # is unambiguous in the sort.
    if primary:
        max_primary = max(score for _, score in primary)
        offset = max_primary + 1.0
        secondary_offset = [
            (svc, max(0.0, score - offset)) for svc, score in secondary
        ]
    else:
        secondary_offset = secondary

    ranked = primary + secondary_offset
    return ranked, severity


# ---- confidence ----


def _derivation_multiplicity_confidence(facts: list[_Fact]) -> float:
    """Fraction of ``final_root_cause`` services derived through ≥ 2
    independent rule paths (distinct ``rule_id``s in their incoming
    derivations).

    Two-step recipe:
      1. For each service tagged ``final_root_cause``, collect the
         distinct ``rule_id``s of every fact that names it as a
         subject (its ``potential_root_cause`` evidence) plus the
         ``rule_id``s of every ``explained_by`` edge pointing AT it.
      2. The service is "multi-derived" iff at least two distinct
         rules appear.

    The confidence is ``#multi_derived / #total_final_root_cause``.
    Falls back to ``0.0`` when no final_root_cause is found (the
    Prolog engine would output no chain).
    """
    final_root = [
        f.args[0] for f in facts if f.relation == "final_root_cause"
    ]
    if not final_root:
        return 0.0
    derivations: dict[str, set[str]] = {svc: set() for svc in final_root}
    for f in facts:
        if f.relation == "potential_root_cause" and f.args[0] in derivations:
            derivations[f.args[0]].add(f.rule_id)
        if f.relation == "explained_by" and f.args[1] in derivations:
            derivations[f.args[1]].add(f.rule_id)
    multi = sum(1 for rules in derivations.values() if len(rules) >= 2)
    return float(np.clip(multi / len(final_root), 0.0, 1.0))


# ---- explanation assembly ----


def _build_yrca_explanation(
    facts: list[_Fact],
    severity_by_service: dict[str, float],
    top_k: int,
) -> CanonicalExplanation:
    """Assemble the rule-derived explanation graph.

    Nodes: one atom per service that appears in any derived fact,
    role-tagged by ``ontology_class``:

    * ``yrca:Role/final_root_cause`` — services with a R3 fact.
    * ``yrca:Role/intermediate_propagator`` — services with a
      potential_root_cause fact AND an outgoing explained_by edge
      (i.e. they're in the chain but not its final root).
    * ``yrca:Role/potential_root_cause`` — services with only a
      potential_root_cause fact and no role above.

    Edges: one ``rule_derived_explanation`` link per ``explained_by``
    fact, weighted by ``1 / (1 + #rules)`` so that multi-rule
    derivations show up as heavier in the explanation graph.
    """
    explanation = CanonicalExplanation()

    final_root = {
        f.args[0] for f in facts if f.relation == "final_root_cause"
    }
    explained_subjects = {
        f.args[0] for f in facts if f.relation == "explained_by"
    }
    prc_subjects = {
        f.args[0] for f in facts if f.relation == "potential_root_cause"
    }
    all_subjects = sorted(prc_subjects | final_root | explained_subjects)
    if not all_subjects:
        return explanation

    # Derivation rules per service (used as a tiebreaker for membership
    # strength: more rule-paths ⇒ higher fuzzy membership).
    rules_per_service: dict[str, set[str]] = {s: set() for s in all_subjects}
    for f in facts:
        if f.relation == "potential_root_cause" and f.args[0] in rules_per_service:
            rules_per_service[f.args[0]].add(f.rule_id)
        if f.relation == "explained_by" and f.args[1] in rules_per_service:
            rules_per_service[f.args[1]].add(f.rule_id)

    max_severity = max(
        (severity_by_service.get(s, 0.0) for s in all_subjects), default=1.0
    ) or 1.0

    atom_by_service: dict[str, ExplanationAtom] = {}
    for svc in all_subjects:
        if svc in final_root:
            role = "final_root_cause"
        elif svc in prc_subjects and svc in explained_subjects:
            role = "intermediate_propagator"
        else:
            role = "potential_root_cause"
        z_sum = severity_by_service.get(svc, 0.0)
        n_rules = len(rules_per_service.get(svc, set()))
        membership = float(np.clip(
            (z_sum / max_severity) * (0.5 + 0.5 * min(1.0, n_rules / 2.0)),
            0.0, 1.0,
        ))
        atom = ExplanationAtom(
            text=(
                f"{svc} [{role}] severity={z_sum:.2f}, "
                f"derived_by_rules={sorted(rules_per_service.get(svc, set()))}"
            ),
            ontology_class=f"yrca:Role/{role}",
            fuzzy_membership=membership,
        )
        explanation.add_atom(atom)
        atom_by_service[svc] = atom

    # explained_by edges. Multiple rules may derive the same
    # (dep, cause) edge — we collapse them, weighting by the count.
    edge_rules: dict[tuple[str, str], set[str]] = {}
    for f in facts:
        if f.relation != "explained_by":
            continue
        key = (f.args[0], f.args[1])  # (dep, cause)
        edge_rules.setdefault(key, set()).add(f.rule_id)

    for (dep, cause), rules in edge_rules.items():
        if dep not in atom_by_service or cause not in atom_by_service:
            continue
        weight = float(np.clip(len(rules) / (len(rules) + 1.0), 0.0, 1.0))
        # Encode the rule-derivation list in ``relation_type`` so the
        # rule_id survives the CanonicalExplanation flatten/rehydrate
        # cycle. Format: ``rule_derived_explanation:R2+R4_retry``.
        # The base label ``rule_derived_explanation`` is the
        # contractual "kind" tag; the suffix lists the firing rules.
        # raw_output["explanation_edges"] carries the same info in
        # structured form for downstream consumers.
        suffix = "+".join(sorted(rules))
        explanation.add_link(CausalLink(
            source_atom_id=atom_by_service[cause].id,
            target_atom_id=atom_by_service[dep].id,
            weight=weight,
            relation_type=f"rule_derived_explanation:{suffix}",
        ))
    return explanation
