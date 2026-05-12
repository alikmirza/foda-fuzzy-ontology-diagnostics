"""Standalone evaluation harness for FODA-FCP against RCAEval.

Mirrors ``evaluate_yrca.py`` with two FODA-FCP-specific diagnostic
axes plus the standard Paper 6 §4 offset-robustness columns:

* ``AC@1_random`` — FODA-FCP's :func:`detect_onset` is replaced by a
  uniformly-random in-band pivot. Detector-vs-rule-engine
  decomposition (analogous to yRCA's: does the value come from the
  onset detector or from the Mamdani+propagation pipeline?).

* ``AC@1_a_standard`` / ``AC@1_b_edge_left`` / ``AC@1_b_edge_right`` /
  ``AC@1_b_edges_mean`` / ``AC@1_c_centered`` — re-normalize each
  case with the inject offset placed at the per-case hashed default,
  the two band extremes (5 % / 95 %), and the band centre (50 %).
  The offset-robustness diagnostic; see ``paper/notes/findings.md``
  → "Universal edge fragility" for the cross-method observation.

Three diagnoses per case (shape shared with the other harnesses):

* **true** — normalize with the per-case hashed offset.
* **shift_minus** / **shift_plus** — re-normalize with the
  ``ground_truth`` shifted by ±300 s while ``case_window`` stays
  identical. FODA-FCP never reads ``ground_truth``, so the shifted
  AC@1 equals the true AC@1 — the structural witness of
  ``S(FODA-FCP) = 0``.

The harness calls
:func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
before iterating; a method that statically references ``ground_truth``
fails fast rather than running 125 cases first.

Usage::

    python -m evaluation.experiments.evaluate_foda_fcp \\
        --data ~/datasets/rcaeval/RE1/RE1-OB \\
        --out results/week2_foda_fcp_validation.csv \\
        --append-offset-diagnostic results/cross_method_offset_diagnostic.csv \\
        --with-random-onset --with-offset-robustness
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
from ..methods import foda_fcp as foda_fcp_mod
from ..methods._protocol import validate_no_ground_truth_peeking
from ..methods.foda_fcp import FodaFCPMethod
from ..metrics.ranking_metrics import accuracy_at_k, mean_reciprocal_rank


DEFAULT_SHIFT_SECONDS: float = 300.0
_SHIFT_FLAG_THRESHOLD: float = 0.20
_RANDOM_ONSET_SEED: int = 0

_OFFSET_EDGE_LEFT_PCT:  float = 0.05
_OFFSET_EDGE_RIGHT_PCT: float = 0.95
_OFFSET_CENTERED_PCT:   float = 0.50


def evaluate(
    data_path: Path,
    top_ks: tuple[int, ...] = (1, 3, 5),
    shift_seconds: float = DEFAULT_SHIFT_SECONDS,
    with_random_onset: bool = False,
    with_offset_robustness: bool = False,
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]]]:
    """Run FODA-FCP on every RCAEval case under ``data_path``.

    Returns ``(summary, per_case_rows)``. The summary has one row per
    fault type plus ``"overall"`` with:

    * ``AC@k`` for every ``k`` in ``top_ks``.
    * ``MRR``.
    * ``AC@1_shift_minus`` / ``AC@1_shift_plus`` / ``S`` / ``S_flag``.
    * ``AC@1_random`` (when ``with_random_onset=True``).
    * ``AC@1_a_standard`` / ``AC@1_b_edge_left`` /
      ``AC@1_b_edge_right`` / ``AC@1_b_edges_mean`` /
      ``AC@1_c_centered`` (when ``with_offset_robustness=True``).
    * ``n``.
    """
    loader = RCAEvalLoader(data_path)
    method = FodaFCPMethod()

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
            with_offset_robustness=with_offset_robustness,
            rng=rng,
        )
        per_case.append(row)
        by_fault[row["fault"]].append(row)

    summary = _summarize(
        by_fault,
        top_ks,
        with_random_onset=with_random_onset,
        with_offset_robustness=with_offset_robustness,
    )
    return summary, per_case


# ---- single-case ----


def _evaluate_one_case(
    case: BenchmarkCase,
    method: FodaFCPMethod,
    top_ks: tuple[int, ...],
    shift_seconds: float,
    band_low: float,
    band_high: float,
    with_random_onset: bool,
    with_offset_robustness: bool,
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
    if with_offset_robustness:
        row.update(_offset_robustness_ac1(method, case, gt))
    return row


def _maybe_shifted_ac1(
    method: FodaFCPMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    shift: float,
    band_low: float,
    band_high: float,
) -> float:
    """``nan`` when the shifted offset would leave the band; else
    AC@1 of the run with a side-channel-shifted ``ground_truth``.

    Only ``ground_truth`` shifts; ``case_window`` is identical. FODA-FCP
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
    method: FodaFCPMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    rng: random.Random,
) -> float:
    """Re-score with FODA-FCP's :func:`detect_onset` replaced by a
    uniformly-random in-band pivot. Detector-vs-rule-engine
    decomposition.
    """
    times = norm_true.case_window["time"].to_numpy(dtype=float)
    if times.size < 2:
        return float("nan")
    t_min, t_max = float(times[0]), float(times[-1])
    t_low  = t_min + DEFAULT_INJECT_LOW_PCT  * (t_max - t_min)
    t_high = t_min + DEFAULT_INJECT_HIGH_PCT * (t_max - t_min)
    pivot = rng.uniform(t_low, t_high)

    original = foda_fcp_mod.detect_onset

    def _fake_detect_onset(case_window, services, **kwargs):
        return pivot

    foda_fcp_mod.detect_onset = _fake_detect_onset
    try:
        out = method.diagnose_normalized(norm_true)
    finally:
        foda_fcp_mod.detect_onset = original
    return float(accuracy_at_k(out.ranked_list, ground_truth, 1))


