"""Phase 2 Week 1 — score SemanticGroundedness for every method on
RE1-OB and emit ``results/phase2_semantic_groundedness.csv``.

Runs all seven Phase-1 method adapters over the same 125 RE1-OB cases
and scores each emitted :class:`CanonicalExplanation` against the
DiagnosticKB ontology via
:class:`evaluation.metrics.semantic_groundedness.SemanticGroundedness`.
Methods differ in how they construct atoms; the metric is the same
for all seven.

Output:

* ``results/phase2_semantic_groundedness.csv`` — one row per
  ``(method, case_id)`` pair (875 rows), columns: ``method``,
  ``case_id``, ``fault``, ``ac1``, ``sg_overall``, ``direct_matches``,
  ``fuzzy_matches``, ``unmatched``, ``atom_count``.
* ``stdout`` — per-method mean/std SG, the 5×7 per-fault matrix, and
  the Spearman rank correlation between AC@1 and SG over all 875
  case-method pairs.

DejaVu is a trained method; we evaluate it via the same 5-fold
stratified CV the standalone harness ``evaluate_dejavu.py`` uses.
The other six methods are single-shot and need no training.

Usage::

    python -m evaluation.experiments.run_phase2_sg \\
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-OB \\
        --out results/phase2_semantic_groundedness.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..benchmarks.rcaeval_loader import RCAEvalLoader
from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
)
from ..extraction.schema_normalizer import NormalizedCase, normalize_case
from ..methods.baro import BAROMethod
from ..methods.causalrca import CausalRCAMethod
from ..methods.dejavu import DejaVuMethod
from ..methods.foda_fcp import FodaFCPMethod
from ..methods.microrca import MicroRCAMethod
from ..methods.monitorrank import MonitorRankMethod
from ..methods.yrca import YRCAMethod
from ..metrics import OntologyAdapter, SemanticGroundedness, accuracy_at_k


_DEJAVU_FOLDS: int = 5
_DEJAVU_EPOCHS: int = 80
_DEJAVU_HIDDEN: int = 32
_DEJAVU_SEED: int = 0

#: Method label → factory. DejaVu is special-cased in :func:`evaluate`.
_SINGLE_SHOT_METHODS: dict[str, Any] = {
    "MR":       lambda: MonitorRankMethod(),
    "CR":       lambda: CausalRCAMethod(),
    "Micro":    lambda: MicroRCAMethod(),
    "BARO":     lambda: BAROMethod(),
    "yRCA":     lambda: YRCAMethod(),
    "FODA-FCP": lambda: FodaFCPMethod(),
}


def evaluate(
    data_path: Path,
    metric: SemanticGroundedness | None = None,
    ontology: OntologyAdapter | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    """Run all seven methods × every RE1-OB case and score
    SemanticGroundedness.

    Returns ``(rows, summary)``. ``rows`` is a list of per-case
    records; ``summary`` is the per-method aggregate ready for
    :func:`print_summary`.
    """
    metric = metric or SemanticGroundedness()
    ontology = ontology or OntologyAdapter()
    loader = RCAEvalLoader(data_path)
    cases = list(loader.iter_cases())
    if not cases:
        raise RuntimeError(f"no cases under {data_path}")

    rows: list[dict[str, Any]] = []

    # --- six single-shot methods --------------------------------------
    for label, factory in _SINGLE_SHOT_METHODS.items():
        method = factory()
        window_s = method.window_seconds
        norms = [normalize_case(c, window_seconds=window_s) for c in cases]
        for case, norm in zip(cases, norms):
            out = method.diagnose_normalized(norm)
            rows.append(_score_row(label, case, out, metric, ontology))

    # --- DejaVu via 5-fold stratified CV ------------------------------
    rows.extend(_dejavu_rows(cases, metric, ontology))

    summary = _summarize(rows)
    return rows, summary


# ---- per-case scoring ----


def _score_row(
    method_label: str,
    case: BenchmarkCase,
    out: DiagnosticOutput,
    metric: SemanticGroundedness,
    ontology: OntologyAdapter,
) -> dict[str, Any]:
    breakdown = metric.score_with_breakdown(out.explanation_chain, ontology)
    ac1 = (
        1.0
        if out.ranked_list and out.ranked_list[0][0] == case.ground_truth_root_cause
        else 0.0
    )
    return {
        "method": method_label,
        "case_id": case.id,
        "fault": case.ground_truth_fault_type,
        "ac1": ac1,
        "sg_overall": breakdown["overall"],
        "direct_matches": breakdown["direct_matches"],
        "fuzzy_matches": breakdown["fuzzy_matches"],
        "unmatched": breakdown["unmatched"],
        "atom_count": breakdown["atom_count"],
    }


# ---- DejaVu CV ----


def _dejavu_fold_assignment(
    cases: list[BenchmarkCase], n_folds: int = _DEJAVU_FOLDS, seed: int = _DEJAVU_SEED,
) -> list[int]:
    """Stratified-by-fault-type round-robin fold assignment, identical
    to ``evaluate_dejavu._fold_assignment`` so we score DejaVu on the
    same CV split it was originally validated under."""
    by_fault: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for c in cases:
        by_fault[c.ground_truth_fault_type].append(c)
    fold_of: dict[str, int] = {}
    for fault, group in sorted(by_fault.items()):
        ordered = sorted(
            group,
            key=lambda c: hashlib.sha256(f"{seed}|{c.id}".encode("utf-8")).digest(),
        )
        offset = int.from_bytes(
            hashlib.sha256(f"{seed}|{fault}".encode("utf-8")).digest()[:4], "big",
        ) % n_folds
        for i, c in enumerate(ordered):
            fold_of[c.id] = (offset + i) % n_folds
    return [fold_of[c.id] for c in cases]


def _dejavu_rows(
    cases: list[BenchmarkCase],
    metric: SemanticGroundedness,
    ontology: OntologyAdapter,
) -> list[dict[str, Any]]:
    """5-fold stratified CV of DejaVu. Returns one SG row per case."""
    # Pre-normalize once at DejaVu's window length.
    method0 = DejaVuMethod(
        epochs=_DEJAVU_EPOCHS, hidden=_DEJAVU_HIDDEN, seed=_DEJAVU_SEED,
    )
    norms = [normalize_case(c, window_seconds=method0.window_seconds) for c in cases]
    folds = _dejavu_fold_assignment(cases)

    rows: list[dict[str, Any]] = []
    for fold_idx in range(_DEJAVU_FOLDS):
        train_norms = [n for n, f in zip(norms, folds) if f != fold_idx]
        test_indices = [i for i, f in enumerate(folds) if f == fold_idx]
        if not train_norms or not test_indices:
            continue
        method = DejaVuMethod(
            epochs=_DEJAVU_EPOCHS, hidden=_DEJAVU_HIDDEN, seed=_DEJAVU_SEED,
        )
        method.train(train_norms)
        for i in test_indices:
            out = method.diagnose_normalized(norms[i])
            rows.append(_score_row("DejaVu", cases[i], out, metric, ontology))
    return rows


# ---- aggregation ----


def _summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per-method aggregate. ``__overall__`` carries cross-method totals."""
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)

    out: dict[str, dict[str, float]] = {}
    for method, rs in by_method.items():
        sg_vals = [r["sg_overall"] for r in rs]
        ac1_vals = [r["ac1"] for r in rs]
        by_fault: dict[str, list[float]] = defaultdict(list)
        for r in rs:
            by_fault[r["fault"]].append(r["sg_overall"])
        out[method] = {
            "n": float(len(rs)),
            "sg_mean": statistics.mean(sg_vals),
            "sg_std": statistics.stdev(sg_vals) if len(sg_vals) > 1 else 0.0,
            "ac1_mean": statistics.mean(ac1_vals),
            "direct_mean": statistics.mean(r["direct_matches"] for r in rs),
            "fuzzy_mean":  statistics.mean(r["fuzzy_matches"] for r in rs),
            "unmatched_mean": statistics.mean(r["unmatched"] for r in rs),
            "atom_count_mean": statistics.mean(r["atom_count"] for r in rs),
            **{f"sg_{fault}": statistics.mean(vs) for fault, vs in by_fault.items()},
        }
    return out


