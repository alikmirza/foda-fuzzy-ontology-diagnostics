"""Cross-pipeline schema normalization for RCAEval benchmark cases.

This module turns a heterogeneously-shaped :class:`BenchmarkCase` into
a :class:`NormalizedCase` whose telemetry is bounded in time and
canonical in column naming, suitable for direct consumption by RCA
methods. Two design constraints govern the layer:

1. **No inject_time leakage.** :class:`NormalizedCase` does NOT expose
   ``inject_time`` on its method-facing surface. The injection
   timestamp lives on :class:`CaseGroundTruth`, a side channel that
   only the evaluation harness should read. Accessing
   ``case.inject_time`` raises ``AttributeError`` with a pointer to
   the side-channel field. The bounded telemetry frame is exposed as
   ``case.case_window`` (not ``case.metrics``) to make the
   "this is a fixed slice" semantics impossible to miss.
2. **Cross-pipeline schema uniformity.** RCAEval RE1 ships per-fault
   telemetry from two visibly different observability pipelines (one
   with percentile latencies and `_workload`, the other with mean
   latency and `_load`, plus the Envoy `PassthroughCluster_*` extras
   and a spurious `time.1`). The canonical schema is::

       {service}_latency  — mean latency. Derived: `_latency` →
                            `_latency-50` → `_latency-90`.
       {service}_traffic  — request rate. Derived: `_traffic` →
                            `_load` → `_workload`.
       {service}_error    — passed through if present.
       {service}_cpu / _mem / _disk / _net — passed through.

The window itself is constructed by:

* Picking a per-case **inject offset** in ``[25 %, 75 %]`` of the
  window length, derived from a SHA-256 of ``f"{case.id}|{window_seconds}"``.
  The randomization defeats methods that would otherwise pivot on
  ``window_centre`` as a proxy for ``inject_time``.
* Cropping to ``[inject_time − offset, inject_time − offset +
  window_seconds]``.
* Resampling onto a regular grid at the median raw sampling interval
  with **linear interpolation** (`interpolate(method="index")`) for
  in-range points, and forward-/back-fill for points that fall past
  the raw data edges.
* Refusing to resample if more than 20 % of consecutive raw intervals
  deviate by more than 50 % from the median — that signals corrupt or
  irregular sampling that linear interpolation cannot honestly bridge.

See ``evaluation/extraction/DESIGN_inject_time_removal.md`` for the
why-it-is-this-way write-up and ``DEVIATIONS.md`` for the deviation
from prior published RCA pipelines that assume the inject time is an
algorithm input.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from .canonical_explanation import BenchmarkCase


DEFAULT_WINDOW_SECONDS: float = 1200.0
DEFAULT_INJECT_LOW_PCT:  float = 0.25
DEFAULT_INJECT_HIGH_PCT: float = 0.75
_MAX_IRREGULAR_FRACTION: float = 0.20  # >20% irregular intervals ⇒ refuse


_NON_SERVICE_PREFIXES: frozenset[str] = frozenset(
    {"PassthroughCluster", "frontend-external"}
)

_CANONICAL_FEATURES: tuple[str, ...] = (
    "latency",
    "traffic",
    "error",
    "cpu",
    "mem",
    "disk",
    "net",
)


# ---- dataclasses ----


@dataclass(frozen=True)
class CaseGroundTruth:
    """Labels available ONLY to the evaluation harness.

    Methods that import this class or read its fields from inside
    :func:`RCAMethod.diagnose` are by definition not deployable.
    ``evaluation.methods._protocol.validate_no_ground_truth_peeking``
    AST-walks each method before its first scoring run and fails the
    method with :class:`ProtocolViolationError` if it touches this
    field.
    """

    inject_time: float
    inject_offset_seconds: float
    root_cause_service: str
    fault_type: str


@dataclass(frozen=True)
class NormalizedCase:
    """Telemetry presented to RCA methods.

    Methods may read every field on this object EXCEPT
    :attr:`ground_truth`. The case_window frame is a regularly-sampled
    slice of fixed length whose inject point sits at a per-case random
    offset in [25 %, 75 %] of the window — there is no fencepost a
    method can exploit to find ``inject_time`` without doing its own
    change-point detection.
    """

    id: str
    case_window: pd.DataFrame
    window_start: float
    window_end:   float
    sampling_dt:  float
    services: list[str]
    schema_summary: dict[str, list[str]]
    ground_truth: CaseGroundTruth

    # The two attribute names below were on the previous flat
    # ``NormalizedCase`` and would silently leak if we kept them as
    # aliases. ``__getattr__`` is consulted only when normal attribute
    # lookup fails, so the defined fields (``case_window``,
    # ``ground_truth``, …) resolve normally; only the removed names
    # land here.
    def __getattr__(self, name: str) -> object:
        if name == "inject_time":
            raise AttributeError(
                "inject_time was removed from NormalizedCase to prevent "
                "fenceposting leakage. For evaluation only, read "
                "NormalizedCase.ground_truth.inject_time via the "
                "evaluation harness."
            )
        if name == "metrics":
            raise AttributeError(
                "NormalizedCase.metrics was renamed to "
                "NormalizedCase.case_window to emphasize that the frame "
                "is a bounded slice, not unbounded telemetry."
            )
        raise AttributeError(name)


# ---- offset selection ----


def default_inject_offset_seconds(
    case_id: str,
    window_seconds: float,
    low_pct:  float = DEFAULT_INJECT_LOW_PCT,
    high_pct: float = DEFAULT_INJECT_HIGH_PCT,
) -> float:
    """Pick a deterministic injection offset in
    ``[low_pct * window_seconds, high_pct * window_seconds]`` from the
    SHA-256 of ``f"{case_id}|{window_seconds}"``.

    Hashing on both ``case_id`` and ``window_seconds`` means that
    changing the window length re-randomizes the placement — methods
    cannot memoize the offset for a given case id across runs at
    different window sizes.
    """
    if low_pct < 0.0 or high_pct > 1.0 or low_pct >= high_pct:
        raise ValueError(
            f"invalid offset band: low_pct={low_pct}, high_pct={high_pct}"
        )
    h = hashlib.sha256(f"{case_id}|{window_seconds}".encode("utf-8")).digest()
    u = int.from_bytes(h[:8], "big") / (1 << 64)
    return float(window_seconds * (low_pct + (high_pct - low_pct) * u))


# ---- public API ----


def parse_service_list(case_or_df: BenchmarkCase | pd.DataFrame) -> list[str]:
    """Return the sorted set of service names present as column prefixes.

    A column ``{service}_{suffix}`` contributes ``service`` (split on
    the **last** underscore so hyphenated names like
    ``ts-auth-service`` survive intact). Excluded by convention:
    ``time``, ``time.1``, ``PassthroughCluster_*``,
    ``frontend-external_*``.
    """
    df = _metrics_df(case_or_df)
    services: set[str] = set()
    for col in df.columns:
        if col in {"time", "time.1"}:
            continue
        if "_" not in col:
            continue
        service = col.rsplit("_", 1)[0]
        if service in _NON_SERVICE_PREFIXES:
            continue
        services.add(service)
    return sorted(services)


def normalize_case(
    case: BenchmarkCase,
    window_seconds: float = DEFAULT_WINDOW_SECONDS,
    inject_offset_seconds: float | None = None,
) -> NormalizedCase:
    """Project ``case`` onto the canonical schema and crop to a
    randomly-positioned window around the (hidden) injection time.

    Parameters
    ----------
    case:
        Source benchmark case. Must carry ``telemetry["metrics"]``
        (DataFrame with a ``time`` column) and
        ``telemetry["inject_time"]``.
    window_seconds:
        Total length of the produced window. Default 1200 s. The
        produced ``case_window`` has ``window_seconds / sampling_dt
        + 1`` rows.
    inject_offset_seconds:
        Override the per-case hashed offset. Caller is **only** the
        evaluation harness (e.g. for the ±300 s shift-evaluation
        protocol); methods MUST NOT supply this.

    Raises
    ------
    KeyError
        ``telemetry`` lacks ``metrics``, ``inject_time``, or a ``time``
        column.
    ValueError
        Explicit ``inject_offset_seconds`` is outside ``[0, window_seconds]``,
        or the raw sampling is too irregular (>20 % of consecutive raw
        intervals deviate >50 % from the median dt).
    """
    if "metrics" not in case.telemetry:
        raise KeyError(f"case {case.id!r}: telemetry has no 'metrics' DataFrame")
    if "inject_time" not in case.telemetry:
        raise KeyError(f"case {case.id!r}: telemetry has no 'inject_time'")

    raw: pd.DataFrame = case.telemetry["metrics"]
    if "time" not in raw.columns:
        raise KeyError(f"case {case.id!r}: metrics has no 'time' column")

    inject_time = float(case.telemetry["inject_time"])

    if inject_offset_seconds is None:
        offset = default_inject_offset_seconds(case.id, window_seconds)
    else:
        offset = float(inject_offset_seconds)
        if not (0.0 <= offset <= window_seconds):
            raise ValueError(
                f"inject_offset_seconds={offset} is outside "
                f"[0, window_seconds={window_seconds}]"
            )

    window_start = inject_time - offset
    window_end   = window_start + window_seconds

    df = raw.copy()
    if "time.1" in df.columns:
        df = df.drop(columns=["time.1"])

    services = parse_service_list(df)
    canonical, summary = _build_canonical_frame(df, services)
    case_window, sampling_dt = _resample_to_window(
        canonical, window_start, window_end
    )

    return NormalizedCase(
        id=case.id,
        case_window=case_window,
        window_start=window_start,
        window_end=window_end,
        sampling_dt=sampling_dt,
        services=services,
        schema_summary=summary,
        ground_truth=CaseGroundTruth(
            inject_time=inject_time,
            inject_offset_seconds=offset,
            root_cause_service=case.ground_truth_root_cause,
            fault_type=case.ground_truth_fault_type,
        ),
    )


# ---- internal: canonical-column construction ----


def _metrics_df(case_or_df: BenchmarkCase | pd.DataFrame) -> pd.DataFrame:
    if isinstance(case_or_df, pd.DataFrame):
        return case_or_df
    if isinstance(case_or_df, BenchmarkCase):
        df = case_or_df.telemetry.get("metrics")
        if not isinstance(df, pd.DataFrame):
            raise KeyError(
                f"case {case_or_df.id!r}: telemetry['metrics'] is not a "
                f"DataFrame"
            )
        return df
    raise TypeError(
        f"parse_service_list expected BenchmarkCase or DataFrame, "
        f"got {type(case_or_df).__name__}"
    )


def _build_canonical_frame(
    df: pd.DataFrame, services: Iterable[str]
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    out: dict[str, pd.Series] = {"time": df["time"]}
    summary: dict[str, list[str]] = {feat: [] for feat in _CANONICAL_FEATURES}

    for svc in services:
        latency_src = _pick_first_present(
            df,
            [f"{svc}_latency", f"{svc}_latency-50", f"{svc}_latency-90"],
        )
        if latency_src is not None:
            out[f"{svc}_latency"] = df[latency_src]
            summary["latency"].append(svc)

        traffic_src = _pick_first_present(
            df,
            [f"{svc}_traffic", f"{svc}_load", f"{svc}_workload"],
        )
        if traffic_src is not None:
            out[f"{svc}_traffic"] = df[traffic_src]
            summary["traffic"].append(svc)

        for resource in ("error", "cpu", "mem", "disk", "net"):
            col = f"{svc}_{resource}"
            if col in df.columns:
                out[col] = df[col]
                summary[resource].append(svc)

    for feat in summary:
        summary[feat].sort()
    return pd.DataFrame(out), summary


def _pick_first_present(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ---- internal: resampling ----


def _resample_to_window(
    df: pd.DataFrame, window_start: float, window_end: float
) -> tuple[pd.DataFrame, float]:
    """Resample ``df`` onto a regular grid at the median sampling
    interval. Points inside the raw time range get **linear
    interpolation** (``interpolate(method="index")``); points past the
    raw edges get forward-/back-fill.

    Raises ``ValueError`` when more than 20 % of consecutive raw
    intervals deviate by more than 50 % from the median — linear
    interpolation across larger gaps would silently invent data.
    """
    df = df.dropna(subset=["time"]).sort_values("time").reset_index(drop=True)
    times = df["time"].to_numpy(dtype=float)

    if len(times) >= 2:
        diffs = np.diff(times)
        dt = float(np.median(diffs))
        if not np.isfinite(dt) or dt <= 0:
            dt = 1.0
        irregular = int(np.sum(np.abs(diffs - dt) > 0.5 * dt))
        if irregular / len(diffs) > _MAX_IRREGULAR_FRACTION:
            raise ValueError(
                f"raw sampling too irregular: {irregular}/{len(diffs)} "
                f"({irregular / len(diffs):.1%}) of consecutive intervals "
                f"deviate >50% from the median dt={dt}; >20% irregular ⇒ "
                f"refusing to interpolate."
            )
    else:
        dt = 1.0

    n_steps = int(round((window_end - window_start) / dt)) + 1
    target_times = window_start + np.arange(n_steps) * dt

    indexed = df.set_index("time")
    indexed = indexed[~indexed.index.duplicated(keep="first")]

    # Linear interpolation: take the union of raw and target indices,
    # interpolate by index distance, then drop back to the target rows.
    target_index = pd.Index(target_times, name="time")
    union_index = indexed.index.union(target_index)
    reindexed = indexed.reindex(union_index).sort_index()
    interpolated = reindexed.interpolate(method="index")

    out = interpolated.reindex(target_index)
    # Edge padding past the raw range cannot interpolate (no surrounding
    # values); ffill the trailing edge and bfill the leading edge.
    out = out.ffill().bfill()
    out = out.reset_index()
    return out, dt