def _offset_robustness_ac1(
    method: FodaFCPMethod,
    case: BenchmarkCase,
    ground_truth: str,
) -> dict[str, float]:
    """Re-normalize the case at four explicit offsets and re-run.

    Returns a dict with five AC@1 columns: ``AC@1_a_standard``,
    ``AC@1_b_edge_left``, ``AC@1_b_edge_right``, ``AC@1_b_edges_mean``,
    ``AC@1_c_centered``. Each AC@1 is ``nan`` when normalization
    fails for the regime (e.g. raw telemetry doesn't cover the
    requested span).
    """
    ws = method.window_seconds
    standard = normalize_case(case, window_seconds=ws)
    out_a = method.diagnose_normalized(standard)
    ac_a = float(accuracy_at_k(out_a.ranked_list, ground_truth, 1))

    def _try(offset_pct: float) -> float:
        try:
            norm = normalize_case(
                case,
                window_seconds=ws,
                inject_offset_seconds=offset_pct * ws,
            )
        except Exception:
            return float("nan")
        out = method.diagnose_normalized(norm)
        return float(accuracy_at_k(out.ranked_list, ground_truth, 1))

    ac_left  = _try(_OFFSET_EDGE_LEFT_PCT)
    ac_right = _try(_OFFSET_EDGE_RIGHT_PCT)
    ac_cent  = _try(_OFFSET_CENTERED_PCT)
    valid_edges = [v for v in (ac_left, ac_right) if not math.isnan(v)]
    ac_edges_mean = mean(valid_edges) if valid_edges else float("nan")
    return {
        "AC@1_a_standard":    ac_a,
        "AC@1_b_edge_left":   ac_left,
        "AC@1_b_edge_right":  ac_right,
        "AC@1_b_edges_mean":  ac_edges_mean,
        "AC@1_c_centered":    ac_cent,
    }


# ---- aggregation ----


def _summarize(
    by_fault: dict[str, list[dict[str, Any]]],
    top_ks: tuple[int, ...],
    with_random_onset: bool,
    with_offset_robustness: bool,
) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}

    def _agg(rows: list[dict[str, Any]]) -> dict[str, float]:
        out: dict[str, float] = {
            f"AC@{k}": mean(r[f"AC@{k}"] for r in rows) for k in top_ks
        }
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
        if with_offset_robustness:
            for col in (
                "AC@1_a_standard", "AC@1_b_edge_left", "AC@1_b_edge_right",
                "AC@1_b_edges_mean", "AC@1_c_centered",
            ):
                vals = [
                    r[col] for r in rows
                    if not math.isnan(r.get(col, float("nan")))
                ]
                out[col] = mean(vals) if vals else float("nan")
        out["n"] = float(len(rows))
        return out

    for fault, rows in sorted(by_fault.items()):
        summary[fault] = _agg(rows)

    all_rows = [r for rs in by_fault.values() for r in rs]
    if all_rows:
        summary["overall"] = _agg(all_rows)
    return summary


