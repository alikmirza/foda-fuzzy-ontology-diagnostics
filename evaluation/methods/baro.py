"""BARO (Pham, Ha, Zhang — Proc. ACM Softw. Eng. 1 FSE 98, July 2024)
refactored for the inject_time-clean :class:`NormalizedCase` contract.

BARO's core contribution is **multivariate Bayesian Online Change-Point
Detection (BOCPD)** on raw service metrics. Once a change point is
detected, services are scored by the magnitude of their post-change-
point shift relative to a pre-change-point baseline (a robust z-score
on each canonical feature, aggregated per service).

Unlike MonitorRank / CausalRCA / MicroRCA, BARO does **not** call
:func:`evaluation.methods._onset.detect_onset`. The shared utility is
a z-score-based onset detector; reusing it would defeat the purpose of
having BARO as a distinct method-family variant. BARO's change-point
detector is its core contribution and must be method-internal.

The detector is exposed at module scope as :func:`_detect_change_point`
so the evaluation harness can monkey-patch it for the two paper-
relevant diagnostic decompositions:

* **random-onset variant** — replace BARO's BOCPD with a uniformly-
  random in-band pivot. Isolates whether BARO's value lives in its
  change-point detector or in its scoring mechanism.
* **z-score-onset variant** — replace BARO's BOCPD with the shared
  z-score :func:`detect_onset`. Discriminates "Bayesian change-point
  detection" vs. "z-score change-point detection" as a paper axis.

BARO's :class:`CanonicalExplanation` is a trigger-event-rooted tree:
one atom for the detected change point, one atom per top-K service,
and :class:`CausalLink` edges from the change-point atom out to each
service atom carrying the service's relative shift contribution.

Deviations from the published method are recorded in ``DEVIATIONS.md``
under "BARO adapter".
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


# ---- per-service post-change shift ----


@dataclass
class _ServiceShift:
    """Per-service post-change-point shift summary.

    ``score`` is the aggregate shift magnitude across the service's
    canonical features; ``dominant_feature`` is the column that
    contributed the largest individual robust-z; ``per_feature`` is
    every feature's robust-z (for the explanation chain).
    """

    score: float = 0.0
    dominant_feature: str | None = None
    per_feature: dict[str, float] = field(default_factory=dict)


# ---- BAROMethod ----


class BAROMethod(RCAMethod):
    """BARO on :class:`NormalizedCase`.

    Parameters
    ----------
    hazard_lambda:
        Expected run length in samples. Hazard rate ``H = 1/hazard_lambda``.
        ``250`` is a defensible default for ~1 Hz telemetry on a
        20-minute window: roughly one change every four minutes,
        consistent with RCAEval's injection cadence.
    prior_var:
        Prior variance on the per-dimension mean. Wide-ish so the
        posterior is data-driven after a handful of samples.
    obs_var_floor:
        Numerical floor on the observation variance (added to the
        per-dimension variance estimated from the leading prefix of
        the window). Prevents divide-by-zero on constant signals.
    max_run_length:
        Truncate the run-length distribution to the most-recent
        ``max_run_length`` samples. Standard BOCPD optimization;
        material savings on long windows with no effect on the
        eventual change-point estimate when the true segment is
        shorter than the cap.
    aggregate:
        ``"sum"`` (default) or ``"max"`` — how to combine per-feature
        robust-z's into a per-service score.
    top_k:
        Size of the explanation head, also the denominator of the
        score-ratio confidence fallback.
    window_seconds:
        Total window length passed to :func:`normalize_case`.

    Notes
    -----
    The class deliberately does **not** import
    :func:`evaluation.methods._onset.detect_onset`. The diagnostic
    variants that reuse it (``--with-zscore-onset``) are implemented
    at the harness level by monkey-patching :func:`_detect_change_point`.
    """

    name = "baro"

    def __init__(
        self,
        hazard_lambda: float = 250.0,
        prior_var: float = 100.0,
        obs_var_floor: float = 1e-6,
        max_run_length: int = 250,
        aggregate: str = "sum",
        top_k: int = 3,
        window_seconds: float = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        if hazard_lambda <= 1.0:
            raise ValueError(
                f"hazard_lambda must be > 1, got {hazard_lambda}"
            )
        if prior_var <= 0.0:
            raise ValueError(f"prior_var must be > 0, got {prior_var}")
        if obs_var_floor <= 0.0:
            raise ValueError(
                f"obs_var_floor must be > 0, got {obs_var_floor}"
            )
        if max_run_length < 4:
            raise ValueError(
                f"max_run_length must be >= 4, got {max_run_length}"
            )
        if aggregate not in ("sum", "max"):
            raise ValueError(
                f"aggregate must be 'sum' or 'max', got {aggregate!r}"
            )
        if top_k < 1:
            raise ValueError(f"top_k must be >= 1, got {top_k}")
        if window_seconds <= 0.0:
            raise ValueError(
                f"window_seconds must be > 0, got {window_seconds}"
            )
        self.hazard_lambda = hazard_lambda
        self.prior_var = prior_var
        self.obs_var_floor = obs_var_floor
        self.max_run_length = max_run_length
        self.aggregate = aggregate
        self.top_k = top_k
        self.window_seconds = window_seconds

    # ---- public API ----

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        norm = normalize_case(case, window_seconds=self.window_seconds)
        return self.diagnose_normalized(norm)

    def diagnose_normalized(self, norm: NormalizedCase) -> DiagnosticOutput:
        """Run BARO on a pre-built :class:`NormalizedCase`.

        The harness calls this directly so it can pass a normalized
        case whose ``ground_truth`` has been deliberately shifted —
        that shift must not move the output because we never read
        ``ground_truth`` from inside ``diagnose``. The static witness
        is :mod:`evaluation.methods._protocol`.
        """
        t0 = time.perf_counter()

        if not norm.services:
            raise ValueError(
                f"BARO: case {norm.id!r} has no recognizable services "
                f"in its normalized metrics"
            )

        cp_time, cp_posterior = _detect_change_point(
            case_window=norm.case_window,
            services=norm.services,
            hazard_lambda=self.hazard_lambda,
            prior_var=self.prior_var,
            obs_var_floor=self.obs_var_floor,
            max_run_length=self.max_run_length,
        )

        shifts = _score_services(
            case_window=norm.case_window,
            services=norm.services,
            change_point_time=cp_time,
            aggregate=self.aggregate,
        )

        ranked = sorted(
            ((s, shifts[s].score) for s in norm.services),
            key=lambda kv: kv[1],
            reverse=True,
        )
        confidence = _confidence(cp_posterior, ranked)
        explanation = _build_baro_explanation(
            change_point_time=cp_time,
            change_point_posterior=cp_posterior,
            ranked=ranked,
            shifts=shifts,
            top_k=self.top_k,
        )

        raw = {
            "change_point_time": cp_time,
            "change_point_posterior": cp_posterior,
            "shift_scores": {s: shifts[s].score for s in norm.services},
            "dominant_features": {
                s: shifts[s].dominant_feature for s in norm.services
            },
            "aggregate": self.aggregate,
        }

        return DiagnosticOutput(
            ranked_list=ranked,
            explanation_chain=explanation,
            confidence=confidence,
            raw_output=raw,
            method_name=self.name,
            wall_time_ms=(time.perf_counter() - t0) * 1000.0,
        )


# ---- change-point detection (module-level so harness can monkey-patch) ----


def _detect_change_point(
    case_window: pd.DataFrame,
    services: list[str],
    hazard_lambda: float = 250.0,
    prior_var: float = 100.0,
    obs_var_floor: float = 1e-6,
    max_run_length: int = 250,
) -> tuple[float, float]:
    """Native BARO change-point detector: multivariate BOCPD on the
    standardized matrix of canonical service-feature columns.

    Returns ``(change_point_time, posterior_probability)``.

    The posterior is ``exp(log P(r_t = 0 | x_{1:t}))`` at the chosen
    ``t`` — i.e. the marginal posterior that the latest observation
    starts a new segment. If no column has non-degenerate signal the
    fallback is the window's centre with posterior 0.0.
    """
    if "time" not in case_window.columns:
        raise KeyError("case_window has no 'time' column")
    times = case_window["time"].to_numpy(dtype=float)
    if times.size < 4:
        return float(times[0]) if times.size else 0.0, 0.0

    X = _stack_signal_matrix(case_window, services)
    if X.size == 0:
        # No usable signal — fall back to window centre.
        return float(times[times.size // 2]), 0.0

    # Standardize columns so the BOCPD predictive uses comparable
    # scales across heterogeneous metrics (latency in seconds,
    # traffic in req/s, CPU as a fraction, etc.).
    X = _standardize(X)

    cp_log_probs = _bocpd_multivariate(
        X=X,
        hazard_lambda=hazard_lambda,
        prior_var=prior_var,
        obs_var_floor=obs_var_floor,
        max_run_length=max_run_length,
    )
    # Confine the argmax to the [25 %, 75 %] band — first/last quarters
    # carry boundary artefacts (the prefix is also used to estimate
    # obs_var, so a "change point" there is degenerate).
    T = cp_log_probs.size
    low, high = T // 4, max(T // 4 + 2, (3 * T) // 4)
    masked = np.full(T, -np.inf)
    masked[low:high] = cp_log_probs[low:high]
    idx = int(np.argmax(masked))
    if not np.isfinite(masked[idx]):
        return float(times[T // 2]), 0.0
    posterior = float(np.clip(np.exp(masked[idx]), 0.0, 1.0))
    return float(times[idx]), posterior


def _stack_signal_matrix(
    case_window: pd.DataFrame, services: list[str]
) -> np.ndarray:
    """Stack every populated ``{svc}_{feat}`` column into a ``T × D``
    matrix. Constant columns (zero std) are dropped — they carry no
    change-point evidence and would explode the predictive."""
    cols: list[np.ndarray] = []
    for svc in services:
        for feat in _FEATURE_PRIORITY:
            col = f"{svc}_{feat}"
            if col not in case_window.columns:
                continue
            x = case_window[col].to_numpy(dtype=float)
            if not np.isfinite(x).all():
                continue
            # Float tolerance: a column literally filled by ``np.full``
            # registers a non-zero std on the order of 1e-17. Anything
            # below 1e-12 × |median| is treated as constant.
            scale = max(1e-12, abs(float(np.median(x))) * 1e-12)
            if float(x.std()) <= scale:
                continue
            cols.append(x)
    if not cols:
        return np.empty((0, 0))
    return np.stack(cols, axis=1)


def _standardize(X: np.ndarray) -> np.ndarray:
    mean = X.mean(axis=0, keepdims=True)
    std = X.std(axis=0, keepdims=True)
    std = np.where(std > 0.0, std, 1.0)
    return (X - mean) / std


# ---- BOCPD ----


def _logsumexp(a: np.ndarray) -> float:
    a_max = float(np.max(a))
    if not np.isfinite(a_max):
        return a_max
    return a_max + float(np.log(np.sum(np.exp(a - a_max))))


def _bocpd_multivariate(
    X: np.ndarray,
    hazard_lambda: float,
    prior_var: float,
    obs_var_floor: float,
    max_run_length: int,
) -> np.ndarray:
    """Bayesian Online Change-Point Detection with a diagonal multi-
    variate Gaussian predictive (Adams & MacKay 2007, adapted).

    The predictive at run length ``r`` is per-dimension Gaussian with
    mean equal to the posterior mean given the last ``r`` samples and
    variance ``1/posterior_precision + observation_variance``. The
    log predictive across dimensions is summed — i.e. an independent
    diagonal multivariate normal.

    Parameters
    ----------
    X:
        ``T × D`` time series.
    hazard_lambda:
        Expected run length. Hazard ``H = 1/hazard_lambda``.
    prior_var:
        Prior variance on each dimension's mean.
    obs_var_floor:
        Lower bound on the per-dimension observation variance
        estimated from the first quarter of ``X``.
    max_run_length:
        Truncate the run-length distribution to this many recent
        samples after each step.

    Returns
    -------
    np.ndarray
        Length-``T`` array of log marginal posteriors
        ``log P(r_t = 0 | x_{1:t+1})``.
    """
    T, D = X.shape
    head_n = max(2, T // 4)
    obs_var = X[:head_n].var(axis=0, ddof=0) + obs_var_floor
    obs_prec = 1.0 / obs_var
    prior_prec = np.full(D, 1.0 / prior_var)
    prior_mean = np.zeros(D)

    log_H   = float(np.log(1.0 / hazard_lambda))
    log_1mH = float(np.log1p(-1.0 / hazard_lambda))

    log_R = np.array([0.0])
    means = prior_mean.reshape(1, D).copy()
    precs = prior_prec.reshape(1, D).copy()

    cp_log_probs = np.full(T, -np.inf)
    log_const = -0.5 * D * float(np.log(2.0 * np.pi))

    for t in range(T):
        x_t = X[t]
        pred_var = 1.0 / precs + obs_var
        diff = x_t - means
        log_pred = log_const + np.sum(
            -0.5 * (np.log(pred_var) + diff * diff / pred_var),
            axis=1,
        )

        growth = log_R + log_pred + log_1mH
        change = _logsumexp(log_R + log_pred + log_H)

        new_log_R = np.empty(log_R.size + 1)
        new_log_R[0] = change
        new_log_R[1:] = growth

        log_norm = _logsumexp(new_log_R)
        new_log_R = new_log_R - log_norm
        cp_log_probs[t] = new_log_R[0]

        new_mean_r = (precs * means + obs_prec * x_t) / (precs + obs_prec)
        new_prec_r = precs + obs_prec
        means = np.concatenate(
            [prior_mean.reshape(1, D), new_mean_r], axis=0
        )
        precs = np.concatenate(
            [prior_prec.reshape(1, D), new_prec_r], axis=0
        )
        log_R = new_log_R

        if log_R.size > max_run_length:
            log_R = log_R[:max_run_length]
            log_R = log_R - _logsumexp(log_R)
            means = means[:max_run_length]
            precs = precs[:max_run_length]

    return cp_log_probs


# ---- post-change-point service scoring ----


def _score_services(
    case_window: pd.DataFrame,
    services: list[str],
    change_point_time: float,
    aggregate: str,
) -> dict[str, _ServiceShift]:
    """Per-service post-change-point shift via a RobustScaler-style
    robust z (median / IQR, with the median and IQR estimated on the
    pre-change-point segment) on every canonical feature column,
    aggregated per service via ``aggregate``.

    This mirrors BARO's RobustScaler+max pattern at the column level
    and aggregates to service granularity by summing (or maxing) the
    per-feature shifts. Per-service aggregation is required because
    RCAEval RE1's ground truth is service-level, not metric-level.
    """
    df = case_window
    times = df["time"].to_numpy(dtype=float)
    pre_mask  = times <  change_point_time
    post_mask = times >= change_point_time
    out: dict[str, _ServiceShift] = {}

    for svc in services:
        shift = _ServiceShift()
        for feat in _FEATURE_PRIORITY:
            col = f"{svc}_{feat}"
            if col not in df.columns:
                continue
            x = df[col].to_numpy(dtype=float)
            x_pre  = x[pre_mask]
            x_post = x[post_mask]
            if x_pre.size < 4 or x_post.size < 1:
                continue
            z = _robust_z(x_pre, x_post)
            if not np.isfinite(z):
                continue
            shift.per_feature[feat] = z
            if z > (shift.per_feature.get(shift.dominant_feature or "", -np.inf)):
                # First feature seen, or strictly larger than the prior best.
                if shift.dominant_feature is None or z > shift.per_feature[shift.dominant_feature]:
                    shift.dominant_feature = feat
        if shift.per_feature:
            if aggregate == "sum":
                shift.score = float(sum(shift.per_feature.values()))
            else:
                shift.score = float(max(shift.per_feature.values()))
        out[svc] = shift
    return out


def _robust_z(pre: np.ndarray, post: np.ndarray) -> float:
    """``max |post − median(pre)| / IQR(pre)``.

    Numpy's RobustScaler analogue: subtract the pre-segment median,
    divide by the pre-segment inter-quartile range, take the max
    absolute value across the post segment. Falls back to the pre-
    segment standard deviation when the IQR is zero (a wholly-flat
    pre segment with a single outlier would otherwise yield
    ``inf``).
    """
    med = float(np.median(pre))
    q75, q25 = np.percentile(pre, [75.0, 25.0])
    iqr = float(q75 - q25)
    if iqr <= 0.0:
        sd = float(pre.std())
        if sd <= 0.0:
            return 0.0
        denom = sd
    else:
        denom = iqr
    return float(np.max(np.abs(post - med))) / denom


# ---- output assembly ----


def _confidence(
    change_point_posterior: float,
    ranked: list[tuple[str, float]],
) -> float:
    """Posterior probability of the detected change point when finite
    and positive; otherwise the top-1/(top-1+top-2) score ratio.

    The posterior is well-defined when the native BOCPD detector runs.
    The harness's diagnostic variants (random pivot, z-score onset)
    pass posterior=NaN — for those we use the score-ratio fallback so
    the column is still populated.
    """
    if np.isfinite(change_point_posterior) and change_point_posterior > 0.0:
        return float(np.clip(change_point_posterior, 0.0, 1.0))
    if not ranked:
        return 0.0
    top1 = max(0.0, float(ranked[0][1]))
    top2 = max(0.0, float(ranked[1][1])) if len(ranked) > 1 else 0.0
    denom = top1 + top2
    if denom <= 0.0:
        return 0.0
    return float(np.clip(top1 / denom, 0.0, 1.0))


def _build_baro_explanation(
    change_point_time: float,
    change_point_posterior: float,
    ranked: list[tuple[str, float]],
    shifts: dict[str, _ServiceShift],
    top_k: int,
) -> CanonicalExplanation:
    """Trigger-event-rooted tree: one change-point atom, ``top_k``
    service atoms, ``top_k`` causal links carrying the relative
    contribution of each service to the total head shift mass.
    """
    explanation = CanonicalExplanation()
    head = [(s, score) for s, score in ranked[:top_k] if score > 0.0]
    cp_membership = (
        float(np.clip(change_point_posterior, 0.0, 1.0))
        if np.isfinite(change_point_posterior) else None
    )
    cp_atom = ExplanationAtom(
        text=(
            f"change point at t={change_point_time:.2f} "
            f"(P(r_t=0)={change_point_posterior:.3f})"
            if np.isfinite(change_point_posterior)
            else f"change point at t={change_point_time:.2f}"
        ),
        ontology_class=None,
        fuzzy_membership=cp_membership,
    )
    explanation.add_atom(cp_atom)
    if not head:
        return explanation

    total = sum(score for _, score in head) or 1.0
    score_max = max(score for _, score in head) or 1.0
    for service, score in head:
        sh = shifts.get(service)
        feat = sh.dominant_feature if sh is not None else None
        if feat is not None:
            z = sh.per_feature.get(feat, 0.0)
            text = (
                f"{service}: post-change shift in {feat} "
                f"(robust-z={z:.2f}, score={score:.3f})"
            )
        else:
            text = f"{service}: score={score:.3f}"
        atom = ExplanationAtom(
            text=text,
            ontology_class=None,
            fuzzy_membership=float(np.clip(score / score_max, 0.0, 1.0)),
        )
        explanation.add_atom(atom)
        explanation.add_link(
            CausalLink(
                source_atom_id=cp_atom.id,
                target_atom_id=atom.id,
                weight=float(np.clip(score / total, 0.0, 1.0)),
                relation_type="post-change-shift-attribution",
            )
        )
    return explanation
