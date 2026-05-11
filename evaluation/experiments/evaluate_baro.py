"""Standalone evaluation harness for BARO against RCAEval.

Mirrors ``evaluate_microrca.py`` with two BARO-specific diagnostic
columns:

* ``AC@1_random`` — BARO's change-point detector is replaced by a
  uniformly-random in-band pivot. Isolates whether BARO's value lives
  in its detector or in its scoring mechanism.
* ``AC@1_zscore_onset`` — BARO's BOCPD is replaced by the shared
  z-score :func:`evaluation.methods._onset.detect_onset` utility.
  Discriminates "Bayesian change-point detection" vs. "z-score change-
  point detection" as a paper axis (brief §9).

Three diagnoses per case (same shape as the other harnesses):

* **true** — normalize with the per-case hashed offset.
* **shift_minus** / **shift_plus** — re-normalize with the offset
  shifted by ±300 s when the shifted offset stays in band. By
  construction BARO doesn't read ``ground_truth``, so the shifted
  AC@1 must equal the true AC@1 — that's the structural witness of
  ``S(BARO) = 0``.

The harness calls
:func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
before iterating; a method that statically references ``ground_truth``
fails fast rather than running 125 cases first.

Usage::

    python -m evaluation.experiments.evaluate_baro \\
        --data ~/datasets/rcaeval/RE1/RE1-OB \\
        --out results/week2_baro_validation.csv \\
        --with-random-onset --with-zscore-onset
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from ..benchmarks.rcaeval_loader import RCAEvalLoader
from ..extraction.canonical_explanation import BenchmarkCase
from ..extraction.schema_normalizer import (
    DEFAULT_INJECT_HIGH_PCT,
    DEFAULT_INJECT_LOW_PCT,
    NormalizedCase,
    normalize_case,
)
from ..methods import baro as baro_mod
from ..methods._onset import detect_onset
from ..methods._protocol import validate_no_ground_truth_peeking
from ..methods.baro import BAROMethod
from ..metrics.ranking_metrics import accuracy_at_k, mean_reciprocal_rank


DEFAULT_SHIFT_SECONDS: float = 300.0
_SHIFT_FLAG_THRESHOLD: float = 0.20
_RANDOM_ONSET_SEED: int = 0


def evaluate(
    data_path: Path,
    top_ks: tuple[int, ...] = (1, 3, 5),
    shift_seconds: float = DEFAULT_SHIFT_SECONDS,
    with_random_onset: bool = False,
    with_zscore_onset: bool = False,
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    """Run BARO on every RCAEval case under ``data_path``.

    Returns ``(summary, per_case_rows)``. The summary has one row per
    fault type plus ``"overall"`` with:

    * ``AC@k`` for every ``k`` in ``top_ks``.
    * ``MRR``.
    * ``AC@1_shift_minus`` / ``AC@1_shift_plus`` / ``S`` / ``S_flag``.
    * ``AC@1_random`` (when ``with_random_onset=True``).
    * ``AC@1_zscore_onset`` (when ``with_zscore_onset=True``).
    * ``n``.
    """
    loader = RCAEvalLoader(data_path)
    method = BAROMethod()

    # Protocol gate: refuse to score a leaky method.
    validate_no_ground_truth_peeking(method)

    window_seconds = method.window_seconds
    band_low  = DEFAULT_INJECT_LOW_PCT  * window_seconds
    band_high = DEFAULT_INJECT_HIGH_PCT * window_seconds

    per_case: list[dict[str, Any]] = []
    by_fault: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rng = random.Random(_RANDOM_ONSET_SEED)

    for case in loader.iter_cases():
        row = _evaluate_one_case(
            case=case,
            method=method,
            top_ks=top_ks,
            shift_seconds=shift_seconds,
            band_low=band_low,
            band_high=band_high,
            with_random_onset=with_random_onset,
            with_zscore_onset=with_zscore_onset,
            rng=rng,
        )
        per_case.append(row)
        by_fault[row["fault"]].append(row)

    summary = _summarize(
        by_fault,
        top_ks,
        with_random_onset=with_random_onset,
        with_zscore_onset=with_zscore_onset,
    )
    return summary, per_case


# ---- single-case ----


def _evaluate_one_case(
    case: BenchmarkCase,
    method: BAROMethod,
    top_ks: tuple[int, ...],
    shift_seconds: float,
    band_low: float,
    band_high: float,
    with_random_onset: bool,
    with_zscore_onset: bool,
    rng: random.Random,
) -> dict[str, Any]:
    norm_true = normalize_case(case, window_seconds=method.window_seconds)
    out_true = method.diagnose_normalized(norm_true)
    gt = case.ground_truth_root_cause
    fault = case.ground_truth_fault_type

    ac_true = {
        f"AC@{k}": float(accuracy_at_k(out_true.ranked_list, gt, k))
        for k in top_ks
    }
    mrr_true = float(mean_reciprocal_rank(out_true.ranked_list, gt))

    ac1_minus = _maybe_shifted_ac1(
        method, norm_true, gt, -shift_seconds, band_low, band_high
    )
    ac1_plus  = _maybe_shifted_ac1(
        method, norm_true, gt,  shift_seconds, band_low, band_high
    )

    row: dict[str, Any] = {
        "case_id": case.id,
        "fault": fault,
        "ground_truth": gt,
        "top1_true": out_true.ranked_list[0][0] if out_true.ranked_list else "",
        **ac_true,
        "MRR": mrr_true,
        "AC@1_shift_minus": ac1_minus,
        "AC@1_shift_plus":  ac1_plus,
    }
    if with_random_onset:
        row["AC@1_random"] = _random_onset_ac1(method, norm_true, gt, rng)
    if with_zscore_onset:
        row["AC@1_zscore_onset"] = _zscore_onset_ac1(method, norm_true, gt)
    return row


def _maybe_shifted_ac1(
    method: BAROMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    shift: float,
    band_low: float,
    band_high: float,
) -> float:
    """``nan`` when the shifted offset would leave the band; else
    AC@1 of the run with a side-channel-shifted ``ground_truth``.

    Only ``ground_truth`` shifts; ``case_window`` is identical. BARO
    does not read ``ground_truth``, so by construction the shifted
    AC@1 equals the true AC@1.
    """
    shifted_offset = norm_true.ground_truth.inject_offset_seconds + shift
    if not band_low <= shifted_offset <= band_high:
        return float("nan")
    shifted_gt = dataclasses.replace(
        norm_true.ground_truth,
        inject_time=norm_true.ground_truth.inject_time + shift,
        inject_offset_seconds=shifted_offset,
    )
    shifted_norm = dataclasses.replace(norm_true, ground_truth=shifted_gt)
    out = method.diagnose_normalized(shifted_norm)
    return float(accuracy_at_k(out.ranked_list, ground_truth, 1))


def _random_onset_ac1(
    method: BAROMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    rng: random.Random,
) -> float:
    """Re-score with BARO's change-point detector replaced by a
    uniformly-random in-band pivot.
    """
    times = norm_true.case_window["time"].to_numpy(dtype=float)
    if times.size < 2:
        return float("nan")
    t_min, t_max = float(times[0]), float(times[-1])
    t_low  = t_min + DEFAULT_INJECT_LOW_PCT  * (t_max - t_min)
    t_high = t_min + DEFAULT_INJECT_HIGH_PCT * (t_max - t_min)
    pivot = rng.uniform(t_low, t_high)
    return _ac1_with_forced_detector(
        method, norm_true, ground_truth,
        lambda case_window, services, **kwargs: (pivot, float("nan")),
    )


def _zscore_onset_ac1(
    method: BAROMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
) -> float:
    """Re-score with BARO's BOCPD replaced by the shared z-score
    :func:`detect_onset` utility — the brief §9 diagnostic.
    """
    return _ac1_with_forced_detector(
        method, norm_true, ground_truth,
        lambda case_window, services, **kwargs: (
            detect_onset(case_window, services), float("nan")
        ),
    )


def _ac1_with_forced_detector(
    method: BAROMethod,
    norm: NormalizedCase,
    ground_truth: str,
    detector,
) -> float:
    """Monkey-patch :func:`_detect_change_point` in the baro module for
    a single call so we can force a known change-point timestamp
    without teaching the method an extra argument it shouldn't carry.
    """
    original = baro_mod._detect_change_point
    baro_mod._detect_change_point = detector
    try:
        out = method.diagnose_normalized(norm)
    finally:
        baro_mod._detect_change_point = original
    return float(accuracy_at_k(out.ranked_list, ground_truth, 1))


# ---- aggregation ----


def _summarize(
    by_fault: dict[str, list[dict[str, Any]]],
    top_ks: tuple[int, ...],
    with_random_onset: bool,
    with_zscore_onset: bool,
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}

    def _agg(rows: list[dict[str, Any]]) -> dict[str, float]:
        out: dict[str, float] = {f"AC@{k}": mean(r[f"AC@{k}"] for r in rows)
                                 for k in top_ks}
        out["MRR"] = mean(r["MRR"] for r in rows)
        ac1_minus_valid = [r["AC@1_shift_minus"] for r in rows
                           if not math.isnan(r["AC@1_shift_minus"])]
        ac1_plus_valid  = [r["AC@1_shift_plus"]  for r in rows
                           if not math.isnan(r["AC@1_shift_plus"])]
        out["AC@1_shift_minus"] = (
            mean(ac1_minus_valid) if ac1_minus_valid else float("nan")
        )
        out["AC@1_shift_plus"] = (
            mean(ac1_plus_valid) if ac1_plus_valid else float("nan")
        )
        deltas: list[float] = []
        for r in rows:
            shifts = [r["AC@1_shift_minus"], r["AC@1_shift_plus"]]
            shifts_valid = [s for s in shifts if not math.isnan(s)]
            if not shifts_valid:
                continue
            deltas.append(abs(r["AC@1"] - mean(shifts_valid)))
        out["S"] = mean(deltas) if deltas else float("nan")
        out["S_flag"] = (
            float(out["S"] > _SHIFT_FLAG_THRESHOLD)
            if not math.isnan(out["S"])
            else float("nan")
        )
        if with_random_onset:
            rand_valid = [
                r["AC@1_random"] for r in rows
                if not math.isnan(r.get("AC@1_random", float("nan")))
            ]
            out["AC@1_random"] = (
                mean(rand_valid) if rand_valid else float("nan")
            )
        if with_zscore_onset:
            zs_valid = [
                r["AC@1_zscore_onset"] for r in rows
                if not math.isnan(r.get("AC@1_zscore_onset", float("nan")))
            ]
            out["AC@1_zscore_onset"] = (
                mean(zs_valid) if zs_valid else float("nan")
            )
        out["n"] = float(len(rows))
        return out

    for fault, rows in sorted(by_fault.items()):
        summary[fault] = _agg(rows)

    all_rows = [r for rs in by_fault.values() for r in rs]
    if all_rows:
        summary["overall"] = _agg(all_rows)
    return summary


# ---- CLI / printing ----


def write_per_case_csv(per_case: list[dict[str, Any]], path: Path,
                       top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base_fields = (
        ["case_id", "fault", "ground_truth", "top1_true"]
        + [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus"]
    )
    has_random = any("AC@1_random" in r for r in per_case)
    has_zscore = any("AC@1_zscore_onset" in r for r in per_case)
    fieldnames = (
        base_fields
        + (["AC@1_random"] if has_random else [])
        + (["AC@1_zscore_onset"] if has_zscore else [])
    )
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(per_case)


def print_summary(summary: dict[str, dict[str, float]],
                  top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    if not summary:
        print("(no cases)")
        return
    has_random = any("AC@1_random" in row for row in summary.values())
    has_zscore = any("AC@1_zscore_onset" in row for row in summary.values())
    metric_cols = (
        [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus", "S", "S_flag"]
        + (["AC@1_random"] if has_random else [])
        + (["AC@1_zscore_onset"] if has_zscore else [])
    )
    header = (
        f"{'fault':<10} {'n':>4} "
        + " ".join(f"{c:>17}" for c in metric_cols)
    )
    print(header)
    print("-" * len(header))
    for fault, row in summary.items():
        cells = [f"{fault:<10}", f"{int(row['n']):>4}"]
        for col in metric_cols:
            v = row.get(col, float("nan"))
            if col == "S_flag":
                cells.append(f"{'FLAG' if v == 1.0 else 'OK':>17}")
            elif isinstance(v, float) and math.isnan(v):
                cells.append(f"{'nan':>17}")
            else:
                cells.append(f"{v:>17.3f}")
        print(" ".join(cells))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument(
        "--shift", type=float, default=DEFAULT_SHIFT_SECONDS,
        help="inject-time shift in seconds (default: 300)",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="optional path to write the per-case CSV",
    )
    parser.add_argument(
        "--with-random-onset", action="store_true",
        help=(
            "additionally compute AC@1 with a uniformly-random in-band "
            "change point (detector-vs-scoring decomposition)"
        ),
    )
    parser.add_argument(
        "--with-zscore-onset", action="store_true",
        help=(
            "additionally compute AC@1 with BARO's BOCPD replaced by "
            "the shared z-score detect_onset utility (brief §9 "
            "change-point-detector comparison)"
        ),
    )
    args = parser.parse_args(argv)

    summary, per_case = evaluate(
        data_path=args.data.expanduser(),
        top_ks=tuple(args.top_k),
        shift_seconds=args.shift,
        with_random_onset=args.with_random_onset,
        with_zscore_onset=args.with_zscore_onset,
    )
    print_summary(summary, tuple(args.top_k))
    if args.out is not None:
        write_per_case_csv(per_case, args.out, tuple(args.top_k))
        print(f"\nWrote per-case CSV to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
