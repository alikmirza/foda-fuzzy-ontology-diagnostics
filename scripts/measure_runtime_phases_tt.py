"""Per-phase wall-clock for FODA-FCP on RE1-TT: where the 345 ms per case goes.

Times each phase of the diagnostic path separately over all 125 RE1-TT cases
(64 services): onset detection, fuzzification, Mamdani inference, topology
inference, propagation, ranking and explanation assembly. Each case is run
--repeats times; the per-case value of each phase is the median over repeats,
and the aggregates are means over the 125 per-case medians plus each phase's
share of the summed mean.

Like measure_runtime_tt.py this is NOT deterministic: wall-clock depends on
the machine and its load. The machine is recorded in the summary JSON.

Usage:
    PYTHONPATH=. python3 scripts/measure_runtime_phases_tt.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-TT --out results
"""
from __future__ import annotations

import argparse, json, statistics, time
from pathlib import Path

import pandas as pd

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.methods.foda_fcp import (
    FodaFCPMethod, _fuzzify_service, _infer_hypothesis, _infer_topology,
    _has_cycle, _propagate_iterative, _propagate_damped, _rank, _build_explanation,
)
from scripts.measure_runtime_tt import machine_spec

PHASES = ("onset", "fuzzify", "infer", "topology", "propagate", "rank", "explain")


def timed_pass(norm, m) -> dict:
    t = {}
    a = time.perf_counter(); onset = detect_onset(norm.case_window, norm.services); t["onset"] = time.perf_counter() - a
    a = time.perf_counter(); fz = {s: _fuzzify_service(norm.case_window, s, onset) for s in norm.services}; t["fuzzify"] = time.perf_counter() - a
    a = time.perf_counter(); hy = {s: _infer_hypothesis(v) for s, v in fz.items()}; t["infer"] = time.perf_counter() - a
    a = time.perf_counter()
    ed = _infer_topology(case_window=norm.case_window, services=norm.services, hypotheses=hy,
                         onset_time=onset, threshold=m.topology_threshold, lag=m.lag)
    t["topology"] = time.perf_counter() - a
    a = time.perf_counter()
    if _has_cycle(norm.services, ed):
        C = _propagate_iterative(hypotheses=hy, services=norm.services, edges=ed,
                                 delta=m.damping_factor, max_iter=m.max_iterations)
    else:
        C = _propagate_damped(hypotheses=hy, services=norm.services, edges=ed, delta=m.damping_factor)
    t["propagate"] = time.perf_counter() - a
    a = time.perf_counter(); r = _rank(C, hy, norm.services); t["rank"] = time.perf_counter() - a
    a = time.perf_counter()
    _build_explanation(services_ranked=r, hypotheses=hy, fuzzy_vectors=fz, edges=ed,
                       delta=m.damping_factor, top_k=m.top_k)
    t["explain"] = time.perf_counter() - a
    return {k: v * 1000.0 for k, v in t.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()
    m = FodaFCPMethod(); rows = []
    for case in RCAEvalLoader(args.data.expanduser()).iter_cases():
        norm = normalize_case(case, window_seconds=m.window_seconds)
        runs = [timed_pass(norm, m) for _ in range(args.repeats)]
        row = {"case_id": case.id, "n_services": len(norm.services)}
        row.update({f"{p}_ms": round(statistics.median(r[p] for r in runs), 4) for p in PHASES})
        rows.append(row)
    df = pd.DataFrame(rows); args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "runtime_tt_phases_per_case.csv", index=False)
    means = {p: float(df[f"{p}_ms"].mean()) for p in PHASES}; total = sum(means.values())
    summary = {"system": "re1-tt", "n_cases": len(df), "repeats_per_case": args.repeats,
               "phase_mean_ms": {p: round(v, 3) for p, v in means.items()},
               "phase_share_pct": {p: round(100 * v / total, 2) for p, v in means.items()},
               "fcp_reasoning_share_pct": round(100 * sum(means[p] for p in ("fuzzify", "infer", "propagate", "rank", "explain")) / total, 2),
               "total_mean_ms": round(total, 3), "machine": machine_spec()}
    (args.out / "runtime_tt_phases_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
