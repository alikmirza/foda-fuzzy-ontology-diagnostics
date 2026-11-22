"""Is the call-graph gain evidence, or a prior on much-called services?

In the reversed direction a service absorbs support from its callers. A service
with many callers therefore gains more, whatever its callers show. RE1 injects
faults into five services per system, and they are mostly services that others
call, so part of the gain could be a degree prior that happens to fit the
benchmark. Three controls separate the two, for the configuration fixed in
advance (probabilistic sum, reversed, unit weights, delta = 0.3):

  one_step       C(s) = H(s) (+) (+)_callers delta * H(t): the update without
                 iteration, to show that the controls below, which are one-step,
                 are comparable with the iterated result.
  degree_prior   every caller's evidence replaced by the case's mean H: support
                 depends only on how many callers a service has.
  degree_tiebreak  rank by H, ties broken by the number of callers.
  permuted       callers' evidence drawn from a random relabelling of H over the
                 services (200 permutations, seed 42): the graph and the evidence
                 values are kept, which caller is anomalous is not.

Graphs: the trace graphs of Online Boutique and Train Ticket, and the documented
Sock Shop graph. Differences use the cluster bootstrap over the 25 scenarios.

Usage:
    PYTHONPATH=. python3 scripts/tracegraph_controls.py --data ~/research/rcaeval-tools/RCAEval/data/RE1
Writes results/tracegraph_controls.csv and results/tracegraph_controls_per_case.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from scripts import run_direction_variants as dv
from scripts.analyse_kes_revision import boot
from scripts.run_propagation_variants import prepare
from scripts.run_tracegraph_variants import load_edges

RESULTS = Path(__file__).resolve().parent.parent / "results"
DELTA, N_PERM, SEED = 0.3, 200, 42


def expected_ac1(score: dict, gt: str) -> float:
    top = max(score.values())
    return 1.0 / sum(1 for v in score.values() if v == top) if score[gt] == top else 0.0


def one_step(H: dict, callers: dict, evidence: dict) -> dict:
    out = {}
    for s, h in H.items():
        keep = 1.0 - h
        for t in callers.get(s, ()):
            keep *= 1.0 - DELTA * evidence[t]
        out[s] = 1.0 - keep
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args()
    method, ont = dv.fcp.FodaFCPMethod(), dv.OntologyAdapter()
    graphs = {**load_edges(), "re1-ss": {e: 1.0 for e in dv.CALLS_SS}}
    rng = np.random.default_rng(SEED)
    rows = []
    for sysdir, tag in dv.SYSTEMS:
        for case in dv.RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            norm, _, _, hyp = prepare(case, method)
            services, gt = list(norm.services), case.ground_truth_root_cause
            H = {s: hyp[s].local_confidence for s in services}
            present = set(services)
            edges = {(a, b): 1.0 for (a, b) in graphs[tag] if a in present and b in present}
            callers = {}
            for a, b in edges:                                  # reversed: the callee b absorbs from its caller a
                callers.setdefault(b, []).append(a)
            out, directed = dv.senders_of(edges, "reversed", "unit", "none", hyp, ont)
            cyclic = dv.fcp._has_cycle(services, directed)
            order = None if cyclic else dv.fcp._reverse_topo_order(services, directed)
            C, _, _ = dv.propagate("probsum", services, H, out, DELTA, cyclic, order)
            mean_h = float(np.mean(list(H.values())))
            k = {s: len(callers.get(s, ())) for s in services}
            vals = np.array([H[s] for s in services])
            perm = 0.0
            for _ in range(N_PERM):
                shuffled = dict(zip(services, rng.permutation(vals)))
                perm += expected_ac1(one_step(H, callers, shuffled), gt)
            rows.append({"system": tag, "case_id": case.id, "scenario": f"{gt}_{case.ground_truth_fault_type}",
                         "root_callers": k[gt], "max_callers": max(k.values()),
                         "local": expected_ac1(H, gt), "propagated": expected_ac1(C, gt),
                         "one_step": expected_ac1(one_step(H, callers, H), gt),
                         "degree_prior": expected_ac1(one_step(H, callers, {s: mean_h for s in services}), gt),
                         "degree_tiebreak": expected_ac1({s: (H[s], k[s]) for s in services}, gt),
                         "permuted": perm / N_PERM})
        print(f"[{tag}] done", flush=True)
    df = pd.DataFrame(rows)
    df.round(6).to_csv(RESULTS / "tracegraph_controls_per_case.csv", index=False)
    summary = []
    for system, g in df.groupby("system", sort=False):
        row = {"system": system, "root_callers_mean": g.root_callers.mean(),
               "callers_mean_all_services": np.nan}
        for col in ("local", "propagated", "one_step", "degree_prior", "degree_tiebreak", "permuted"):
            row[col] = g[col].mean()
        for a, b in (("propagated", "local"), ("degree_prior", "local"), ("degree_tiebreak", "local"),
                     ("permuted", "local"), ("propagated", "degree_prior"), ("propagated", "degree_tiebreak"),
                     ("propagated", "permuted")):
            d, lo, hi, p = boot(g[a] - g[b], g.scenario)
            row.update({f"{a}_minus_{b}": d, f"{a}_minus_{b}_lo": lo, f"{a}_minus_{b}_hi": hi, f"{a}_minus_{b}_p": p})
        summary.append(row)
    summary = pd.DataFrame(summary).drop(columns=["callers_mean_all_services"])
    summary.round(4).to_csv(RESULTS / "tracegraph_controls.csv", index=False)
    pd.set_option("display.width", 250)
    print(summary.round(3).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
