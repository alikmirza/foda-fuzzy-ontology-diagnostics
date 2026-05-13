"""ConfidenceCalibration — does a method's reported confidence track its
empirical top-1 accuracy across cases?

This is the fourth and final Paper 6 Phase 2 semantic-quality metric, and
the only one in the suite where **lower scores are better**. The metric
is the standard Expected Calibration Error (ECE): partition cases into
``n_bins`` equal-width buckets along the confidence axis, then average
``|mean(confidence) − mean(accuracy)|`` over the buckets, weighted by
bucket population. ECE ∈ [0, 1]; ECE = 0 is perfect calibration.

Aggregate-only contract (Option A)
----------------------------------

Unlike SemanticGroundedness, SemanticCoherence, and ExplanationCompleteness
— each of which scores a single :class:`CanonicalExplanation` per case
— calibration is fundamentally an **aggregate** property of a method
across a set of cases. A single (confidence, correct) pair carries no
calibration information: "0.8 confidence, correct" is well-calibrated
iff *across* high-confidence cases the accuracy averages near 0.8. ECE
is not naturally decomposable per-case.

Rather than force a fictional per-case score that doesn't sum to the
aggregate, this module ships ConfidenceCalibration as a **standalone
analyzer** that consumes a list of case-result dicts. It deliberately
does NOT subclass :class:`SemanticMetric` — its interface is
``compute_ece(case_results, n_bins) -> float`` and
``compute_reliability_diagram(case_results, n_bins) -> dict``, not the
``(explanation, ontology) -> float`` signature the other three Phase 2
metrics share. The architectural asymmetry is documented in
DEVIATIONS.md → "ConfidenceCalibration metric (Paper 6 Phase 2 Week 4)".

For per-case correlation analysis (Spearman against AC@1 / SG / SC / EC),
callers use :func:`per_case_calibration_error`:

    cal_err = |confidence − (1.0 if correct else 0.0)|

This per-case proxy is 0 when high confidence matches correctness or
low confidence matches incorrectness, and large when they mismatch. It
is NOT identical to ECE (the bucketed averaging is what makes ECE a
calibration metric rather than a Brier-style scoring rule), but it
preserves the directionally-relevant signal at the per-case granularity
that cross-metric correlation analysis requires.

Inputs
------

A ``CaseResult`` is a plain ``dict`` (or any mapping) with at least:

* ``confidence``: ``float`` in [0, 1] — the method's reported confidence
  on this case.
* ``correct``: ``bool`` (or 0/1) — whether the method's top-1
  prediction matches the case's ground truth.

Additional keys (``method``, ``fault``, ``case_id``, …) are ignored by
this module; callers are expected to filter/group case results by those
keys before passing them in.

Buckets
-------

``n_bins`` equal-width buckets span [0.0, 1.0]. Bucket edges are
``[0.0, 1/n_bins, 2/n_bins, ..., 1.0]``. A confidence value of exactly
0.0 falls into bucket 0; a confidence of exactly 1.0 falls into the
last bucket (right edge inclusive). The default ``n_bins = 10`` matches
common ECE conventions in the calibration literature.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


#: Default bin count used by ECE / reliability-diagram. Ten equal-width
#: buckets across [0, 1] is the convention in Guo et al. 2017
#: ("On Calibration of Modern Neural Networks") and matches the
#: reliability-diagram resolution Paper 6 reports in the findings note.
_DEFAULT_N_BINS: int = 10


def _bucket_index(confidence: float, n_bins: int) -> int:
    """Return the bucket index in ``[0, n_bins - 1]`` for ``confidence``.

    Right-edge inclusive at 1.0 — a confidence of exactly 1.0 lands in
    bucket ``n_bins - 1``, not in a (non-existent) bucket ``n_bins``.
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(
            f"confidence must be in [0, 1], got {confidence}"
        )
    if confidence >= 1.0:
        return n_bins - 1
    idx = int(confidence * n_bins)
    return min(idx, n_bins - 1)


