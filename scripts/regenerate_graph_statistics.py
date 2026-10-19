"""Inferred-graph statistics and propagation convergence for FODA-FCP.

Theorem 1 of the method paper (global contraction, rho <= delta) assumes every
row sum sum_t w(s,t) <= 1. The topology FODA-FCP infers on RCAEval carries raw
|lagged_corr| >= threshold edge weights and is not row-normalised. This script
measures, per case and at the shipped configuration, how far the evaluated
graphs are from that assumption and how the propagation actually behaves on
them:

  graph     n_services, n_edges, density, cyclic, max_out_degree,
            max_row_sum, median_row_sum (over services with callees),
            frac_services_row_sum_gt1 (over all services)
  Jacobi    iterations, hit_max_iter, final_residual, min_step
            (cyclic cases only; min_step < 0 would mean an iterate decreased)
  ranking   n_saturated (services with C >= 1 - 1e-12),
            n_saturated_H_lt_1 (of those, services whose local H < 1)

Every case is cross-checked against FodaFCPMethod.diagnose_normalized: the
confidence vector this script computes must equal the method's own, or the
script aborts.

Deterministic: no RNG on this path. Re-running reproduces byte-identical
output for a given commit.

Usage:
    PYTHONPATH=. python3 scripts/regenerate_graph_statistics.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from pathlib import Path

import pandas as pd

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.methods.foda_fcp import (
    FodaFCPMethod, _fuzzify_service, _infer_hypothesis, _infer_topology,
    _has_cycle, _propagate_iterative, _propagate_damped,
)

SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
SATURATION_TOL = 1e-12


def case_row(tag: str, case, method: FodaFCPMethod) -> dict:
    norm = normalize_case(case, window_seconds=method.window_seconds)
    services = norm.services
    onset = detect_onset(norm.case_window, services)
    fuzzy = {s: _fuzzify_service(norm.case_window, s, onset) for s in services}
    hyp = {s: _infer_hypothesis(v) for s, v in fuzzy.items()}
    edges = _infer_topology(
        case_window=norm.case_window, services=services, hypotheses=hyp,
        onset_time=onset, threshold=method.topology_threshold, lag=method.lag,
    )

    row_sum: dict[str, float] = defaultdict(float)
    out_deg: dict[str, int] = defaultdict(int)
    for (u, _v), w in edges.items():
        row_sum[u] += w
        out_deg[u] += 1
    sums = list(row_sum.values())
    n = len(services)
    cyclic = _has_cycle(services, edges)

    trace: list[dict[str, float]] = []
    if cyclic:
        C = _propagate_iterative(
            hypotheses=hyp, services=services, edges=edges,
            delta=method.damping_factor, max_iter=method.max_iterations, trace=trace,
        )
    else:
        C = _propagate_damped(
            hypotheses=hyp, services=services, edges=edges, delta=method.damping_factor,
        )

    reference = method.diagnose_normalized(norm).raw_output["final_confidence_C"]
    if reference != C:
        raise SystemExit(f"{case.id}: confidence vector differs from diagnose_normalized")

    H = {s: hyp[s].local_confidence for s in services}
    saturated = [s for s in services if C[s] >= 1.0 - SATURATION_TOL]
    return {
        "system": tag,
        "case_id": case.id,
        "fault": case.ground_truth_fault_type,
        "n_services": n,
        "n_edges": len(edges),
        "density": round(len(edges) / (n * (n - 1)), 6) if n > 1 else 0.0,
        "cyclic": cyclic,
        "max_out_degree": max(out_deg.values(), default=0),
        "max_row_sum": round(max(sums, default=0.0), 6),
        "median_row_sum": round(statistics.median(sums), 6) if sums else 0.0,
        "frac_services_row_sum_gt1": round(sum(x > 1.0 for x in sums) / n, 6),
        "iterations": len(trace) if cyclic else None,
        "hit_max_iter": (len(trace) == method.max_iterations
                         and trace[-1]["residual"] >= 1e-6) if cyclic else None,
        "final_residual": trace[-1]["residual"] if cyclic else None,
        "min_step": min(r["min_step"] for r in trace) if cyclic else None,
        "n_saturated": len(saturated),
        "n_saturated_H_lt_1": sum(H[s] < 1.0 for s in saturated),
    }


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for tag, g in df.groupby("system", sort=False):
        cyc = g[g["cyclic"]]
        rows.append({
            "system": tag,
            "n_cases": len(g),
            "n_services": int(g["n_services"].iloc[0]),
            "median_edges": float(g["n_edges"].median()),
            "max_edges": int(g["n_edges"].max()),
            "median_density": round(float(g["density"].median()), 4),
            "cases_cyclic": int(g["cyclic"].sum()),
            "cases_all_row_sums_le1": int((g["max_row_sum"] <= 1.0).sum()),
            "median_max_row_sum": round(float(g["max_row_sum"].median()), 3),
            "max_max_row_sum": round(float(g["max_row_sum"].max()), 3),
            "median_frac_services_row_sum_gt1": round(float(g["frac_services_row_sum_gt1"].median()), 3),
            "median_max_out_degree": float(g["max_out_degree"].median()),
            "median_iterations_cyclic": float(cyc["iterations"].median()) if len(cyc) else None,
            "max_iterations_cyclic": int(cyc["iterations"].max()) if len(cyc) else None,
            "cases_hit_max_iter": int(cyc["hit_max_iter"].sum()) if len(cyc) else 0,
            "min_step_over_cases": float(cyc["min_step"].min()) if len(cyc) else None,
            "cases_with_saturation": int((g["n_saturated"] > 0).sum()),
            "cases_saturated_H_lt_1": int((g["n_saturated_H_lt_1"] > 0).sum()),
        })
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RCAEval RE1 data root")
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    method = FodaFCPMethod()
    rows = []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            rows.append(case_row(tag, case, method))
        print(f"[{tag}] done", flush=True)

    df = pd.DataFrame(rows)
    df.to_csv(args.out / "graph_stats_per_case.csv", index=False)
    summary = summarise(df)
    summary.to_csv(args.out / "graph_stats_summary.csv", index=False)
    print(summary.T.to_string(header=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
