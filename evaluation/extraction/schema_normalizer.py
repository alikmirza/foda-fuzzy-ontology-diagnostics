"""Cross-pipeline schema normalization for RCAEval benchmark cases.

RCAEval ships per-fault-type telemetry from two visibly different
observability pipelines. On ``RE1-OB`` the split is:

==========================  ====================  ====================
                            short pipeline        long pipeline
                            (delay/disk/loss)     (cpu/mem)
==========================  ====================  ====================
duration                    ~720 s (721 rows)     ~4200 s (4201 rows)
latency columns             ``<svc>_latency-50``, ``<svc>_latency``
                            ``<svc>_latency-90``  (single mean column)
traffic columns             ``<svc>_workload``    ``<svc>_load``
Envoy passthrough metrics   absent                ``PassthroughCluster_*``
extras                      —                     spurious ``time.1``
==========================  ====================  ====================

This module produces a :class:`NormalizedCase` with a uniform column
naming convention so downstream methods can ignore the split:

* ``{service}_latency``  — derived from ``_latency`` → ``_latency-50`` →
                            ``_latency-90`` (first that exists wins)
* ``{service}_traffic``  — derived from ``_load`` → ``_workload``
* ``{service}_error``    — passed through if present
* ``{service}_cpu`` / ``_mem`` / ``_disk`` / ``_net`` — passed through

It also crops every case to a symmetric ``[inject_time - W,
inject_time + W]`` window (default ``W=600 s``), padding with
forward-fill at the trailing edge and back-fill at the leading edge
when the window exceeds the available data. The result is a fixed-size
``2W/Δt + 1`` time grid per case regardless of the raw length, so
downstream methods can compare windows across pipelines on equal
footing.

:func:`parse_service_list` is exported for callers that only need to
enumerate services (e.g. for topology-free baselines).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from .canonical_explanation import BenchmarkCase


DEFAULT_WINDOW_SECONDS: float = 600.0

# Columns that should never be parsed as a service prefix. ``time`` and
# ``time.1`` have no underscore so they are filtered earlier; the rest
# are real columns that look service-shaped but are not microservices
# in the sense downstream methods care about.
_NON_SERVICE_PREFIXES: frozenset[str] = frozenset(
    {"PassthroughCluster", "frontend-external"}
)

# Canonical per-service feature names in their preferred ordering.
_CANONICAL_FEATURES: tuple[str, ...] = (
    "latency",
    "traffic",
    "error",
    "cpu",
    "mem",
    "disk",
    "net",
)


@dataclass
class NormalizedCase:
    """A :class:`BenchmarkCase` projected onto the canonical schema.

    Attributes
    ----------
    id:
        Case identifier, copied verbatim from the source case.
    metrics:
        DataFrame with a ``time`` column plus zero or more canonical
        per-service feature columns. Always exactly
        ``round(2 * window_seconds / dt) + 1`` rows.
    inject_time:
        Unix timestamp of the fault injection (copied from the source).
    window_start, window_end:
        Closed time interval covered by ``metrics`` (in Unix seconds).
    services:
        Sorted list of services present in the normalized frame.
    schema_summary:
        ``{canonical_feature → sorted list of services that populate it}``.
        Empty lists are kept so callers can iterate over the full key
        set without ``KeyError``.
    """

    id: str
    metrics: pd.DataFrame
    inject_time: float
    window_start: float
    window_end: float
    services: list[str]
    schema_summary: dict[str, list[str]] = field(default_factory=dict)


# ---- public API ----


def parse_service_list(case_or_df: BenchmarkCase | pd.DataFrame) -> list[str]:
    """Return the sorted set of service names present as column prefixes.

    A column is considered service-shaped when it has the form
    ``{service}_{suffix}``. The split is on the **last** underscore so
    that hyphenated names like ``ts-auth-service`` survive intact.
    ``time``, ``time.1``, ``PassthroughCluster_*`` and
    ``frontend-external_*`` are excluded by convention.
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
    case: BenchmarkCase, window_seconds: float = DEFAULT_WINDOW_SECONDS
) -> NormalizedCase:
    """Project ``case`` onto the canonical schema and crop to a
    symmetric window around the injection time.

    Raises
    ------
    KeyError
        If ``case.telemetry`` is missing ``metrics`` or ``inject_time``.
    """
    if "metrics" not in case.telemetry:
        raise KeyError(f"case {case.id!r}: telemetry has no 'metrics' DataFrame")
    if "inject_time" not in case.telemetry:
        raise KeyError(f"case {case.id!r}: telemetry has no 'inject_time'")

    raw: pd.DataFrame = case.telemetry["metrics"]
    if "time" not in raw.columns:
        raise KeyError(f"case {case.id!r}: metrics has no 'time' column")

    inject_time = float(case.telemetry["inject_time"])
    window_start = inject_time - window_seconds
    window_end = inject_time + window_seconds

    df = raw.copy()
    if "time.1" in df.columns:
        df = df.drop(columns=["time.1"])

    services = parse_service_list(df)
    canonical, summary = _build_canonical_frame(df, services)
    windowed = _apply_symmetric_window(canonical, window_start, window_end)

    return NormalizedCase(
        id=case.id,
        metrics=windowed,
        inject_time=inject_time,
        window_start=window_start,
        window_end=window_end,
        services=services,
        schema_summary=summary,
    )


