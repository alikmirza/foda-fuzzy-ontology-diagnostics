"""Phase 2 Week 3 — score :class:`ExplanationCompleteness` (and
report alongside SG and SC) for every method on RE1-OB.

Runs all seven Phase-1 method adapters over the same 125 RE1-OB
cases and scores each emitted :class:`CanonicalExplanation` on
SG + SC + EC. Saves the joined per-case rows to
``results/phase2_explanation_completeness.csv``; prints per-method
aggregates (mean + std), per-category presence fractions, the
EC-score distribution (how many cases at each of
``{0.0, 0.333, 0.667, 1.0}``), and three Spearman correlations:
ρ(AC@1, EC), ρ(SG, EC), ρ(SC, EC).

The per-case CSV has columns: ``method``, ``case_id``, ``fault``,
``ac1``, ``sg``, ``sc``, ``ec_overall``, ``has_cause``,
``has_component``, ``has_mitigation``. AC@1 / SG / SC are joined
to avoid downstream cross-CSV merges.

Usage::

    python -m evaluation.experiments.run_phase2_ec \\
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-OB \\
        --out results/phase2_explanation_completeness.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..benchmarks.rcaeval_loader import RCAEvalLoader
from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from ..extraction.schema_normalizer import NormalizedCase, normalize_case
from ..methods.baro import BAROMethod
from ..methods.causalrca import CausalRCAMethod
from ..methods.dejavu import DejaVuMethod
from ..methods.foda_fcp import FodaFCPMethod
from ..methods.microrca import MicroRCAMethod
from ..methods.monitorrank import MonitorRankMethod
from ..methods.yrca import YRCAMethod
from ..metrics import (
    ExplanationCompleteness,
    OntologyAdapter,
    SemanticCoherence,
    SemanticGroundedness,
)


_DEJAVU_FOLDS: int = 5
_DEJAVU_EPOCHS: int = 80
_DEJAVU_HIDDEN: int = 32
_DEJAVU_SEED: int = 0


_SINGLE_SHOT_METHODS: dict[str, Any] = {
    "MR":       lambda: MonitorRankMethod(),
    "CR":       lambda: CausalRCAMethod(),
    "Micro":    lambda: MicroRCAMethod(),
    "BARO":     lambda: BAROMethod(),
    "yRCA":     lambda: YRCAMethod(),
    "FODA-FCP": lambda: FodaFCPMethod(),
}


_EC_BUCKETS: tuple[float, ...] = (0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0)


def evaluate(
    data_path: Path,
    sg: SemanticGroundedness | None = None,
    sc: SemanticCoherence | None = None,
    ec: ExplanationCompleteness | None = None,
    ontology: OntologyAdapter | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    sg = sg or SemanticGroundedness()
    sc = sc or SemanticCoherence()
    ec = ec or ExplanationCompleteness()
    ontology = ontology or OntologyAdapter()
    loader = RCAEvalLoader(data_path)
    cases = list(loader.iter_cases())
    if not cases:
        raise RuntimeError(f"no cases under {data_path}")

    rows: list[dict[str, Any]] = []

    for label, factory in _SINGLE_SHOT_METHODS.items():
        method = factory()
        window_s = method.window_seconds
        norms = [normalize_case(c, window_seconds=window_s) for c in cases]
        for case, norm in zip(cases, norms):
            out = method.diagnose_normalized(norm)
            rows.append(_score_row(label, case, norm, out, sg, sc, ec, ontology))

    rows.extend(_dejavu_rows(cases, sg, sc, ec, ontology))

    summary = _summarize(rows)
    return rows, summary


def _score_row(
    method_label: str,
    case: BenchmarkCase,
    norm: NormalizedCase,
    out: DiagnosticOutput,
    sg: SemanticGroundedness,
    sc: SemanticCoherence,
    ec: ExplanationCompleteness,
    ontology: OntologyAdapter,
) -> dict[str, Any]:
    sg_overall = sg.score(out.explanation_chain, ontology)
    sc_overall = sc.score(out.explanation_chain, ontology)
    ec_br = ec.score_with_breakdown(
        out.explanation_chain, ontology, case_services=norm.services,
    )
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
        "sg": sg_overall,
        "sc": sc_overall,
        "ec_overall": ec_br["overall"],
        "has_cause": int(ec_br["has_cause"]),
        "has_component": int(ec_br["has_component"]),
        "has_mitigation": int(ec_br["has_mitigation"]),
    }


# ---- DejaVu CV (same as Week 2 harness) ----


def _dejavu_fold_assignment(
    cases: list[BenchmarkCase], n_folds: int = _DEJAVU_FOLDS, seed: int = _DEJAVU_SEED,
) -> list[int]:
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
    sg: SemanticGroundedness,
    sc: SemanticCoherence,
    ec: ExplanationCompleteness,
    ontology: OntologyAdapter,
) -> list[dict[str, Any]]:
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
            rows.append(_score_row(
                "DejaVu", cases[i], norms[i], out, sg, sc, ec, ontology,
            ))
    return rows


# ---- aggregation ----


def _bucket_ec(ec_overall: float) -> float:
    """Snap an EC overall score to its nearest discrete bucket. The
    metric is constructed to produce one of four exact values, but
    floating-point arithmetic can introduce 1e-16 deviations; this
    rounds to the canonical bucket."""
    return min(_EC_BUCKETS, key=lambda b: abs(b - ec_overall))


def _summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)
    out: dict[str, dict[str, float]] = {}
    for method, rs in by_method.items():
        ec_vals = [r["ec_overall"] for r in rs]
        bucket_counts = Counter(_bucket_ec(v) for v in ec_vals)
        out[method] = {
            "n": float(len(rs)),
            "ec_mean": statistics.mean(ec_vals),
            "ec_std": statistics.stdev(ec_vals) if len(ec_vals) > 1 else 0.0,
            "sg_mean": statistics.mean(r["sg"] for r in rs),
            "sc_mean": statistics.mean(r["sc"] for r in rs),
            "ac1_mean": statistics.mean(r["ac1"] for r in rs),
            "frac_cause":      statistics.mean(r["has_cause"] for r in rs),
            "frac_component":  statistics.mean(r["has_component"] for r in rs),
            "frac_mitigation": statistics.mean(r["has_mitigation"] for r in rs),
            "n_at_0":          float(bucket_counts.get(0.0, 0)),
            "n_at_one_third":  float(bucket_counts.get(1.0 / 3.0, 0)),
            "n_at_two_thirds": float(bucket_counts.get(2.0 / 3.0, 0)),
            "n_at_1":          float(bucket_counts.get(1.0, 0)),
        }
    return out


def spearman(rows: list[dict[str, Any]], x_key: str, y_key: str) -> float:
    """Tie-aware Spearman rank correlation between two per-row columns.

    Same shape as the Week 2 harness's helper; duplicated here so the
    two run scripts stay independent. If a third week starts to share
    more, factor into ``evaluation/experiments/_correlations.py``.
    """
    n = len(rows)
    if n < 2:
        return float("nan")
    pairs = [(r[x_key], r[y_key]) for r in rows]

    def _ranks(values: list[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda kv: kv[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    x_ranks = _ranks([float(p[0]) for p in pairs])
    y_ranks = _ranks([float(p[1]) for p in pairs])
    mean_x = statistics.mean(x_ranks)
    mean_y = statistics.mean(y_ranks)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_ranks, y_ranks))
    den_x = sum((x - mean_x) ** 2 for x in x_ranks) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in y_ranks) ** 0.5
    if den_x == 0.0 or den_y == 0.0:
        return float("nan")
    return num / (den_x * den_y)


# ---- IO ----


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "method", "case_id", "fault", "ac1", "sg", "sc", "ec_overall",
        "has_cause", "has_component", "has_mitigation",
    ]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def print_summary(
    summary: dict[str, dict[str, float]],
    sp_ac_ec: float,
    sp_sg_ec: float,
    sp_sc_ec: float,
) -> None:
    method_order = ["MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP"]

    print(f"\n{'Method':<10} {'n':>5} {'EC_mean':>9} {'EC_std':>8} "
          f"{'SG_mean':>9} {'SC_mean':>9} {'AC@1':>7} "
          f"{'cause%':>8} {'comp%':>8} {'mit%':>8}")
    print("-" * 100)
    for m in method_order:
        if m not in summary:
            continue
        r = summary[m]
        print(
            f"{m:<10} {int(r['n']):>5} {r['ec_mean']:>9.3f} {r['ec_std']:>8.3f} "
            f"{r['sg_mean']:>9.3f} {r['sc_mean']:>9.3f} {r['ac1_mean']:>7.3f} "
            f"{r['frac_cause']:>8.3f} {r['frac_component']:>8.3f} "
            f"{r['frac_mitigation']:>8.3f}"
        )

    print("\nEC score-bucket distribution (cases per method at each EC value):")
    print(f"{'Method':<10} {'n@0.0':>8} {'n@0.333':>10} {'n@0.667':>10} {'n@1.0':>8}")
    print("-" * 50)
    for m in method_order:
        if m not in summary:
            continue
        r = summary[m]
        print(
            f"{m:<10} {int(r['n_at_0']):>8} {int(r['n_at_one_third']):>10} "
            f"{int(r['n_at_two_thirds']):>10} {int(r['n_at_1']):>8}"
        )

    n_total = int(sum(summary[m]["n"] for m in summary))
    print(f"\nSpearman rank correlations (over all {n_total} case-method pairs):")
    print(f"  ρ(AC@1, EC) = {sp_ac_ec:+.3f}")
    print(f"  ρ(SG,   EC) = {sp_sg_ec:+.3f}")
    print(f"  ρ(SC,   EC) = {sp_sc_ec:+.3f}")

    # Brief alarm gates.
    print("\nAlarm gates:")
    fcp = summary.get("FODA-FCP", {})
    if fcp.get("ec_mean", 0.0) < 0.9:
        print(f"  ⚠ FCP EC mean {fcp.get('ec_mean'):.3f} < 0.9")
    else:
        print(f"  ✓ FCP EC mean {fcp.get('ec_mean'):.3f} ≥ 0.9")
    for label in ("MR", "CR", "Micro", "BARO"):
        v = summary.get(label, {}).get("ec_mean", 0.0)
        if v > 0.4:
            print(f"  ⚠ {label} EC mean {v:.3f} > 0.4 (component detector too generous)")
        else:
            print(f"  ✓ {label} EC mean {v:.3f} ≤ 0.4")
    yrca_ec = summary.get("yRCA", {}).get("ec_mean", 0.0)
    if yrca_ec >= 1.0:
        print(f"  ⚠ yRCA EC mean {yrca_ec:.3f} ≥ 1.0 (yRCA should not emit mitigation)")
    else:
        print(f"  ✓ yRCA EC mean {yrca_ec:.3f} < 1.0")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_explanation_completeness.csv"),
    )
    args = parser.parse_args(argv)

    rows, summary = evaluate(args.data.expanduser())
    write_csv(rows, args.out)
    sp_ac_ec = spearman(rows, "ac1", "ec_overall")
    sp_sg_ec = spearman(rows, "sg", "ec_overall")
    sp_sc_ec = spearman(rows, "sc", "ec_overall")
    print_summary(summary, sp_ac_ec, sp_sg_ec, sp_sc_ec)
    print(f"\nWrote {len(rows)} per-case rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
