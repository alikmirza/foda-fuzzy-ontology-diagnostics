"""Standalone evaluation harness for MonitorRank against RCAEval.

Runs MonitorRank on every case under ``data_path`` and reports per-
fault AC@k / MRR plus the **inject-time sensitivity** ``S(M)`` per the
inject_time-removal design
(``evaluation/extraction/DESIGN_inject_time_removal.md`` §5).

For every case the harness produces three diagnoses:

* **true** — normalize with the per-case hashed offset.
* **shift_minus** — re-normalize with ``offset' = offset − 300 s``
  if that still lies in the ``[25 %, 75 %]`` band; else NaN.
* **shift_plus**  — symmetrically for ``+300 s``.

A method whose AC@1 is *invariant* under the shift (i.e. it does not
peek at ``ground_truth.inject_time``) has ``S(M) ≈ 0``. A method that
quietly fenceposts on the side channel has ``S(M)`` close to its own
AC@1, and is flagged ``inject_time_dependent`` in the Paper-6 Section
4 method-characterization table.

The harness also calls
:func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
before iterating, so a method that *statically* references
``ground_truth`` fails fast rather than running 125 cases first.

Usage::

    python -m evaluation.experiments.evaluate_monitorrank \\
        --data ~/datasets/rcaeval/RE1/RE1-OB \\
        --out results/week2_monitorrank_validation.csv
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import math
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
from ..methods._protocol import validate_no_ground_truth_peeking
from ..methods.monitorrank import MonitorRankMethod
from ..metrics.ranking_metrics import accuracy_at_k, mean_reciprocal_rank


DEFAULT_SHIFT_SECONDS: float = 300.0
_SHIFT_FLAG_THRESHOLD: float = 0.20  # S(M) > 0.20 ⇒ flag


def evaluate(
    data_path: Path,
    top_ks: tuple[int, ...] = (1, 3, 5),
    alpha: float = 0.85,
    shift_seconds: float = DEFAULT_SHIFT_SECONDS,
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    """Run MonitorRank on every RCAEval case under ``data_path`` and
    return ``(summary, per_case_rows)``.

    The summary has one row per fault type plus ``"overall"``. Each
    row contains:

    * ``AC@k`` for every ``k`` in ``top_ks`` (averaged over cases).
    * ``MRR`` (averaged).
    * ``AC@1_shift_minus`` / ``AC@1_shift_plus`` (averaged over the
      cases where the shift was legal).
    * ``S`` — inject-time sensitivity ``mean |AC@1_true −
      mean(AC@1_shifted)|``.
    * ``S_flag`` — ``True`` when ``S > 0.20``.
    * ``n`` — case count.
    """
    loader = RCAEvalLoader(data_path)
    method = MonitorRankMethod(alpha=alpha)

    # Step 1 in the protocol: refuse to run any method that statically
    # references the ground-truth side channel from inside diagnose.
    validate_no_ground_truth_peeking(method)

    window_seconds = method.window_seconds
    band_low  = DEFAULT_INJECT_LOW_PCT  * window_seconds
    band_high = DEFAULT_INJECT_HIGH_PCT * window_seconds

    per_case: list[dict[str, Any]] = []
    by_fault: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for case in loader.iter_cases():
        row = _evaluate_one_case(
            case=case,
            method=method,
            top_ks=top_ks,
            shift_seconds=shift_seconds,
            band_low=band_low,
            band_high=band_high,
        )
        per_case.append(row)
        by_fault[row["fault"]].append(row)

    summary = _summarize(by_fault, top_ks)
    return summary, per_case


# ---- single-case ----


def _evaluate_one_case(
    case: BenchmarkCase,
    method: MonitorRankMethod,
    top_ks: tuple[int, ...],
    shift_seconds: float,
    band_low: float,
    band_high: float,
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
    return row


def _maybe_shifted_ac1(
    method: MonitorRankMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    shift: float,
    band_low: float,
    band_high: float,
) -> float:
    """Re-run ``method`` on a copy of ``norm_true`` whose ground_truth
    is shifted by ``shift`` seconds. Returns ``nan`` when the shifted
    offset would leave the ``[25 %, 75 %]`` band.

    Note: only ``ground_truth`` is shifted — ``case_window`` is
    identical between the two runs. A method that ignores
    ``ground_truth`` therefore produces identical output, which is
    exactly the invariant the shift protocol verifies."""
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


# ---- aggregation ----


def _summarize(
    by_fault: dict[str, list[dict[str, Any]]],
    top_ks: tuple[int, ...],
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
        # S(M) = mean over cases of |AC@1_true − mean(valid shifted AC@1)|.
        # Cases where both shifts are NaN are skipped from the average.
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
    fieldnames = (
        ["case_id", "fault", "ground_truth", "top1_true"]
        + [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus"]
    )
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(per_case)


def print_summary(summary: dict[str, dict[str, float]],
                  top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    if not summary:
        print("(no cases)")
        return
    metric_cols = (
        [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus", "S", "S_flag"]
    )
    header = (
        f"{'fault':<10} {'n':>4} "
        + " ".join(f"{c:>10}" for c in metric_cols)
    )
    print(header)
    print("-" * len(header))
    for fault, row in summary.items():
        cells = [f"{fault:<10}", f"{int(row['n']):>4}"]
        for col in metric_cols:
            v = row.get(col, float("nan"))
            if col == "S_flag":
                cells.append(f"{'FLAG' if v == 1.0 else 'OK':>10}")
            elif isinstance(v, float) and math.isnan(v):
                cells.append(f"{'nan':>10}")
            else:
                cells.append(f"{v:>10.3f}")
        print(" ".join(cells))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument(
        "--top-k", type=int, nargs="+", default=[1, 3, 5],
    )
    parser.add_argument("--alpha", type=float, default=0.85)
    parser.add_argument(
        "--shift", type=float, default=DEFAULT_SHIFT_SECONDS,
        help="inject-time shift in seconds (default: 300)",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="optional path to write the per-case CSV",
    )
    args = parser.parse_args(argv)

    summary, per_case = evaluate(
        data_path=args.data.expanduser(),
        top_ks=tuple(args.top_k),
        alpha=args.alpha,
        shift_seconds=args.shift,
    )
    print_summary(summary, tuple(args.top_k))
    if args.out is not None:
        write_per_case_csv(per_case, args.out, tuple(args.top_k))
        print(f"\nWrote per-case CSV to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