# ---- helpers ----


def _metrics_df(case_or_df: BenchmarkCase | pd.DataFrame) -> pd.DataFrame:
    if isinstance(case_or_df, pd.DataFrame):
        return case_or_df
    if isinstance(case_or_df, BenchmarkCase):
        df = case_or_df.telemetry.get("metrics")
        if not isinstance(df, pd.DataFrame):
            raise KeyError(
                f"case {case_or_df.id!r}: telemetry['metrics'] is not a DataFrame"
            )
        return df
    raise TypeError(
        f"parse_service_list expected BenchmarkCase or DataFrame, "
        f"got {type(case_or_df).__name__}"
    )


def _build_canonical_frame(
    df: pd.DataFrame, services: Iterable[str]
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Construct a frame with only ``time`` + canonical service columns."""
    out: dict[str, pd.Series] = {"time": df["time"]}
    summary: dict[str, list[str]] = {feat: [] for feat in _CANONICAL_FEATURES}

    for svc in services:
        latency_src = _pick_first_present(
            df, [f"{svc}_latency", f"{svc}_latency-50", f"{svc}_latency-90"]
        )
        if latency_src is not None:
            out[f"{svc}_latency"] = df[latency_src]
            summary["latency"].append(svc)

        traffic_src = _pick_first_present(df, [f"{svc}_load", f"{svc}_workload"])
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


def _apply_symmetric_window(
    df: pd.DataFrame, window_start: float, window_end: float
) -> pd.DataFrame:
    """Crop ``df`` to ``[window_start, window_end]`` on a regular time grid.

    The grid step is inferred from the median of consecutive raw time
    diffs (with a 1.0 fallback for degenerate single-row inputs). Points
    that lie outside the raw data range are filled by forward-fill on
    the trailing edge and back-fill on the leading edge.
    """
    df = df.sort_values("time").reset_index(drop=True)
    times = df["time"].to_numpy(dtype=float)
    if len(times) >= 2:
        dt = float(np.median(np.diff(times)))
        if dt <= 0:
            dt = 1.0
    else:
        dt = 1.0

    n_steps = int(round((window_end - window_start) / dt)) + 1
    target_times = window_start + np.arange(n_steps) * dt

    indexed = df.set_index("time")
    # Drop duplicate time indices, keeping the first observation per
    # timestamp — without this, ``reindex`` raises.
    indexed = indexed[~indexed.index.duplicated(keep="first")]
    reindexed = indexed.reindex(target_times, method="ffill")
    # ``ffill`` cannot fill the leading edge (no earlier observation
    # exists); ``bfill`` handles that case.
    reindexed = reindexed.bfill()

    out = reindexed.reset_index().rename(columns={"index": "time"})
    return out
