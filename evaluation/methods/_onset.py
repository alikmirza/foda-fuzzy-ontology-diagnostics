"""Opt-in change-point detector for RCA methods that previously read
:class:`NormalizedCase.inject_time` directly.

This is **not** invoked by the normalization layer and **not** invoked
by :class:`RCAMethod`. Methods that want a "pre vs. post" split must
either:

* call :func:`detect_onset` explicitly on ``case.case_window``, or
* implement their own change-point detection, or
* reformulate to use window-aggregate statistics (no pivot needed).

The reference implementation here is the cheapest defensible default:
scan a small grid of candidate pivots in the ``[25 %, 75 %]`` band of
the case window, compute the aggregate z-score of post-vs-pre across
every populated canonical service-feature column, and return the
pivot that maximizes it.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


_DEFAULT_FEATURE_PRIORITY: tuple[str, ...] = (
    "latency",
    "traffic",
    "error",
    "cpu",
    "mem",
    "disk",
    "net",
)


def detect_onset(
    case_window: pd.DataFrame,
    services: Iterable[str],
    feature_priority: tuple[str, ...] = _DEFAULT_FEATURE_PRIORITY,
    pivot_low_pct:  float = 0.25,
    pivot_high_pct: float = 0.75,
    n_candidates:   int   = 30,
) -> float:
    """Return a ``time`` value that approximately separates pre- from
    post-injection in ``case_window``.

    The score for a candidate pivot ``t`` is
    ``Σ_svc Σ_feat |mean(post_t) − mean(pre_t)| / std(pre_t)``,
    summed across every available ``{service}_{feature}`` column. The
    pivot maximizing the sum wins.

    Parameters
    ----------
    case_window:
        Bounded normalized telemetry, with a ``time`` column.
    services:
        Iterable of service prefixes to consider. Typically
        ``norm.services``.
    feature_priority:
        Suffixes to consider for each service. Order is informational;
        every populated column contributes to the sum regardless.
    pivot_low_pct, pivot_high_pct:
        Restrict candidate pivots to ``[low_pct, high_pct]`` of the
        window length so we never pivot on an edge-padded sample.
    n_candidates:
        How many pivots to evaluate. Linear cost.

    Returns
    -------
    float
        The selected pivot ``time``. Falls back to the band centre
        when no candidate has any non-zero z-score (e.g. completely
        flat case).
    """
    if "time" not in case_window.columns:
        raise KeyError("case_window has no 'time' column")
    if not 0.0 <= pivot_low_pct < pivot_high_pct <= 1.0:
        raise ValueError(
            f"invalid pivot band: low={pivot_low_pct}, high={pivot_high_pct}"
        )
    if n_candidates < 1:
        raise ValueError(f"n_candidates must be >= 1, got {n_candidates}")

    times = case_window["time"].to_numpy(dtype=float)
    if times.size < 2:
        return float(times[0]) if times.size else 0.0
    t_min, t_max = float(times[0]), float(times[-1])
    t_low  = t_min + pivot_low_pct  * (t_max - t_min)
    t_high = t_min + pivot_high_pct * (t_max - t_min)
    candidates = np.linspace(t_low, t_high, n_candidates)

    columns = [
        (svc, feat, f"{svc}_{feat}")
        for svc in services
        for feat in feature_priority
        if f"{svc}_{feat}" in case_window.columns
    ]
    arrays = {col: case_window[col].to_numpy(dtype=float) for _, _, col in columns}

    best_t: float = float((t_low + t_high) * 0.5)
    best_score: float = -np.inf
    for t in candidates:
        pre_mask = times < t
        post_mask = times >= t
        if int(pre_mask.sum()) < 2 or int(post_mask.sum()) < 1:
            continue
        total = 0.0
        for _, _, col in columns:
            x = arrays[col]
            x_pre, x_post = x[pre_mask], x[post_mask]
            if x_pre.size < 2 or x_post.size < 1:
                continue
            sd = float(x_pre.std())
            if sd == 0.0:
                continue
            z = abs(float(x_post.mean()) - float(x_pre.mean())) / sd
            if np.isfinite(z):
                total += z
        if total > best_score:
            best_score = total
            best_t = float(t)
    return best_t
