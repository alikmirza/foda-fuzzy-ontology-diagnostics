"""Standalone evaluation harness for DejaVu against RCAEval.

DejaVu requires a training phase, so the harness diverges from the
single-shot pattern used by the previous four methods (MR/CR/Micro/
BARO) in three places:

1. **5-fold cross-validation, stratified by fault type.** Each case
   is normalised once and assigned to a fold via a SHA-derived hash
   so the assignment is deterministic across runs. Per fold, a fresh
   :class:`DejaVuMethod` is trained on the other four folds and used
   to diagnose the held-out fold.

2. **Training-size ablation.** A separate pass trains on
   ``N ∈ {25, 50, 75, 100}`` cases and tests on a fixed 25-case
   held-out set (the first stratified fold), reporting AC@1 vs. N to
   isolate how much DejaVu's performance comes from training data
   vs. its architecture.

3. **Attention-output extraction.** For the standard 5-fold pass we
   pick 5 correct-prediction cases and 5 incorrect-prediction cases
   and dump their service-vocabulary attention matrices to
   ``results/dejavu_attention_samples.json`` for SemanticGroundedness
   inspection in Paper 6.

The harness calls
:func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
on the method *before* iterating through the test cases of each fold.
``train`` is exempt from the validator by design.

Usage::

    python -m evaluation.experiments.evaluate_dejavu \\
        --data ~/datasets/rcaeval/RE1/RE1-OB \\
        --out results/week2_dejavu_validation.csv \\
        --attention-out results/dejavu_attention_samples.json \\
        --with-size-ablation
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
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
from ..methods._protocol import validate_no_ground_truth_peeking
from ..methods.dejavu import DejaVuMethod
from ..metrics.ranking_metrics import accuracy_at_k, mean_reciprocal_rank


DEFAULT_SHIFT_SECONDS: float = 300.0
_SHIFT_FLAG_THRESHOLD: float = 0.20
_N_FOLDS: int = 5
_ABLATION_NS: tuple[int, ...] = (25, 50, 75, 100)
_ATTN_SAMPLES_CORRECT: int = 5
_ATTN_SAMPLES_INCORRECT: int = 5


# ---- fold assignment ----


def _fold_assignment(
    cases: list[BenchmarkCase], n_folds: int = _N_FOLDS, seed: int = 0
) -> list[int]:
    """Stratified-by-fault-type fold assignment.

    Within each fault group, cases are ordered by SHA-256 of
    ``f"{seed}|{case.id}"`` and round-robin assigned into folds with a
    per-group starting offset (also seed-and-fault-derived) so single-
    case strata don't all collapse into fold 0. Deterministic across
    runs and across machines.
    """
    by_fault: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for c in cases:
        by_fault[c.ground_truth_fault_type].append(c)
    fold_of: dict[str, int] = {}
    for fault, group in by_fault.items():
        ordered = sorted(
            group,
            key=lambda c: hashlib.sha256(
                f"{seed}|{c.id}".encode("utf-8")
            ).digest(),
        )
        offset = int.from_bytes(
            hashlib.sha256(f"{seed}|{fault}".encode("utf-8")).digest()[:4],
            "big",
        ) % n_folds
        for i, c in enumerate(ordered):
            fold_of[c.id] = (offset + i) % n_folds
    return [fold_of[c.id] for c in cases]


# ---- per-case shift ----


def _maybe_shifted_ac1(
    method: DejaVuMethod,
    norm_true: NormalizedCase,
    ground_truth: str,
    shift: float,
    band_low: float,
    band_high: float,
) -> float:
    """``nan`` if shifted offset leaves the band, else AC@1 with a
    ground-truth-shifted normalized case."""
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


# ---- main evaluation ----


def evaluate(
    data_path: Path,
    top_ks: tuple[int, ...] = (1, 3, 5),
    shift_seconds: float = DEFAULT_SHIFT_SECONDS,
    n_folds: int = _N_FOLDS,
    epochs: int = 80,
    hidden: int = 32,
    seed: int = 0,
    with_size_ablation: bool = False,
    attention_samples_out: Path | None = None,
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]], dict[str, Any]]:
    """Run 5-fold cross-validation of DejaVu on RCAEval cases.

    Returns ``(summary, per_case_rows, extras)`` where ``extras``
    carries the training-size-ablation table (if requested) and the
    attention-sample dump path.
    """
    loader = RCAEvalLoader(data_path)
    all_cases = list(loader.iter_cases())
    if not all_cases:
        raise RuntimeError(f"no cases found under {data_path}")
    folds = _fold_assignment(all_cases, n_folds=n_folds, seed=seed)
    method = DejaVuMethod(
        epochs=epochs, hidden=hidden, seed=seed
    )

    # Protocol gate: refuse to score a leaky method. Note: this checks
    # ``diagnose``; ``train`` legitimately reads ground_truth.
    validate_no_ground_truth_peeking(method)

    band_low  = DEFAULT_INJECT_LOW_PCT  * method.window_seconds
    band_high = DEFAULT_INJECT_HIGH_PCT * method.window_seconds

    # Pre-normalize every case once.
    norm_cases: list[NormalizedCase] = [
        normalize_case(c, window_seconds=method.window_seconds)
        for c in all_cases
    ]

    per_case: list[dict[str, Any]] = []
    by_fault: dict[str, list[dict[str, Any]]] = defaultdict(list)
    attention_records: list[dict[str, Any]] = []

    for fold_idx in range(n_folds):
        train_norms = [
            n for n, f in zip(norm_cases, folds) if f != fold_idx
        ]
        test_pairs = [
            (i, n) for i, (n, f) in enumerate(zip(norm_cases, folds))
            if f == fold_idx
        ]
        if not train_norms or not test_pairs:
            continue
        method = DejaVuMethod(
            epochs=epochs, hidden=hidden, seed=seed
        )
        method.train(train_norms)

        for case_idx, n_test in test_pairs:
            case = all_cases[case_idx]
            gt = case.ground_truth_root_cause
            fault = case.ground_truth_fault_type
            out = method.diagnose_normalized(n_test)
            row = {
                "case_id": case.id,
                "fault": fault,
                "ground_truth": gt,
                "fold": fold_idx,
                "top1_pred": out.ranked_list[0][0] if out.ranked_list else "",
                "predicted_fault_type": out.raw_output.get(
                    "predicted_failure_type", ""
                ),
                **{
                    f"AC@{k}": float(accuracy_at_k(out.ranked_list, gt, k))
                    for k in top_ks
                },
                "MRR": float(mean_reciprocal_rank(out.ranked_list, gt)),
                "AC@1_shift_minus": _maybe_shifted_ac1(
                    method, n_test, gt, -shift_seconds, band_low, band_high
                ),
                "AC@1_shift_plus": _maybe_shifted_ac1(
                    method, n_test, gt,  shift_seconds, band_low, band_high
                ),
            }
            per_case.append(row)
            by_fault[fault].append(row)

            # Maybe collect an attention sample.
            ac1 = row["AC@1"]
            if attention_samples_out is not None:
                correct = ac1 == 1.0
                want = (
                    (correct and sum(1 for r in attention_records if r["correct"]) < _ATTN_SAMPLES_CORRECT)
                    or (not correct and sum(1 for r in attention_records if not r["correct"]) < _ATTN_SAMPLES_INCORRECT)
                )
                if want:
                    attention_records.append({
                        "case_id": case.id,
                        "fault": fault,
                        "ground_truth": gt,
                        "predicted_failure_unit": out.raw_output.get(
                            "predicted_failure_unit"
                        ),
                        "predicted_failure_type": out.raw_output.get(
                            "predicted_failure_type"
                        ),
                        "correct": bool(correct),
                        "service_vocab": out.raw_output.get("service_vocab", []),
                        "present_mask": out.raw_output.get("present_mask", []),
                        "attention": out.raw_output.get("attention", []),
                    })

    summary = _summarize(by_fault, top_ks)

    extras: dict[str, Any] = {}
    if with_size_ablation:
        extras["size_ablation"] = _size_ablation(
            all_cases=all_cases,
            norm_cases=norm_cases,
            folds=folds,
            method_kwargs=dict(epochs=epochs, hidden=hidden, seed=seed),
            ns=_ABLATION_NS,
            top_ks=top_ks,
        )

    if attention_samples_out is not None:
        attention_samples_out.parent.mkdir(parents=True, exist_ok=True)
        with attention_samples_out.open("w") as fh:
            json.dump(
                {
                    "samples": attention_records,
                    "n_correct": sum(1 for r in attention_records if r["correct"]),
                    "n_incorrect": sum(1 for r in attention_records if not r["correct"]),
                },
                fh,
                indent=2,
            )
        extras["attention_samples_out"] = str(attention_samples_out)

    return summary, per_case, extras


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
        deltas: list[float] = []
        for r in rows:
            shifts = [r["AC@1_shift_minus"], r["AC@1_shift_plus"]]
            valid = [s for s in shifts if not math.isnan(s)]
            if not valid:
                continue
            deltas.append(abs(r["AC@1"] - mean(valid)))
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


# ---- training-size ablation ----


def _size_ablation(
    all_cases: list[BenchmarkCase],
    norm_cases: list[NormalizedCase],
    folds: list[int],
    method_kwargs: dict[str, Any],
    ns: tuple[int, ...],
    top_ks: tuple[int, ...],
) -> dict[int, dict[str, float]]:
    """Train on the first ``N`` non-test cases for each ``N``, test on
    the held-out fold-0 cases. Returns ``{N: {AC@k: ..., n: ...}}``.

    The training pool is ordered the same way the fold assigner orders
    it (deterministic hash), so the increments are nested:
    ``train_pool[:25] ⊂ train_pool[:50] ⊂ …``.
    """
    test_idx = [i for i, f in enumerate(folds) if f == 0]
    train_pool_idx = [i for i, f in enumerate(folds) if f != 0]
    if not test_idx or not train_pool_idx:
        return {}

    out: dict[int, dict[str, float]] = {}
    test_norms = [norm_cases[i] for i in test_idx]
    test_cases = [all_cases[i] for i in test_idx]
    for N in ns:
        if N > len(train_pool_idx):
            continue
        train_norms = [norm_cases[i] for i in train_pool_idx[:N]]
        method = DejaVuMethod(**method_kwargs)
        method.train(train_norms)
        rows = []
        for n_test, case in zip(test_norms, test_cases):
            o = method.diagnose_normalized(n_test)
            rows.append(
                {
                    f"AC@{k}": float(accuracy_at_k(
                        o.ranked_list, case.ground_truth_root_cause, k
                    ))
                    for k in top_ks
                }
            )
        out[N] = {
            f"AC@{k}": mean(r[f"AC@{k}"] for r in rows) for k in top_ks
        }
        out[N]["n"] = float(len(rows))
    return out


# ---- CSV / CLI ----


def write_per_case_csv(per_case: list[dict[str, Any]], path: Path,
                       top_ks: tuple[int, ...] = (1, 3, 5)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = (
        ["case_id", "fault", "ground_truth", "fold",
         "top1_pred", "predicted_fault_type"]
        + [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus"]
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
    cols = (
        [f"AC@{k}" for k in top_ks]
        + ["MRR", "AC@1_shift_minus", "AC@1_shift_plus", "S", "S_flag"]
    )
    header = (
        f"{'fault':<10} {'n':>4} "
        + " ".join(f"{c:>17}" for c in cols)
    )
    print(header)
    print("-" * len(header))
    for fault, row in summary.items():
        cells = [f"{fault:<10}", f"{int(row['n']):>4}"]
        for col in cols:
            v = row.get(col, float("nan"))
            if col == "S_flag":
                cells.append(f"{'FLAG' if v == 1.0 else 'OK':>17}")
            elif isinstance(v, float) and math.isnan(v):
                cells.append(f"{'nan':>17}")
            else:
                cells.append(f"{v:>17.3f}")
        print(" ".join(cells))


def print_size_ablation(table: dict[int, dict[str, float]]) -> None:
    if not table:
        return
    print()
    print("Training-size ablation (test = fold-0 held-out):")
    print(f"{'N_train':>8} {'AC@1':>8} {'AC@3':>8} {'AC@5':>8} {'n_test':>8}")
    for N in sorted(table):
        row = table[N]
        print(
            f"{N:>8} {row.get('AC@1', float('nan')):>8.3f} "
            f"{row.get('AC@3', float('nan')):>8.3f} "
            f"{row.get('AC@5', float('nan')):>8.3f} "
            f"{int(row.get('n', 0)):>8}"
        )


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
    parser.add_argument("--n-folds", type=int, default=_N_FOLDS)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--hidden", type=int, default=32)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--out", type=Path, default=None,
        help="optional path to write the per-case CSV",
    )
    parser.add_argument(
        "--attention-out", type=Path, default=None,
        help=(
            "optional path to write the 5-correct + 5-incorrect "
            "attention sample JSON for Paper 6 inspection"
        ),
    )
    parser.add_argument(
        "--with-size-ablation", action="store_true",
        help="run the N∈{25,50,75,100} training-size ablation",
    )
    args = parser.parse_args(argv)

    summary, per_case, extras = evaluate(
        data_path=args.data.expanduser(),
        top_ks=tuple(args.top_k),
        shift_seconds=args.shift,
        n_folds=args.n_folds,
        epochs=args.epochs,
        hidden=args.hidden,
        seed=args.seed,
        with_size_ablation=args.with_size_ablation,
        attention_samples_out=(
            args.attention_out.expanduser() if args.attention_out else None
        ),
    )
    print_summary(summary, tuple(args.top_k))
    if "size_ablation" in extras:
        print_size_ablation(extras["size_ablation"])
    if args.out is not None:
        write_per_case_csv(per_case, args.out, tuple(args.top_k))
        print(f"\nWrote per-case CSV to {args.out}")
    if "attention_samples_out" in extras:
        print(f"Wrote attention samples to {extras['attention_samples_out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