def _coerce_pair(result: Mapping[str, Any]) -> tuple[float, float]:
    """Extract ``(confidence, correct)`` from a case-result mapping.

    ``correct`` is coerced to a float in {0.0, 1.0} so it averages
    cleanly inside a bucket. Raises ``KeyError`` if either column is
    missing; this is a programming error, not a data condition.
    """
    conf = float(result["confidence"])
    correct = 1.0 if bool(result["correct"]) else 0.0
    return conf, correct


def compute_ece(
    case_results: Sequence[Mapping[str, Any]],
    n_bins: int = _DEFAULT_N_BINS,
) -> float:
    """Expected Calibration Error across a set of case results.

    Returns ECE in [0, 1]; 0 means perfectly calibrated. An empty
    ``case_results`` returns ``nan`` (no evidence to score, distinct
    from "perfectly calibrated").
    """
    if n_bins < 1:
        raise ValueError(f"n_bins must be ≥ 1, got {n_bins}")
    n_total = len(case_results)
    if n_total == 0:
        return float("nan")

    bucket_conf_sum = [0.0] * n_bins
    bucket_acc_sum = [0.0] * n_bins
    bucket_count = [0] * n_bins
    for r in case_results:
        conf, correct = _coerce_pair(r)
        b = _bucket_index(conf, n_bins)
        bucket_conf_sum[b] += conf
        bucket_acc_sum[b] += correct
        bucket_count[b] += 1

    ece = 0.0
    for b in range(n_bins):
        c = bucket_count[b]
        if c == 0:
            continue
        avg_conf = bucket_conf_sum[b] / c
        avg_acc = bucket_acc_sum[b] / c
        gap = abs(avg_conf - avg_acc)
        weight = c / n_total
        ece += weight * gap
    return ece


def compute_reliability_diagram(
    case_results: Sequence[Mapping[str, Any]],
    n_bins: int = _DEFAULT_N_BINS,
) -> dict[str, Any]:
    """Reliability-diagram data for a set of case results.

    Returns a dict shaped for downstream plotting and over/under-
    confidence summarisation:

    * ``bin_edges`` — ``n_bins + 1`` equal-width edges in [0, 1].
    * ``bin_centers`` — ``n_bins`` midpoints (``(edge_i + edge_i+1)/2``).
    * ``bin_counts`` — ``n_bins`` ints (cases per bucket).
    * ``bin_avg_confidence`` — per-bucket mean confidence, or ``nan``
      for empty buckets.
    * ``bin_accuracy`` — per-bucket mean accuracy, or ``nan`` for
      empty buckets.
    * ``overconfidence_bins`` — count of non-empty buckets where
      ``avg_confidence > accuracy``.
    * ``underconfidence_bins`` — count of non-empty buckets where
      ``avg_confidence < accuracy``.

    A reliability diagram is well-calibrated when the per-bucket
    ``avg_confidence`` ≈ ``accuracy`` across all non-empty buckets;
    the over / under-confidence bin counts give a quick read on which
    failure mode (if any) dominates.
    """
    if n_bins < 1:
        raise ValueError(f"n_bins must be ≥ 1, got {n_bins}")

    edges = [i / n_bins for i in range(n_bins + 1)]
    centers = [(edges[i] + edges[i + 1]) / 2.0 for i in range(n_bins)]

    bucket_conf_sum = [0.0] * n_bins
    bucket_acc_sum = [0.0] * n_bins
    bucket_count = [0] * n_bins
    for r in case_results:
        conf, correct = _coerce_pair(r)
        b = _bucket_index(conf, n_bins)
        bucket_conf_sum[b] += conf
        bucket_acc_sum[b] += correct
        bucket_count[b] += 1

    avg_conf: list[float] = []
    avg_acc: list[float] = []
    over = 0
    under = 0
    for b in range(n_bins):
        c = bucket_count[b]
        if c == 0:
            avg_conf.append(float("nan"))
            avg_acc.append(float("nan"))
            continue
        ac = bucket_conf_sum[b] / c
        aa = bucket_acc_sum[b] / c
        avg_conf.append(ac)
        avg_acc.append(aa)
        if ac > aa:
            over += 1
        elif ac < aa:
            under += 1

    return {
        "bin_edges": edges,
        "bin_centers": centers,
        "bin_counts": list(bucket_count),
        "bin_avg_confidence": avg_conf,
        "bin_accuracy": avg_acc,
        "overconfidence_bins": over,
        "underconfidence_bins": under,
    }