def spearman_ac1_vs_sg(rows: list[dict[str, Any]]) -> float:
    """Spearman rank correlation between AC@1 and SG over all 875
    case-method pairs.

    Tie-aware: pairs with identical AC@1 are ranked by average rank.
    We implement Spearman manually (rather than importing scipy) to
    keep the dependency surface narrow.
    """
    n = len(rows)
    if n < 2:
        return float("nan")
    pairs = [(r["ac1"], r["sg_overall"]) for r in rows]

    def _ranks(values: list[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda kv: kv[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0  # average 1-based rank
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    ac_ranks = _ranks([p[0] for p in pairs])
    sg_ranks = _ranks([p[1] for p in pairs])
    mean_x = statistics.mean(ac_ranks)
    mean_y = statistics.mean(sg_ranks)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(ac_ranks, sg_ranks))
    den_x = sum((x - mean_x) ** 2 for x in ac_ranks) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in sg_ranks) ** 0.5
    if den_x == 0.0 or den_y == 0.0:
        return float("nan")
    return num / (den_x * den_y)


# ---- IO ----


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "method", "case_id", "fault", "ac1", "sg_overall",
        "direct_matches", "fuzzy_matches", "unmatched", "atom_count",
    ]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def print_summary(summary: dict[str, dict[str, float]], spearman: float) -> None:
    method_order = ["MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP"]
    faults = sorted({k[3:] for v in summary.values() for k in v if k.startswith("sg_") and k != "sg_mean" and k != "sg_std"})

    print(f"\n{'Method':<10} {'n':>5} {'SG_mean':>9} {'SG_std':>8} {'AC@1':>7} "
          f"{'direct_avg':>11} {'fuzzy_avg':>10} {'unmatched_avg':>14} {'atoms_avg':>10}")
    print("-" * 92)
    for m in method_order:
        if m not in summary:
            continue
        r = summary[m]
        print(
            f"{m:<10} {int(r['n']):>5} {r['sg_mean']:>9.3f} {r['sg_std']:>8.3f} "
            f"{r['ac1_mean']:>7.3f} {r['direct_mean']:>11.2f} {r['fuzzy_mean']:>10.2f} "
            f"{r['unmatched_mean']:>14.2f} {r['atom_count_mean']:>10.2f}"
        )

    print(f"\nPer-fault SG mean (rows = method, cols = fault):")
    header = f"{'Method':<10} " + " ".join(f"{f:>8}" for f in faults)
    print(header)
    print("-" * len(header))
    for m in method_order:
        if m not in summary:
            continue
        cells = [f"{m:<10}"]
        for f in faults:
            v = summary[m].get(f"sg_{f}", float("nan"))
            cells.append(f"{v:>8.3f}")
        print(" ".join(cells))

    print(f"\nSpearman rank correlation between AC@1 and SG "
          f"(over all {sum(int(summary[m]['n']) for m in summary)} case-method pairs):")
    print(f"  ρ = {spearman:+.3f}")
    if spearman > 0.3:
        print("  → positive: methods that rank well also produce grounded explanations")
    elif spearman < -0.3:
        print("  → negative: rank-quality and ontology-grounding axes are inversely correlated")
    else:
        print("  → near zero: the two axes are roughly independent — the empirical "
              "claim Paper 6 §4 is positioned to make")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_semantic_groundedness.csv"),
    )
    args = parser.parse_args(argv)

    rows, summary = evaluate(args.data.expanduser())
    write_csv(rows, args.out)
    sp = spearman_ac1_vs_sg(rows)
    print_summary(summary, sp)
    print(f"\nWrote {len(rows)} per-case rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
