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

Guidance is run for the probabilistic sum only.

Operators. The five of scripts/run_propagation_variants.py (probsum, max, supmin,
bounded, einstein; the accumulating ones use the product t-norm), plus:
  bounded_dual   bounded sum with its dual, the Lukasiewicz t-norm
                 T(a, b) = max(0, a + b - 1)
  einstein_dual  Einstein sum with the Einstein product ab / (1 + (1-a)(1-b))
                 (the probabilistic sum is already paired with its dual, the product)
  mean           an averaging operator: P(s) is the weighted arithmetic mean of
                 the damped sender confidences, sum_t w delta C(t) / sum_t w, and
                 C(s) = 1 - (1 - H(s))(1 - P(s)). Max and the mean are the two
                 ends of the ordered weighted averaging family.
  uninorm        the representable uninorm with neutral element 0.5,
                 U(a, b) = ab / (ab + (1-a)(1-b)) (products of odds, i.e. a
                 logarithmic opinion pool): each sender transmits
                 x = 0.5 + delta w (C(t) - 0.5), neutral when it carries no
                 information, and C(s) = U(H(s), x_1, ..., x_n); a service with
                 H(s) = 0 stays at 0. Unlike a t-conorm it can lower C below H.
The damping grid is that of scripts/run_propagation_variants.py. Local evidence
alone (C = H) is recorded once per case as operator "local".

Per case: n_above (services scoring strictly above the ground truth) and gt_block
(services tied with it, itself included), from which every tie convention
follows: pessimistic rank = n_above + gt_block, expected AC@k under random
tie-breaking = clip((k - n_above) / gt_block, 0, 1). Also AC@1, expected AC@1,
AC@3, AC@5, reciprocal rank (pessimistic), top tie block size, saturated
services, Jacobi rounds and whether the cap of 100 was reached. Ties are exact
floating-point equality, as in evaluation.metrics.ranking_metrics.

For the tie-ordering test: local_block is the size of the top tie block of H
when the ground truth is in it (0 otherwise), and p_first_in_local_block is the
probability that the ground truth comes first among that block's members when
they are ordered by C with random tie-breaking; chance is 1 / local_block.

For explanations: the fault prototype of the top-ranked service (top1_type) and
whether it comes from the fuzzy-term fallback (top1_fallback); any_fired and
gt_fired say whether some rule fired anywhere and at the ground truth. SG, SC
and EC are scored for the configurations listed in REPORTED only.

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
import math

from evaluation.metrics import (
    ExplanationCompleteness, OntologyAdapter, SemanticCoherence, SemanticGroundedness,
)
from scripts.run_propagation_variants import (
    DELTAS, EPSILON, MAX_ITER, SATURATION_TOL, prepare,
    transmit as _transmit_base, update as _update_base,
)
from scripts.run_propagation_variants import OPERATORS as BASE_OPERATORS

OPERATORS = BASE_OPERATORS + ("bounded_dual", "einstein_dual", "mean", "uninorm")
#: (graph, direction, weights, guidance, operator, delta) scored for SG / SC / EC.
REPORTED = {
    ("inferred", "forward", "raw", "none", "probsum", 0.85),
    ("inferred", "forward", "rownorm", "none", "probsum", 0.85),
    ("inferred", "forward", "capped", "none", "probsum", 0.85),
    ("inferred", "forward", "rownorm", "none", "max", 0.85),
    ("callgraph", "forward", "unit", "none", "probsum", 0.85),
    ("callgraph", "reversed", "unit", "none", "probsum", 0.3),
}
_CLIP = 1e-15


def _logit(x: float) -> float:
    x = min(1.0 - _CLIP, max(_CLIP, x))
    return math.log(x / (1.0 - x))


def receive(op: str, h: float, senders, C, delta: float) -> float:
    """C(s) from own evidence h and senders [(t, w, g)] under operator op."""
    if op in BASE_OPERATORS:
        return _update_base(op, h, [_transmit_base(op, w, delta, g, C.get(t, 0.0)) for t, w, g in senders])
    if op == "mean":
        total = sum(w for _, w, _ in senders)
        p = sum(w * delta * g * C.get(t, 0.0) for t, w, g in senders) / total if total > 0 else 0.0
        return max(0.0, min(1.0, 1.0 - (1.0 - h) * (1.0 - p)))
    if op == "uninorm":
        if h <= 0.0:
            return 0.0
        z = _logit(h) + sum(_logit(0.5 + delta * w * g * (C.get(t, 0.0) - 0.5)) for t, w, g in senders)
        return 1.0 / (1.0 + math.exp(-z)) if z > -700 else 0.0
    if op == "bounded_dual":
        p = min(1.0, sum(max(0.0, delta * w * g + C.get(t, 0.0) - 1.0) for t, w, g in senders))
        return min(1.0, h + p)
    if op == "einstein_dual":
        c = h
        for t, w, g in senders:
            a, b = delta * w * g, C.get(t, 0.0)
            x = a * b / (1.0 + (1.0 - a) * (1.0 - b))
            c = (c + x) / (1.0 + c * x)
        return max(0.0, min(1.0, c))
    raise ValueError(op)

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
                C[s] = receive(op, C[s], out[s], C, delta)
        return C, 0, False
    for k in range(1, MAX_ITER + 1):
        nxt = {s: receive(op, H[s], out.get(s, []), C, delta) for s in services}
        residual = max(abs(nxt[s] - C[s]) for s in services)
        C = nxt
        if residual < EPSILON:
            return C, k, False
    return C, MAX_ITER, True


