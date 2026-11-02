"""Propagation variants for FODA-FCP: aggregation operator, weights, guidance, density.

Studies how the choice of fuzzy aggregation in the propagation step, the
normalisation of edge weights, ontology guidance and graph density change
ranking accuracy and explanation quality, across the full damping grid. The
shipped method is one point of this space and is reproduced exactly.

Propagation, written with a t-conorm S and a t-norm T:

    x(s,t) = T( delta * w(s,t) * g(s,t),  C(t) )     transmitted evidence
    P(s)   = S over callees t of x(s,t)
    C(s)   = S( H(s), P(s) )

on an acyclic graph in one reverse-topological pass, otherwise by Jacobi
iteration from C = H until the sup-norm residual falls below 1e-6 or 100
rounds, exactly as the shipped port routes it.

Axes:
  operator   probsum  S = probabilistic sum, T = product (the shipped Noisy-OR)
             max      S = maximum, T = product (sup-product composition)
             supmin   S = maximum, T = minimum (sup-min composition)
             bounded  S = bounded sum min(1, a + b), T = product
             einstein S = Einstein sum (a + b) / (1 + ab), T = product
             local    no propagation at all: C = H (recorded once, delta = 0).
                      delta = 0.001 is not the same thing: the residual
                      propagation still breaks ties between equal H values.
  weights    raw      w(s,t) = |lagged corr| as inferred (shipped)
             rownorm  w(s,t) / sum_u w(s,u): the weights out of each service
                      sum to 1, the budget Theorem 1 assumes
  guidance   none     g = 1 (shipped)
             ontology g = DiagnosticKB propagation strength of
                      type(t) -> type(s), types from the fired rules; 1.0
                      when both types are equal (an assumption: the table
                      has no same-type pairs); 0 when either service has no
                      rule-derived type
  threshold  correlation threshold for admitting an edge; 0.5 is shipped. The
             threshold sweep runs the shipped operator, raw weights and no
             guidance only, and varies graph density on the same data.
  delta      0.001, 0.1, ..., 1.0 as in the delta sweep.

Per case: AC@1 (pessimistic ties), expected AC@1 (1 / size of the top tie block
when the ground truth is in it: AC@1 under random tie-breaking), refined AC@1
over (C, H) ties, AC@3, AC@5,
MRR, the size of the top tie block, the number of services with
C >= 1 - 1e-12, and SG / SC / EC on the emitted explanation.

Cross-check, fatal on mismatch: at threshold 0.5 the shipped configuration
must equal results/delta_sweep_per_case_<system>.csv case by case at every
delta (AC@1, refined AC@1, SG, SC, EC).

Deterministic: no RNG. Re-running reproduces byte-identical output for a given
commit.

Usage:
    PYTHONPATH=. python3 scripts/run_propagation_variants.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from functools import reduce
from pathlib import Path

import pandas as pd

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.metrics import (
    SemanticGroundedness, SemanticCoherence, ExplanationCompleteness,
    OntologyAdapter, accuracy_at_k, mean_reciprocal_rank,
)

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
DELTAS = (0.001, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.75, 0.85, 0.95, 1.0)
OPERATORS = ("probsum", "max", "supmin", "bounded", "einstein")
WEIGHTS = ("raw", "rownorm")
GUIDANCE = ("none", "ontology")
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
SHIPPED_THRESHOLD = 0.5
EPSILON, MAX_ITER, SATURATION_TOL = 1e-6, 100, 1e-12

S = {
    "max": max,
    "supmin": max,
    "bounded": lambda a, b: min(1.0, a + b),
    "einstein": lambda a, b: (a + b) / (1.0 + a * b),
}


def update(op: str, h: float, xs: list[float]) -> float:
    """C(s) from local evidence h and transmitted terms xs."""
    if op == "local":
        return h
    if op == "probsum":                      # identical arithmetic to the shipped port
        comp = 1.0
        for x in xs:
            comp *= 1.0 - x
        p = 1.0 - comp
        return max(0.0, min(1.0, 1.0 - (1.0 - h) * (1.0 - p)))
    p = reduce(S[op], xs, 0.0)
    return max(0.0, min(1.0, S[op](h, p)))


def transmit(op: str, w: float, delta: float, g: float, ct: float) -> float:
    if op == "supmin":
        return min(delta * w * g, ct)
    x = ct * w * delta                       # the shipped port's multiplication order
    return x if g == 1.0 else x * g


def propagate(op, services, H, out, delta, cyclic, order):
    """out[s] = [(t, w, g)]: callee, (possibly normalised) weight, ontology gate."""
    C = dict(H)
    if not cyclic:
        for s in order:
            if out.get(s):
                C[s] = update(op, C[s], [transmit(op, w, delta, g, C.get(t, 0.0)) for t, w, g in out[s]])
        return C
    for _ in range(MAX_ITER):
        nxt = {s: update(op, H[s], [transmit(op, w, delta, g, C.get(t, 0.0)) for t, w, g in out.get(s, [])])
               for s in services}
        residual = max(abs(nxt[s] - C[s]) for s in services)
        C = nxt
        if residual < EPSILON:
            break
    return C


def refined_hit(services, C, H, gt) -> float:
    keyed = sorted(((s, (round(C.get(s, 0.0), 12), round(H.get(s, 0.0), 12))) for s in services),
                   key=lambda kv: (-kv[1][0], -kv[1][1]))
    block = [s for s, k in keyed if k == keyed[0][1]]
    return 1.0 if block == [gt] else 0.0


def prepare(case, method):
    norm = normalize_case(case, window_seconds=method.window_seconds)
    onset = detect_onset(norm.case_window, norm.services)
    fuzzy = {s: fcp._fuzzify_service(norm.case_window, s, onset) for s in norm.services}
    hyp = {s: fcp._infer_hypothesis(v) for s, v in fuzzy.items()}
    return norm, onset, fuzzy, hyp


def edge_coefs(edges, weights, guidance, hyp, ont):
    raw_out = defaultdict(list)
    for (u, v), w in edges.items():
        raw_out[u].append((v, w))
    out = {}
    for s, lst in raw_out.items():
        total = sum(w for _, w in lst)
        row = []
        for t, w in lst:
            if weights == "rownorm":
                w = w / total
            g = 1.0
            if guidance == "ontology":
                ps = fcp.CATEGORY_TO_FAULT.get(hyp[s].dominant_category)
                pt = fcp.CATEGORY_TO_FAULT.get(hyp[t].dominant_category)
                if ps is None or pt is None:
                    g = 0.0
                elif ps == pt:
                    g = 1.0
                else:
                    g = ont.get_propagation_strength(fcp._ontology_uri(pt), fcp._ontology_uri(ps))
            row.append((t, w, g))
        out[s] = row
    return out


def run_system(sysdir, tag, data, method, ont, metrics, configs_main, configs_thr):
    sg, sc, ec = metrics
    cases = [(c, *prepare(c, method)) for c in RCAEvalLoader(data / sysdir).iter_cases()]
    rows = []
    for thr in THRESHOLDS:
        configs = configs_main if thr == SHIPPED_THRESHOLD else configs_thr
        for case, norm, onset, fuzzy, hyp in cases:
            services, gt = norm.services, case.ground_truth_root_cause
            edges = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                        onset_time=onset, threshold=thr, lag=method.lag)
            cyclic = fcp._has_cycle(services, edges)
            order = None if cyclic else fcp._reverse_topo_order(services, edges)
            H = {s: hyp[s].local_confidence for s in services}
            for op, weights, guidance, delta in configs:
                out = edge_coefs(edges, weights, guidance, hyp, ont)
                C = propagate(op, services, H, out, delta, cyclic, order)
                ranked = fcp._rank(C, hyp, services)
                expl = fcp._build_explanation(services_ranked=ranked, hypotheses=hyp, fuzzy_vectors=fuzzy,
                                              edges=edges, delta=delta, top_k=method.top_k)
                top = ranked[0][1]
                block = [s for s, c in ranked if c == top]
                rows.append({
                    "system": tag, "threshold": thr, "operator": op, "weights": weights,
                    "guidance": guidance, "delta": delta, "case_id": case.id,
                    "fault": case.ground_truth_fault_type, "n_edges": len(edges),
                    "ac1": 1.0 if accuracy_at_k(ranked, gt, 1) else 0.0,
                    "ac1_expected": 1.0 / len(block) if gt in block else 0.0,
                    "ac1_refined": refined_hit(services, C, H, gt),
                    "ac3": 1.0 if accuracy_at_k(ranked, gt, 3) else 0.0,
                    "ac5": 1.0 if accuracy_at_k(ranked, gt, 5) else 0.0,
                    "mrr": mean_reciprocal_rank(ranked, gt),
                    "top_block": len(block),
                    "n_saturated": sum(1 for s in services if C[s] >= 1.0 - SATURATION_TOL),
                    "sg": sg.score(expl, ont), "sc": sc.score(expl, ont),
                    "ec": ec.score(expl, ont, case_services=services),
                })
        print(f"[{tag}] threshold {thr} done", flush=True)
    return pd.DataFrame(rows)


def cross_check(df: pd.DataFrame, tag: str) -> None:
    sweep = pd.read_csv(RESULTS / f"delta_sweep_per_case_{tag}.csv").set_index(["delta", "case_id"])
    ship = df[(df.threshold == SHIPPED_THRESHOLD) & (df.operator == "probsum") & (df.weights == "raw")
              & (df.guidance == "none")].set_index(["delta", "case_id"])
    for mine, theirs in (("ac1", "ac1_shipped"), ("ac1_refined", "ac1_refined"),
                         ("sg", "sg"), ("sc", "sc"), ("ec", "ec")):
        gap = (ship[mine] - sweep[theirs].reindex(ship.index)).abs().max()
        assert gap < 1e-9, f"{tag}: {mine} differs from the committed delta sweep by {gap}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RCAEval RE1 data root")
    ap.add_argument("--out", type=Path, default=Path("results"))
    ap.add_argument("--systems", nargs="*", default=[t for _, t in SYSTEMS])
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    method, ont = fcp.FodaFCPMethod(), OntologyAdapter()
    metrics = (SemanticGroundedness(), SemanticCoherence(), ExplanationCompleteness())
    configs_main = ([("local", "raw", "none", 0.0)] +
                    [(o, w, g, d) for o in OPERATORS for w in WEIGHTS for g in GUIDANCE for d in DELTAS])
    configs_thr = [("probsum", "raw", "none", d) for d in DELTAS]

    frames = []
    for sysdir, tag in SYSTEMS:
        if tag not in args.systems:
            continue
        df = run_system(sysdir, tag, args.data.expanduser(), method, ont, metrics, configs_main, configs_thr)
        cross_check(df, tag)
        print(f"[{tag}] cross-check against the delta sweep passed", flush=True)
        frames.append(df)

    per_case = pd.concat(frames, ignore_index=True)
    per_case.to_csv(args.out / "propagation_variants_per_case.csv.gz", index=False)
    keys = ["system", "threshold", "operator", "weights", "guidance", "delta"]
    summary = (per_case.groupby(keys, sort=False)
               [["n_edges", "ac1", "ac1_expected", "ac1_refined", "ac3", "ac5", "mrr", "top_block", "n_saturated", "sg", "sc", "ec"]]
               .mean().round(6).reset_index())
    summary.to_csv(args.out / "propagation_variants_summary.csv", index=False)
    print(summary[(summary.threshold == SHIPPED_THRESHOLD) & (summary.delta.isin([0.001, 0.85]))]
          .to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
