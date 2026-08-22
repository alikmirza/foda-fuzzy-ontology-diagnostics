"""Per-case wall-clock instrumentation for FODA-FCP on RE1-TT (Section 4.8).

Measures the cost of the diagnostic computation itself — fuzzify, infer,
infer-topology, propagate, rank, explain — over the 125 RE1-TT cases, on the
largest system in the study (64 services). This is the scalability number the
conference version did not report.

Timing boundary: the clock covers the five FCP phases only. Case loading and
schema normalization are harness I/O rather than method cost, so they are timed
separately and reported in their own column instead of being folded in or
silently dropped. Onset detection sits inside the diagnostic boundary because
under the inject_time-removal contract (Deviation 0) it is the method's own
work, not an oracle the harness supplies.

Each case is run --repeats times and the per-case representative value is the
MEDIAN of those repeats, which suppresses scheduler noise without the
optimistic bias of taking a minimum. The reported aggregates are the mean and
the 95th percentile over the 125 per-case medians.

NOT deterministic, unlike the other regeneration scripts in this directory:
wall-clock varies with machine and load. Re-running reproduces the shape of the
distribution, not byte-identical output. The provenance row records the machine
the committed numbers were measured on.

Usage:
    PYTHONPATH=. python3 scripts/measure_runtime_tt.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-TT --out results
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import time
from pathlib import Path

import pandas as pd

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.methods.foda_fcp import (
    FodaFCPMethod, _fuzzify_service, _infer_hypothesis, _infer_topology,
    _has_cycle, _propagate_iterative, _propagate_damped, _rank, _build_explanation,
)


def machine_spec() -> dict:
    """Best-effort machine description for the provenance row."""
    spec = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "processor": platform.processor() or "unknown",
    }
    try:  # macOS
        spec["cpu"] = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
        mem = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
        spec["ram_gb"] = round(mem / 1024**3, 1)
        spec["cores"] = int(subprocess.check_output(["sysctl", "-n", "hw.ncpu"], text=True).strip())
    except Exception:
        pass
    return spec


def diagnose(norm, method) -> None:
    """One full FCP diagnostic pass. This is what the clock covers."""
    onset = detect_onset(norm.case_window, norm.services)
    fuzzy = {s: _fuzzify_service(norm.case_window, s, onset) for s in norm.services}
    hyp = {s: _infer_hypothesis(v) for s, v in fuzzy.items()}
    edges = _infer_topology(
        case_window=norm.case_window, services=norm.services, hypotheses=hyp,
        onset_time=onset, threshold=method.topology_threshold, lag=method.lag,
    )
    if _has_cycle(norm.services, edges):
        C = _propagate_iterative(hypotheses=hyp, services=norm.services, edges=edges,
                                 delta=method.damping_factor, max_iter=method.max_iterations)
    else:
        C = _propagate_damped(hypotheses=hyp, services=norm.services, edges=edges,
                              delta=method.damping_factor)
    ranked = _rank(C, hyp, norm.services)
    _build_explanation(services_ranked=ranked, hypotheses=hyp, fuzzy_vectors=fuzzy,
                       edges=edges, delta=method.damping_factor, top_k=method.top_k)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RE1-TT system directory")
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()

    method = FodaFCPMethod()
    rows = []
    for case in RCAEvalLoader(args.data.expanduser()).iter_cases():
        t0 = time.perf_counter()
        norm = normalize_case(case, window_seconds=method.window_seconds)
        normalize_ms = (time.perf_counter() - t0) * 1000.0

        samples = []
        for _ in range(args.repeats):
            t1 = time.perf_counter()
            diagnose(norm, method)
            samples.append((time.perf_counter() - t1) * 1000.0)

        rows.append({
            "system": "re1-tt",
            "case_id": case.id,
            "fault": case.ground_truth_fault_type,
            "n_services": len(norm.services),
            "diagnose_ms_median": round(statistics.median(samples), 4),
            "diagnose_ms_min": round(min(samples), 4),
            "diagnose_ms_max": round(max(samples), 4),
            "normalize_ms": round(normalize_ms, 4),
            "repeats": args.repeats,
        })
        print("  %-44s %8.2f ms" % (case.id, statistics.median(samples)), flush=True)

    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    csv_path = args.out / "runtime_tt_per_case.csv"
    df.to_csv(csv_path, index=False)

    med = df["diagnose_ms_median"]
    summary = {
        "system": "re1-tt",
        "n_cases": int(len(df)),
        "n_services": int(df["n_services"].max()),
        "repeats_per_case": args.repeats,
        "diagnose_ms_mean": round(float(med.mean()), 3),
        "diagnose_ms_p50": round(float(med.quantile(0.50)), 3),
        "diagnose_ms_p95": round(float(med.quantile(0.95)), 3),
        "diagnose_ms_min": round(float(med.min()), 3),
        "diagnose_ms_max": round(float(med.max()), 3),
        "normalize_ms_mean": round(float(df["normalize_ms"].mean()), 3),
        "machine": machine_spec(),
    }
    (args.out / "runtime_tt_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    pd.DataFrame([{k: v for k, v in summary.items() if k != "machine"}]).to_csv(
        args.out / "runtime_tt_summary.csv", index=False)

    print("\n" + json.dumps(summary, indent=2))
    print("\nwrote %s, runtime_tt_summary.{csv,json}" % csv_path)


if __name__ == "__main__":
    main()