def score(services, C, hyp, fuzzy, gt, local_top, extra):
    ranked = fcp._rank(C, hyp, services)
    scores = [c for _, c in ranked]
    gt_score = C[gt]
    n_above = sum(1 for c in scores if c > gt_score)
    gt_block = sum(1 for c in scores if c == gt_score)
    rank = n_above + gt_block                                            # pessimistic
    block = sum(1 for c in scores if c == scores[0])
    if gt in local_top and len(local_top) > 1:
        best = max(C[s] for s in local_top)
        p_first = 1.0 / sum(1 for s in local_top if C[s] == best) if C[gt] == best else 0.0
        local_block = len(local_top)
    else:
        p_first, local_block = float("nan"), 0
    top = ranked[0][0]
    proto = fcp.CATEGORY_TO_FAULT.get(hyp[top].dominant_category)
    fallback = False
    if proto is None:
        proto = fcp._infer_fault_prototype_from_fuzzy(fuzzy[top])
        fallback = proto is not None
    row = {"n_above": n_above, "gt_block": gt_block, "rank": rank, "ac1": float(rank == 1),
           "ac1_expected": 1.0 / block if gt_score == scores[0] else 0.0,
           "ac3": float(rank <= 3), "ac5": float(rank <= 5), "rr": 1.0 / rank, "top_block": block,
           "n_saturated": sum(1 for c in scores if c >= 1.0 - SATURATION_TOL),
           "local_block": local_block, "p_first_in_local_block": p_first,
           "top1": top, "top1_type": proto or "none", "top1_fallback": fallback}
    row.update(extra)
    return row, ranked


def explanation_scores(ranked, hyp, fuzzy, edges, delta, method, ont, metrics, services):
    sg, sc, ec = metrics
    expl = fcp._build_explanation(services_ranked=ranked, hypotheses=hyp, fuzzy_vectors=fuzzy,
                                  edges=edges, delta=delta, top_k=method.top_k)
    return {"sg": sg.score(expl, ont), "sc": sc.score(expl, ont),
            "ec": ec.score(expl, ont, case_services=services)}


def run_case(tag, case, method, ont, metrics):
    norm, onset, fuzzy, hyp = prepare(case, method)
    services, gt = norm.services, case.ground_truth_root_cause
    H = {s: hyp[s].local_confidence for s in services}
    h_max = max(H.values())
    local_top = {s for s in services if H[s] == h_max}
    base = {"system": tag, "case_id": case.id, "fault": case.ground_truth_fault_type, "root": gt,
            "any_fired": h_max > 0.0, "gt_fired": H[gt] > 0.0, "gt_H": H[gt]}
    inferred = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                   onset_time=onset, threshold=method.topology_threshold, lag=method.lag)
    row, ranked = score(services, H, hyp, fuzzy, gt, local_top,
                        {**base, "graph": "none", "direction": "none", "weights": "none", "guidance": "none",
                         "operator": "local", "delta": 0.0, "n_edges": 0, "rounds": 0, "hit_cap": False})
    row.update(explanation_scores(ranked, hyp, fuzzy, inferred, 0.0, method, ont, metrics, services))
    rows = [row]
    graphs = [("inferred", inferred, ("raw", "rownorm", "capped"))]
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
                    for op in (OPERATORS if guidance == "none" else ("probsum",)):
                        for delta in DELTAS:
                            C, rounds, hit = propagate(op, services, H, out, delta, cyclic, order)
                            row, ranked = score(services, C, hyp, fuzzy, gt, local_top, {
                                **base, "graph": graph, "direction": direction, "weights": weights,
                                "guidance": guidance, "operator": op, "delta": delta,
                                "n_edges": len(edges), "rounds": rounds, "hit_cap": hit})
                            if (graph, direction, weights, guidance, op, delta) in REPORTED:
                                row.update(explanation_scores(ranked, hyp, fuzzy, directed, delta, method, ont,
                                                              metrics, services))
                            rows.append(row)
    return rows


def cross_check(df: pd.DataFrame) -> None:
    ref = pd.read_csv(RESULTS / "propagation_variants_per_case.csv.gz")
    ref = ref[(ref.threshold == 0.5) & (ref.operator != "local")]
    ref = ref.assign(guidance=ref.guidance.replace({"ontology": "s2r"}))
    ref = ref[(ref.guidance == "none") | (ref.operator == "probsum")]
    keys = ["system", "case_id", "operator", "weights", "guidance", "delta"]
    mine = df[(df.graph == "inferred") & (df.direction == "forward") & df.weights.isin(["raw", "rownorm"])
              & df.guidance.isin(["none", "s2r"]) & df.operator.isin(BASE_OPERATORS)]
    cols = ["ac1", "ac1_expected", "ac3", "ac5", "n_saturated", "sg", "sc", "ec"]
    m = mine.merge(ref[keys + cols], on=keys, suffixes=("", "_ref"), validate="1:1")
    assert len(m) == len(ref) == len(mine), (len(m), len(ref), len(mine))
    for col in ("ac1", "ac1_expected", "ac3", "ac5", "n_saturated"):
        gap = (m[col] - m[col + "_ref"]).abs().max()
        assert gap < 1e-9, f"{col} differs from the committed propagation variants by {gap}"
    scored = m[m["sg"].notna()]
    assert len(scored) == 3 * 375, len(scored)            # probsum raw and rownorm, max rownorm, at delta = 0.85
    for col in ("sg", "sc", "ec"):
        gap = (scored[col] - scored[col + "_ref"]).abs().max()
        assert gap < 1e-9, f"{col} differs from the committed propagation variants by {gap}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method, ont = fcp.FodaFCPMethod(), OntologyAdapter()
    metrics = (SemanticGroundedness(), SemanticCoherence(), ExplanationCompleteness())
    rows = []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            rows += run_case(tag, case, method, ont, metrics)
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
