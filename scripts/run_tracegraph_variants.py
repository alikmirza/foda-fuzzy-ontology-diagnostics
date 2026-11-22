"""Direction of propagation on call graphs measured from traces.

The call graphs of scripts/run_direction_variants.py came from a demonstration
deployment (Online Boutique) and from documentation (Sock Shop), and Train
Ticket had none. Here the graphs are the calls observed in RCAEval's RE2 traces
before fault injection (scripts/extract_re2_call_graphs.py), applied to the RE1
cases of the same applications:

  trace      the measured service-to-service calls
  trace_db   the same, plus an edge from a service to its own datastore where
             RE1 has one as a separate node (ts-x-service -> ts-x-mongo/-mysql,
             cartservice -> redis). Traces do not show these calls; the edges
             are architecture knowledge and this graph is a sensitivity check.

Everything else is the code of run_direction_variants.py: the same hypotheses,
operators, damping grid, directions, guidance and scoring. Weights per receiver
are unit, equal, or share (trace call counts; not defined for trace_db).

The confirmatory question is fixed in advance: the configuration chosen across
Online Boutique and Sock Shop on the earlier call graphs (probabilistic sum,
reversed direction, unit weights, delta = 0.3) is applied unchanged. Train
Ticket took no part in choosing it.

Usage:
    PYTHONPATH=. python3 scripts/run_tracegraph_variants.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
Writes results/tracegraph_variants_per_case.csv.gz and _summary.csv.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from scripts import run_direction_variants as dv
from scripts.run_propagation_variants import DELTAS, prepare

fcp = dv.fcp
RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-TT", "re1-tt"))


def load_edges() -> dict:
    e = pd.read_csv(RESULTS / "re2_call_graph_edges.csv")
    e = e[e.calls_pre > 0]
    return {tag: {(r.caller, r.callee): float(r.calls_pre) for r in g.itertuples()} for tag, g in e.groupby("system")}


def datastore_edges(services) -> dict:
    present, out = set(services), {}
    for s in services:
        if s.endswith("-service"):
            for suffix in ("-mongo", "-mysql"):
                d = s[: -len("-service")] + suffix
                if d in present:
                    out[(s, d)] = 1.0
    if {"cartservice", "redis"} <= present:
        out[("cartservice", "redis")] = 1.0
    return out


def run_case(tag, case, method, ont, calls):
    norm, onset, fuzzy, hyp = prepare(case, method)
    services, gt = norm.services, case.ground_truth_root_cause
    H = {s: hyp[s].local_confidence for s in services}
    h_max = max(H.values())
    local_top = {s for s in services if H[s] == h_max}
    base = {"system": tag, "case_id": case.id, "fault": case.ground_truth_fault_type, "root": gt,
            "any_fired": h_max > 0.0, "gt_fired": H[gt] > 0.0, "gt_H": H[gt]}
    row, _ = dv.score(services, H, hyp, fuzzy, gt, local_top,
                      {**base, "graph": "none", "direction": "none", "weights": "none", "guidance": "none",
                       "operator": "local", "delta": 0.0, "n_edges": 0, "rounds": 0, "hit_cap": False})
    rows = [row]
    present = set(services)
    trace = {(a, b): n for (a, b), n in calls.items() if a in present and b in present}
    graphs = (("trace", trace, ("unit", "equal", "share")),
              ("trace_db", {**trace, **datastore_edges(services)}, ("unit", "equal")))
    for graph, edges, weight_modes in graphs:
        for direction in dv.DIRECTIONS:
            for weights in weight_modes:
                for guidance in dv.GUIDANCE:
                    out, directed = dv.senders_of(edges, direction, weights, guidance, hyp, ont)
                    cyclic = fcp._has_cycle(services, directed)
                    order = None if cyclic else fcp._reverse_topo_order(services, directed)
                    for op in (dv.OPERATORS if guidance == "none" else ("probsum",)):
                        for delta in DELTAS:
                            C, rounds, hit = dv.propagate(op, services, H, out, delta, cyclic, order)
                            row, _ = dv.score(services, C, hyp, fuzzy, gt, local_top, {
                                **base, "graph": graph, "direction": direction, "weights": weights,
                                "guidance": guidance, "operator": op, "delta": delta,
                                "n_edges": len(edges), "rounds": rounds, "hit_cap": hit})
                            rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method, ont, calls = fcp.FodaFCPMethod(), dv.OntologyAdapter(), load_edges()
    rows = []
    for sysdir, tag in SYSTEMS:
        for case in dv.RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            rows += run_case(tag, case, method, ont, calls[tag])
        print(f"[{tag}] done", flush=True)
    df = pd.DataFrame(rows)

    # the local-evidence rows must be those of the committed direction experiment
    ref = pd.read_csv(RESULTS / "direction_variants_per_case.csv.gz")
    ref = ref[ref.operator == "local"].set_index("case_id")
    mine = df[df.operator == "local"].set_index("case_id")
    assert len(mine) == 250 and set(mine.index) <= set(ref.index)
    for col in ("ac1", "ac1_expected", "ac3", "ac5", "n_above", "gt_block"):
        assert (mine[col] - ref.loc[mine.index, col]).abs().max() < 1e-12, col
    print("local evidence reproduces the committed direction experiment", flush=True)

    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "tracegraph_variants_per_case.csv.gz", index=False)
    keys = ["graph", "system", "direction", "weights", "guidance", "operator", "delta"]
    summary = (df.groupby(keys, sort=False)
                 .agg(cases=("case_id", "count"), n_edges=("n_edges", "median"), ac1=("ac1", "mean"),
                      ac1_expected=("ac1_expected", "mean"), ac3=("ac3", "mean"), ac5=("ac5", "mean"),
                      mrr=("rr", "mean"), top_block=("top_block", "mean"), n_saturated=("n_saturated", "mean"),
                      max_rounds=("rounds", "max"), hit_cap=("hit_cap", "sum"))
                 .round(6).reset_index())
    summary.to_csv(args.out / "tracegraph_variants_summary.csv", index=False)
    print(f"{len(df)} rows; runs at the iteration cap: {int(df.hit_cap.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