def per_case_calibration_error(
    confidence: float,
    correct: bool,
) -> float:
    """Per-case calibration-error proxy: ``|confidence − target|``.

    ``target`` is ``1.0`` if ``correct`` else ``0.0``. The result is
    in [0, 1]: zero when confidence and correctness agree (high-conf +
    correct, or low-conf + wrong), and approaches one when they
    mismatch (high-conf + wrong, or low-conf + correct).

    Used for **per-case** cross-metric correlation analysis only —
    aggregate calibration should be reported via :func:`compute_ece`,
    which uses bucketed averaging rather than per-case absolute error.
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(
            f"confidence must be in [0, 1], got {confidence}"
        )
    target = 1.0 if correct else 0.0
    return abs(confidence - target)


class ConfidenceCalibration:
    """Standalone aggregate analyzer for confidence calibration (Option A).

    Deliberately not a :class:`SemanticMetric` subclass: ECE is an
    aggregate property of a method across a set of cases, not a per-
    explanation score. See the module docstring and DEVIATIONS.md for
    the architectural rationale.

    The class is a thin wrapper around :func:`compute_ece` and
    :func:`compute_reliability_diagram` that holds the ``n_bins``
    parameter as instance state — convenient for the harness where the
    same configuration is reused across many method / fault subsets.
    """

    name = "confidence_calibration"

    def __init__(self, n_bins: int = _DEFAULT_N_BINS) -> None:
        if n_bins < 1:
            raise ValueError(f"n_bins must be ≥ 1, got {n_bins}")
        self.n_bins = n_bins

    def ece(self, case_results: Sequence[Mapping[str, Any]]) -> float:
        return compute_ece(case_results, n_bins=self.n_bins)

    def reliability_diagram(
        self,
        case_results: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        return compute_reliability_diagram(
            case_results, n_bins=self.n_bins,
        )

    def summarize(
        self,
        case_results: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """ECE + mean confidence + mean accuracy + over/under counts.

        Convenience for the harness: a single call returns everything
        the per-method / per-fault summary table needs. Returns
        ``nan`` aggregates on empty input rather than raising, so the
        harness can elide empty buckets cleanly.
        """
        n = len(case_results)
        if n == 0:
            return {
                "n_cases": 0,
                "ece": float("nan"),
                "mean_confidence": float("nan"),
                "mean_accuracy": float("nan"),
                "overconfidence_bins": 0,
                "underconfidence_bins": 0,
            }
        pairs = [_coerce_pair(r) for r in case_results]
        mean_conf = sum(c for c, _ in pairs) / n
        mean_acc = sum(a for _, a in pairs) / n
        diag = compute_reliability_diagram(case_results, n_bins=self.n_bins)
        return {
            "n_cases": n,
            "ece": compute_ece(case_results, n_bins=self.n_bins),
            "mean_confidence": mean_conf,
            "mean_accuracy": mean_acc,
            "overconfidence_bins": diag["overconfidence_bins"],
            "underconfidence_bins": diag["underconfidence_bins"],
        }


# Re-export so callers can ``from .confidence_calibration import isnan``
# without pulling stdlib directly. The harness uses isnan for printing.
isnan = math.isnan
