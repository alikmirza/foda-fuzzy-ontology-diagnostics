"""Phase 2 Week 2 — score SemanticCoherence (and report alongside
SemanticGroundedness) for every method on RE1-OB.

Runs all seven Phase-1 method adapters over the same 125 RE1-OB
cases and scores each emitted :class:`CanonicalExplanation` on both
SG and SC. Saves the joined per-case rows to
``results/phase2_semantic_coherence.csv``; prints per-method
aggregates, the 5×7 per-fault matrix, and the two cross-method
correlations (ρ(AC@1, SC) and ρ(SG, SC)).

The per-case CSV mirrors the Week 1 CSV's schema and adds seven SC
columns: ``sc_overall``, ``coherent_links``, ``incoherent_links``,
``unmapped_links``, ``excluded_mitigation_links``,
``scored_link_count``, ``link_count``. The SG column is preserved
so downstream analyses don't need to join two CSVs.

The metric is the variant-4 typicality scorer (see
:mod:`evaluation.metrics.semantic_coherence`): mitigation links are
dropped from the denominator and coherent propagation links are
credited the ontology's typicality strength (0.5 or 1.0).

Usage::

    python -m evaluation.experiments.run_phase2_sc \\
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-OB \\
        --out results/phase2_semantic_coherence.csv
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
    OntologyAdapter,
    SemanticCoherence,
    SemanticGroundedness,
    accuracy_at_k,
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


def evaluate(
    data_path: Path,
    sg: SemanticGroundedness | None = None,
    sc: SemanticCoherence | None = None,
    ontology: OntologyAdapter | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    """Run all seven methods × every RE1-OB case and score both SG and
    SC.

    Returns ``(rows, summary)``. ``rows`` is a list of per-case
    records; ``summary`` is the per-method aggregate ready for
    :func:`print_summary`.
    """
    sg = sg or SemanticGroundedness()
    sc = sc or SemanticCoherence()
    ontology = ontology or OntologyAdapter()
    loader = RCAEvalLoader(data_path)
    cases = list(loader.iter_cases())
    if not cases:
        raise RuntimeError(f"no cases under {data_path}")

    rows: list[dict[str, Any]] = []

    # --- six single-shot methods ---
    for label, factory in _SINGLE_SHOT_METHODS.items():
        method = factory()
        window_s = method.window_seconds
        norms = [normalize_case(c, window_seconds=window_s) for c in cases]
        for case, norm in zip(cases, norms):
            out = method.diagnose_normalized(norm)
            rows.append(_score_row(label, case, out, sg, sc, ontology))

    # --- DejaVu via 5-fold stratified CV ---
    rows.extend(_dejavu_rows(cases, sg, sc, ontology))

    summary = _summarize(rows)
    return rows, summary


def _score_row(
    method_label: str,
    case: BenchmarkCase,
    out: DiagnosticOutput,
    sg: SemanticGroundedness,
    sc: SemanticCoherence,
    ontology: OntologyAdapter,
) -> dict[str, Any]:
    sg_br = sg.score_with_breakdown(out.explanation_chain, ontology)
    sc_br = sc.score_with_breakdown(out.explanation_chain, ontology)
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
        "sg": sg_br["overall"],
        "sc_overall": sc_br["overall"],
        "coherent_links": sc_br["coherent_links"],
        "incoherent_links": sc_br["incoherent_links"],
        "unmapped_links": sc_br["unmapped_links"],
        "excluded_mitigation_links": sc_br["excluded_mitigation_links"],
        "scored_link_count": sc_br["scored_link_count"],
        "link_count": sc_br["link_count"],
    }


# ---- DejaVu CV (same as Week 1 harness) ----


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
            rows.append(_score_row("DejaVu", cases[i], out, sg, sc, ontology))
    return rows


# ---- aggregation ----


def _summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_method[r["method"]].append(r)
    out: dict[str, dict[str, float]] = {}
    for method, rs in by_method.items():
        sc_vals = [r["sc_overall"] for r in rs]
        by_fault: dict[str, list[float]] = defaultdict(list)
        for r in rs:
            by_fault[r["fault"]].append(r["sc_overall"])
        out[method] = {
            "n": float(len(rs)),
            "sc_mean": statistics.mean(sc_vals),
            "sc_std": statistics.stdev(sc_vals) if len(sc_vals) > 1 else 0.0,
            "sg_mean": statistics.mean(r["sg"] for r in rs),
            "ac1_mean": statistics.mean(r["ac1"] for r in rs),
            "coherent_mean":    statistics.mean(r["coherent_links"] for r in rs),
            "incoherent_mean":  statistics.mean(r["incoherent_links"] for r in rs),
            "unmapped_mean":    statistics.mean(r["unmapped_links"] for r in rs),
            "excluded_mitigation_mean":
                statistics.mean(r["excluded_mitigation_links"] for r in rs),
            "scored_link_mean":
                statistics.mean(r["scored_link_count"] for r in rs),
            "link_count_mean":  statistics.mean(r["link_count"] for r in rs),
            **{f"sc_{fault}": statistics.mean(vs) for fault, vs in by_fault.items()},
        }
    return out


def spearman(rows: list[dict[str, Any]], x_key: str, y_key: str) -> float:
    """Tie-aware Spearman rank correlation between two per-row columns."""
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

    x_ranks = _ranks([p[0] for p in pairs])
    y_ranks = _ranks([p[1] for p in pairs])
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
        "method", "case_id", "fault", "ac1", "sg", "sc_overall",
        "coherent_links", "incoherent_links", "unmapped_links",
        "excluded_mitigation_links", "scored_link_count", "link_count",
    ]
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def print_summary(
    summary: dict[str, dict[str, float]],
    spearman_ac_sc: float,
    spearman_sg_sc: float,
) -> None:
    method_order = ["MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP"]
    faults = sorted({k[3:] for v in summary.values() for k in v if k.startswith("sc_") and k not in ("sc_mean", "sc_std")})

    print(f"\n{'Method':<10} {'n':>5} {'SC_mean':>9} {'SC_std':>8} "
          f"{'SG_mean':>9} {'AC@1':>7} "
          f"{'coh':>6} {'incoh':>7} {'unmap':>7} {'excl_mit':>10} "
          f"{'scored':>7} {'links':>7}")
    print("-" * 110)
    for m in method_order:
        if m not in summary:
            continue
        r = summary[m]
        print(
            f"{m:<10} {int(r['n']):>5} {r['sc_mean']:>9.3f} {r['sc_std']:>8.3f} "
            f"{r['sg_mean']:>9.3f} {r['ac1_mean']:>7.3f} "
            f"{r['coherent_mean']:>6.2f} {r['incoherent_mean']:>7.2f} "
            f"{r['unmapped_mean']:>7.2f} {r['excluded_mitigation_mean']:>10.2f} "
            f"{r['scored_link_mean']:>7.2f} {r['link_count_mean']:>7.2f}"
        )

    print(f"\nPer-fault SC mean (rows = method, cols = fault):")
    header = f"{'Method':<10} " + " ".join(f"{f:>8}" for f in faults)
    print(header)
    print("-" * len(header))
    for m in method_order:
        if m not in summary:
            continue
        cells = [f"{m:<10}"]
        for f in faults:
            v = summary[m].get(f"sc_{f}", float("nan"))
            cells.append(f"{v:>8.3f}")
        print(" ".join(cells))

    n_total = int(sum(summary[m]["n"] for m in summary))
    print(f"\nSpearman rank correlations (over all {n_total} case-method pairs):")
    print(f"  ρ(AC@1, SC) = {spearman_ac_sc:+.3f}")
    print(f"  ρ(SG,   SC) = {spearman_sg_sc:+.3f}")
    if spearman_sg_sc > 0.8:
        print("  → ρ(SG, SC) > 0.8 — SC may be redundant with SG")
    elif spearman_sg_sc > 0.5:
        print("  → ρ(SG, SC) > 0.5 — SC partially overlaps with SG but adds signal")
    else:
        print("  → ρ(SG, SC) ≤ 0.5 — SC is a distinct measurement axis from SG")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_semantic_coherence.csv"),
    )
    args = parser.parse_args(argv)

    rows, summary = evaluate(args.data.expanduser())
    write_csv(rows, args.out)
    sp_ac_sc = spearman(rows, "ac1", "sc_overall")
    sp_sg_sc = spearman(rows, "sg", "sc_overall")
    print_summary(summary, sp_ac_sc, sp_sg_sc)
    print(f"\nWrote {len(rows)} per-case rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