# ---- CSV writers ----


def write_per_case_csv(per_case: list[dict[str, Any]], path: Path,
                       top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    base_fields = (
        ["case_id", "fault", "ground_truth", "top1_true"]
        + [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus"]
    )
    has_random = any("AC@1_random" in r for r in per_case)
    has_offset = any("AC@1_a_standard" in r for r in per_case)
    fieldnames = (
        base_fields
        + (["AC@1_random"] if has_random else [])
        + ([
            "AC@1_a_standard", "AC@1_b_edge_left", "AC@1_b_edge_right",
            "AC@1_b_edges_mean", "AC@1_c_centered",
        ] if has_offset else [])
    )
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(per_case)


def append_offset_diagnostic_csv(
    per_case: list[dict[str, Any]],
    path: Path,
    method_label: str = "FODA-FCP",
) -> None:
    """Append per-case offset-robustness rows to the shared cross-method
    diagnostic CSV at ``path``. The CSV must already exist (the file is
    populated by the previous six methods' harnesses); this function
    appends one row per case in the expected column order.

    Columns: ``method, case_id, fault, ground_truth, AC@1_a_standard,
    AC@1_b_edge_left, AC@1_b_edge_right, AC@1_b_edges_mean,
    AC@1_c_centered``. Cases without offset-robustness columns are
    skipped (they wouldn't have meaningful rows to append).
    """
    fieldnames = [
        "method", "case_id", "fault", "ground_truth",
        "AC@1_a_standard", "AC@1_b_edge_left", "AC@1_b_edge_right",
        "AC@1_b_edges_mean", "AC@1_c_centered",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            w.writeheader()
        for r in per_case:
            if "AC@1_a_standard" not in r:
                continue
            w.writerow({
                "method": method_label,
                "case_id": r["case_id"],
                "fault": r["fault"],
                "ground_truth": r["ground_truth"],
                "AC@1_a_standard":   r["AC@1_a_standard"],
                "AC@1_b_edge_left":  r["AC@1_b_edge_left"],
                "AC@1_b_edge_right": r["AC@1_b_edge_right"],
                "AC@1_b_edges_mean": r["AC@1_b_edges_mean"],
                "AC@1_c_centered":   r["AC@1_c_centered"],
            })


def print_summary(summary: dict[str, dict[str, float]],
                  top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    if not summary:
        print("(no cases)")
        return
    has_random = any("AC@1_random" in row for row in summary.values())
    has_offset = any("AC@1_a_standard" in row for row in summary.values())
    metric_cols = (
        [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus", "S", "S_flag"]
        + (["AC@1_random"] if has_random else [])
        + (["AC@1_a_standard", "AC@1_b_edges_mean", "AC@1_c_centered"]
           if has_offset else [])
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
        "--append-offset-diagnostic", type=Path, default=None,
        help=(
            "optional path to append per-case offset-robustness rows to "
            "the shared cross-method diagnostic CSV (one row per case, "
            "method=FODA-FCP). Requires --with-offset-robustness."
        ),
    )
    parser.add_argument(
        "--with-random-onset", action="store_true",
        help=(
            "additionally compute AC@1 with a uniformly-random in-band "
            "onset (detector-vs-rule-engine decomposition)"
        ),
    )
    parser.add_argument(
        "--with-offset-robustness", action="store_true",
        help=(
            "additionally compute AC@1 at four explicit offsets "
            "(standard / edge-left / edge-right / centered) — the "
            "offset-robustness diagnostic (Paper 6 §4)"
        ),
    )
    args = parser.parse_args(argv)

    summary, per_case = evaluate(
        data_path=args.data.expanduser(),
        top_ks=tuple(args.top_k),
        shift_seconds=args.shift,
        with_random_onset=args.with_random_onset,
        with_offset_robustness=args.with_offset_robustness,
    )
    print_summary(summary, tuple(args.top_k))
    if args.out is not None:
        write_per_case_csv(per_case, args.out, tuple(args.top_k))
        print(f"\nWrote per-case CSV to {args.out}")
    if args.append_offset_diagnostic is not None:
        if not args.with_offset_robustness:
            parser.error(
                "--append-offset-diagnostic requires --with-offset-robustness"
            )
        append_offset_diagnostic_csv(per_case, args.append_offset_diagnostic)
        print(
            f"Appended {len(per_case)} FODA-FCP rows to "
            f"{args.append_offset_diagnostic}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
