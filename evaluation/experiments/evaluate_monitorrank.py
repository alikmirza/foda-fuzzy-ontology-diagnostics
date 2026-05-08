"""Standalone evaluation harness for MonitorRank against RCAEval.

Pending: MonitorRank's AC@k against the real RCAEval data has not yet
been validated, because the dataset (~ several GB) lives outside this
repository. RCAEval itself does **not** include MonitorRank in its
published baselines (their table compares BARO, MicroCause, MicroRank,
CIRCA, RCD, etc.), so there is no exact published number to reproduce
— but BARO / MicroCause / MicroRank serve as comparable reference
points for sanity-checking the AC@1 ballpark by fault type.

Usage::

    python -m evaluation.experiments.evaluate_monitorrank \\
        --data ~/datasets/rcaeval/RE1 \\
        --top-k 1 3 5

The script groups results by ground-truth fault type (CPU / MEM / DISK
/ etc.) and prints AC@k and MRR for each, plus an overall row. It
makes no other side-effects: no plots, no files written.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean

from ..benchmarks.rcaeval_loader import RCAEvalLoader
from ..methods.monitorrank import MonitorRankMethod
from ..metrics.ranking_metrics import accuracy_at_k, mean_reciprocal_rank


def evaluate(
    data_path: Path,
    top_ks: tuple[int, ...] = (1, 3, 5),
    alpha: float = 0.85,
    rho: float = 0.5,
) -> dict[str, dict[str, float]]:
    """Run MonitorRank on every RCAEval case under ``data_path``.

    Returns a nested dict ``{fault_type: {metric_name: value}}`` plus
    an ``"overall"`` row.
    """
    loader = RCAEvalLoader(data_path)
    method = MonitorRankMethod(alpha=alpha, rho=rho)

    by_fault: dict[str, list[dict[str, float]]] = defaultdict(list)
    for case in loader.iter_cases():
        out = method.diagnose(case)
        row = {
            f"AC@{k}": float(
                accuracy_at_k(out.ranked_list, case.ground_truth_root_cause, k)
            )
            for k in top_ks
        }
        row["MRR"] = mean_reciprocal_rank(
            out.ranked_list, case.ground_truth_root_cause
        )
        by_fault[case.ground_truth_fault_type].append(row)

    summary: dict[str, dict[str, float]] = {}
    metric_names = [f"AC@{k}" for k in top_ks] + ["MRR"]
    for fault, rows in sorted(by_fault.items()):
        summary[fault] = {m: mean(r[m] for r in rows) for m in metric_names}
        summary[fault]["n"] = float(len(rows))
    all_rows = [r for rows in by_fault.values() for r in rows]
    if all_rows:
        summary["overall"] = {
            m: mean(r[m] for r in all_rows) for m in metric_names
        }
        summary["overall"]["n"] = float(len(all_rows))
    return summary


def _print_table(summary: dict[str, dict[str, float]]) -> None:
    if not summary:
        print("(no cases)")
        return
    columns = ["n"] + [c for c in summary[next(iter(summary))] if c != "n"]
    header = "fault_type".ljust(12) + "".join(c.rjust(10) for c in columns)
    print(header)
    print("-" * len(header))
    for fault, row in summary.items():
        line = fault.ljust(12)
        for col in columns:
            v = row.get(col, 0.0)
            line += (f"{int(v):>10}" if col == "n" else f"{v:>10.3f}")
        print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        required=True,
        help="path to an extracted RCAEval directory (e.g. ~/datasets/rcaeval/RE1)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        nargs="+",
        default=[1, 3, 5],
        help="AC@k cutoffs to report (default: 1 3 5)",
    )
    parser.add_argument("--alpha", type=float, default=0.85)
    parser.add_argument("--rho", type=float, default=0.5)
    args = parser.parse_args(argv)

    summary = evaluate(
        data_path=args.data.expanduser(),
        top_ks=tuple(args.top_k),
        alpha=args.alpha,
        rho=args.rho,
    )
    _print_table(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
