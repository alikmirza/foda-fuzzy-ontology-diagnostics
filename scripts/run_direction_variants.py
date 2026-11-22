"""Direction of propagation, on the inferred graph and on real call graphs.

The propagation update gives a service ("receiver") support from other services
("senders"). Which services send to which is a modelling choice that the papers
left implicit, and it is the variable studied here.

Graphs. Every graph is a set of directed edges (s, t).
  inferred   (s, t) means s's anomaly signal leads t's by one sample, with weight
             |lagged correlation| >= 0.5 (the evaluated configuration).
  callgraph  (s, t) means s calls t. Online Boutique: the calls measured by Istio
             in the product demo on 2026-11-05 (request counts). Sock Shop: its
             published architecture, with per-request call multiplicities read
             from its code. Train Ticket has no call graph available, so
             callgraph covers RE1-OB and RE1-SS only.

Direction.
  forward    the receiver of edge (s, t) is s: a service absorbs from the
             services it leads (inferred) or calls (callgraph). This is the
             evaluated configuration and the papers' Eq. (1).
  reversed   the receiver is t: a service absorbs from the services that lead
             it or call it.

Weights, normalised per receiver over its senders.
  inferred:  raw (|corr|, evaluated), rownorm (w / sum), capped (w / max(1, sum))
  callgraph: unit (1 per call edge), equal (unit / number of senders),
             share (measured or code call counts / their sum)

Ontology guidance multiplies each weight by a DiagnosticKB propagation strength
between the two services' rule-derived fault prototypes (1.0 for equal
prototypes, 0 when either has none).
  none
  s2r   strength(sender's prototype -> receiver's prototype)   [as first run]
  r2s   strength(receiver's prototype -> sender's prototype)

Operators and the damping grid are those of scripts/run_propagation_variants.py.
Local evidence alone (C = H) is recorded once per case as operator "local".

Per case: the ground truth's pessimistic rank, AC@1, expected AC@1 under random
tie-breaking, AC@3, AC@5, reciprocal rank, top tie block size, saturated
services, Jacobi rounds and whether the cap of 100 was reached.

Cross-check, fatal on mismatch: inferred / forward / {none, s2r} / {raw, rownorm}
must equal results/propagation_variants_per_case.csv.gz on AC@1, expected AC@1
and the saturation count for every operator, damping level and case.

Deterministic: no RNG.

Usage:
    PYTHONPATH=. python3 scripts/run_direction_variants.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import pandas as pd

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.metrics import OntologyAdapter
from scripts.run_propagation_variants import (
    DELTAS, EPSILON, MAX_ITER, OPERATORS, SATURATION_TOL, prepare, transmit, update,
)

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
DIRECTIONS = ("forward", "reversed")
GUIDANCE = ("none", "s2r", "r2s")

#: Online Boutique: requests between services over 20 minutes of the product
#: demo, istio_requests_total at 2026-11-05T08:44Z (foda-diagnostics,
#: product/benchmarks/2026-11-05-callee-blame). cartservice -> redis is TCP,
#: which Istio does not count; it is the cart's only outbound call.
CALLS_OB = {
    ("frontend", "adservice"): 5446, ("frontend", "cartservice"): 8484,
    ("frontend", "checkoutservice"): 309, ("frontend", "currencyservice"): 27574,
    ("frontend", "productcatalogservice"): 44257, ("frontend", "recommendationservice"): 6775,
    ("frontend", "shippingservice"): 2028, ("checkoutservice", "cartservice"): 615,
    ("checkoutservice", "currencyservice"): 1104, ("checkoutservice", "emailservice"): 307,
    ("checkoutservice", "paymentservice"): 309, ("checkoutservice", "productcatalogservice"): 796,
    ("checkoutservice", "shippingservice"): 615, ("recommendationservice", "productcatalogservice"): 6773,
    ("cartservice", "redis"): 1.0,
}
#: Sock Shop: published architecture, calls per request as its code makes them
#: (foda-diagnostics, product/benchmarks/2026-11-16-sock-shop-callee-blame).
CALLS_SS = {
    ("front-end", "catalogue"): 6, ("front-end", "carts"): 3, ("front-end", "user"): 2,
    ("front-end", "orders"): 1, ("front-end", "session-db"): 2, ("orders", "user"): 3,
    ("orders", "carts"): 1, ("orders", "payment"): 1, ("orders", "shipping"): 1,
    ("orders", "orders-db"): 1, ("carts", "carts-db"): 1, ("catalogue", "catalogue-db"): 1,
    ("user", "user-db"): 1, ("shipping", "rabbitmq"): 1, ("queue-master", "rabbitmq"): 1,
}
CALLS = {"re1-ob": CALLS_OB, "re1-ss": CALLS_SS}


def senders_of(edges, direction, weights, guidance, hyp, ont):
    """receiver -> [(sender, weight, gate)], and the directed edge set used."""
    directed = edges if direction == "forward" else {(t, s): w for (s, t), w in edges.items()}
    raw = defaultdict(list)
    for (r, x), w in directed.items():
        raw[r].append((x, w))
    out = {}
    for r, lst in raw.items():
        total = sum(w for _, w in lst)
        row = []
        for x, w in lst:
            if weights in ("rownorm", "share"):
                w = w / total
            elif weights == "capped":
                w = w / max(1.0, total)
            elif weights == "equal":
                w = 1.0 / len(lst)
            elif weights == "unit":
                w = 1.0
            g = 1.0
            if guidance != "none":
                pr = fcp.CATEGORY_TO_FAULT.get(hyp[r].dominant_category)
                px = fcp.CATEGORY_TO_FAULT.get(hyp[x].dominant_category)
                if pr is None or px is None:
                    g = 0.0
                elif pr != px:
                    a, b = (px, pr) if guidance == "s2r" else (pr, px)
                    g = ont.get_propagation_strength(fcp._ontology_uri(a), fcp._ontology_uri(b))
            row.append((x, w, g))
        out[r] = row
    return out, directed


def propagate(op, services, H, out, delta, cyclic, order):
    C = dict(H)
    if not cyclic:
        for s in order:
            if out.get(s):
                C[s] = update(op, C[s], [transmit(op, w, delta, g, C.get(t, 0.0)) for t, w, g in out[s]])
        return C, 0, False
    for k in range(1, MAX_ITER + 1):
        nxt = {s: update(op, H[s], [transmit(op, w, delta, g, C.get(t, 0.0)) for t, w, g in out.get(s, [])])
               for s in services}
        residual = max(abs(nxt[s] - C[s]) for s in services)
        C = nxt
        if residual < EPSILON:
            return C, k, False
    return C, MAX_ITER, True


def score(services, C, hyp, gt, extra):
    ranked = fcp._rank(C, hyp, services)
    scores = [c for _, c in ranked]
    gt_score = C[gt]
    rank = max(i for i, c in enumerate(scores) if c == gt_score) + 1     # pessimistic
    block = sum(1 for c in scores if c == scores[0])
    row = {"rank": rank, "ac1": float(rank == 1), "ac1_expected": 1.0 / block if gt_score == scores[0] else 0.0,
           "ac3": float(rank <= 3), "ac5": float(rank <= 5), "rr": 1.0 / rank, "top_block": block,
           "n_saturated": sum(1 for c in scores if c >= 1.0 - SATURATION_TOL)}
    row.update(extra)
    return row


def run_case(tag, case, method, ont):
    norm, onset, _fuzzy, hyp = prepare(case, method)
    services, gt = norm.services, case.ground_truth_root_cause
    H = {s: hyp[s].local_confidence for s in services}
    base = {"system": tag, "case_id": case.id, "fault": case.ground_truth_fault_type, "root": gt}
    rows = [score(services, H, hyp, gt, {**base, "graph": "none", "direction": "none", "weights": "none",
                                         "guidance": "none", "operator": "local", "delta": 0.0,
                                         "n_edges": 0, "rounds": 0, "hit_cap": False})]
    graphs = [("inferred", fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                               onset_time=onset, threshold=method.topology_threshold,
                                               lag=method.lag), ("raw", "rownorm", "capped"))]
    if tag in CALLS:
        present = set(services)
        calls = {(a, b): float(n) for (a, b), n in CALLS[tag].items() if a in present and b in present}
        graphs.append(("callgraph", calls, ("unit", "equal", "share")))
    for graph, edges, weight_modes in graphs:
        for direction in DIRECTIONS:
            for weights in weight_modes:
                for guidance in GUIDANCE:
                    out, directed = senders_of(edges, direction, weights, guidance, hyp, ont)
                    cyclic = fcp._has_cycle(services, directed)
                    order = None if cyclic else fcp._reverse_topo_order(services, directed)
                    for op in OPERATORS:
                        for delta in DELTAS:
                            C, rounds, hit = propagate(op, services, H, out, delta, cyclic, order)
                            rows.append(score(services, C, hyp, gt, {
                                **base, "graph": graph, "direction": direction, "weights": weights,
                                "guidance": guidance, "operator": op, "delta": delta,
                                "n_edges": len(edges), "rounds": rounds, "hit_cap": hit}))
    return rows


def cross_check(df: pd.DataFrame) -> None:
    ref = pd.read_csv(RESULTS / "propagation_variants_per_case.csv.gz")
    ref = ref[(ref.threshold == 0.5) & (ref.operator != "local")]
    ref = ref.assign(guidance=ref.guidance.replace({"ontology": "s2r"}))
    keys = ["system", "case_id", "operator", "weights", "guidance", "delta"]
    mine = df[(df.graph == "inferred") & (df.direction == "forward") & df.weights.isin(["raw", "rownorm"])
              & df.guidance.isin(["none", "s2r"])]
    m = mine.merge(ref[keys + ["ac1", "ac1_expected", "n_saturated"]], on=keys, suffixes=("", "_ref"), validate="1:1")
    assert len(m) == len(ref) == len(mine), (len(m), len(ref), len(mine))
    for col in ("ac1", "ac1_expected", "n_saturated"):
        gap = (m[col] - m[col + "_ref"]).abs().max()
        assert gap < 1e-9, f"{col} differs from the committed propagation variants by {gap}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method, ont = fcp.FodaFCPMethod(), OntologyAdapter()
    rows = []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            rows += run_case(tag, case, method, ont)
        print(f"[{tag}] done", flush=True)
    df = pd.DataFrame(rows)
    cross_check(df)
    print("cross-check against the committed propagation variants passed", flush=True)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "direction_variants_per_case.csv.gz", index=False)
    keys = ["graph", "system", "direction", "weights", "guidance", "operator", "delta"]
    summary = (df.groupby(keys, sort=False)
                 .agg(cases=("case_id", "count"), ac1=("ac1", "mean"), ac1_expected=("ac1_expected", "mean"),
                      ac3=("ac3", "mean"), ac5=("ac5", "mean"), mrr=("rr", "mean"),
                      top_block=("top_block", "mean"), n_saturated=("n_saturated", "mean"),
                      max_rounds=("rounds", "max"), hit_cap=("hit_cap", "sum"))
                 .round(6).reset_index())
    summary.to_csv(args.out / "direction_variants_summary.csv", index=False)
    print(f"{len(df)} rows; runs that stopped at the cap of {MAX_ITER} rounds: {int(df.hit_cap.sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
