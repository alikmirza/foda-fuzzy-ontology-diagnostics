"""Analytical saturation brackets for accumulating t-conorms, checked against the data.

Every computed confidence satisfies H(t) <= C(t) <= 1 (the iterates start at H
and never decrease). Substituting the two extremes for the senders' confidences
brackets each service's own confidence before any propagation is run. With
x_lo = delta w(s,t) H(t) and x_hi = delta w(s,t), all with the product t-norm:

  probabilistic sum   (1-H) prod(1 - x_hi)  <=  1 - C  <=  (1-H) prod(1 - x_lo)
  Einstein sum        atanh(H) + sum atanh(x_lo)  <=  atanh(C)
                                                  <=  atanh(H) + sum atanh(x_hi)
                      (the Einstein sum is addition of inverse hyperbolic tangents)
  bounded sum         H + sum x_lo  <=  C before the cap at 1  <=  H + sum x_hi

A service saturates when C >= 1 - eps, eps = 1e-12. The lower bound on C gives
a sufficient condition (it must saturate) and the upper bound a necessary one
(otherwise it cannot). Because max <= probabilistic sum <= Einstein sum <=
bounded sum, a service that must saturate under one also must under the next.
Within a weight budget sum_t w(s,t) <= 1, prod(1 - delta w) >= 1 - delta, so
under the probabilistic sum no service with H(s) < 1 - eps / (1 - delta) can
saturate; with certainty factors of at most 0.95 that is every service, for
every delta < 1.

Checked per (system, operator, delta, case) on the evaluated configuration
(inferred graph, raw weights): sufficient <= observed <= possible as sets of
services; the script aborts otherwise. A numerical margin of 1e-6 on the
atanh scale and 1e-9 on the bounded sum keeps rounding at the threshold from
deciding the comparison.

Outputs
  saturation_bounds_per_case.csv      services guaranteed / observed / allowed to
                                      saturate, with the case's largest out-degree
                                      and weight sum
  saturation_bounds_summary.csv       cases with a saturated tie (>= 2 services):
                                      guaranteed / observed / allowed; and the
                                      per-service counts behind them
  saturation_predictors.csv           how well the necessary bound, the out-degree
                                      and the weight sum rank services (and cases)
                                      by whether they saturate: area under the ROC
                                      curve, plus precision and recall of the
                                      bound as a yes/no rule
  saturation_bounds_per_service.csv.gz  every service at delta = 0.85
  saturation_critical_delta.csv       probabilistic sum: per service, the smallest
                                      grid delta at which saturation is possible
                                      and at which it is certain

Deterministic: no RNG.

Usage:
    PYTHONPATH=. python3 scripts/saturation_bounds.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from scripts.run_propagation_variants import prepare, propagate

SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
DELTAS = (0.001, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.75, 0.85, 0.95, 1.0)
OPERATORS = ("probsum", "einstein", "bounded")
EPS = 1e-12
ATANH_SAT = math.atanh(1.0 - EPS)


def _atanh(x: float) -> float:
    return math.inf if x >= 1.0 else math.atanh(x)


def bracket(op, H, out, delta):
    """Per service: (must saturate, can saturate, score of the necessary bound)."""
    must, can, score = set(), set(), {}
    for s, h in H.items():
        lo_terms = [delta * w * H[t] for t, w in out.get(s, [])]
        hi_terms = [delta * w for _, w in out.get(s, [])]
        if op == "probsum":
            lower = (1.0 - h) * math.prod(1.0 - x for x in hi_terms)     # lower bound on 1 - C
            upper = (1.0 - h) * math.prod(1.0 - x for x in lo_terms)
            if upper <= EPS:
                must.add(s)
            if lower <= EPS:
                can.add(s)
            score[s] = -math.log10(lower) if lower > 0 else 400.0
        elif op == "einstein":
            a_lo = _atanh(h) + sum(_atanh(x) for x in lo_terms)
            a_hi = _atanh(h) + sum(_atanh(x) for x in hi_terms)
            if a_lo >= ATANH_SAT + 1e-6:
                must.add(s)
            if a_hi >= ATANH_SAT - 1e-6:
                can.add(s)
            score[s] = min(a_hi, 400.0)
        else:                                                           # bounded
            if h + sum(lo_terms) >= 1.0 - EPS + 1e-9:
                must.add(s)
            if h + sum(hi_terms) >= 1.0 - EPS - 1e-9:
                can.add(s)
            score[s] = h + sum(hi_terms)
    return must, can, score


def auc(scores, labels) -> float:
    labels = np.asarray(labels, dtype=bool)
    n_pos, n_neg = int(labels.sum()), int((~labels).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = rankdata(scores)
    return float((ranks[labels].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method = fcp.FodaFCPMethod()
    case_rows, svc_rows, crit = [], [], []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            norm, onset, _fuzzy, hyp = prepare(case, method)
            services = norm.services
            edges = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                        onset_time=onset, threshold=method.topology_threshold, lag=method.lag)
            out = defaultdict(list)
            for (u, v), w in edges.items():
                out[u].append((v, w))
            gated = {s: [(t, w, 1.0) for t, w in lst] for s, lst in out.items()}
            H = {s: hyp[s].local_confidence for s in services}
            degree = {s: len(out.get(s, [])) for s in services}
            row_sum = {s: sum(w for _, w in out.get(s, [])) for s in services}
            cyclic = fcp._has_cycle(services, edges)
            order = None if cyclic else fcp._reverse_topo_order(services, edges)
            first_can, first_must = {}, {}
            for op in OPERATORS:
                for delta in DELTAS:
                    C = propagate(op, services, H, gated, delta, cyclic, order)
                    must, can, score = bracket(op, H, out, delta)
                    obs = {s for s in services if C[s] >= 1.0 - EPS}
                    assert must <= obs <= can, f"{case.id} {op} delta={delta}: bracket violated"
                    if op == "probsum":
                        for s in can:
                            first_can.setdefault(s, delta)
                        for s in must:
                            first_must.setdefault(s, delta)
                    case_rows.append({"system": tag, "operator": op, "delta": delta, "case_id": case.id,
                                      "n_sufficient": len(must), "n_observed": len(obs), "n_possible": len(can),
                                      "max_out_degree": max(degree.values()), "max_row_sum": max(row_sum.values())})
                    for s in services:
                        svc_rows.append((tag, op, delta, case.id, s, H[s], degree[s], row_sum[s], score[s],
                                         s in must, s in can, s in obs))
            for s in first_can:
                crit.append({"system": tag, "case_id": case.id, "service": s, "H": round(H[s], 6),
                             "out_degree": degree[s], "row_sum": round(row_sum[s], 6),
                             "delta_nec": first_can[s], "delta_suf": first_must.get(s, math.nan)})
        print(f"[{tag}] done; every bracket holds", flush=True)

    cases = pd.DataFrame(case_rows)
    svc = pd.DataFrame(svc_rows, columns=["system", "operator", "delta", "case_id", "service", "H", "out_degree",
                                          "row_sum", "bound_score", "must", "can", "observed"])
    args.out.mkdir(parents=True, exist_ok=True)
    cases.to_csv(args.out / "saturation_bounds_per_case.csv", index=False)
    pd.DataFrame(crit).to_csv(args.out / "saturation_critical_delta.csv", index=False)
    svc[svc.delta == 0.85].round(6).to_csv(args.out / "saturation_bounds_per_service.csv.gz", index=False)

    summ = (cases.assign(tie_guaranteed=cases.n_sufficient >= 2, tie_observed=cases.n_observed >= 2,
                         tie_possible=cases.n_possible >= 2)
                 .groupby(["system", "operator", "delta"], sort=False)
                 .agg(tie_guaranteed=("tie_guaranteed", "sum"), tie_observed=("tie_observed", "sum"),
                      tie_possible=("tie_possible", "sum"), services_guaranteed=("n_sufficient", "sum"),
                      services_observed=("n_observed", "sum"), services_possible=("n_possible", "sum"))
                 .astype(int).reset_index())
    summ.to_csv(args.out / "saturation_bounds_summary.csv", index=False)

    preds = []
    for (system, op, delta), g in svc.groupby(["system", "operator", "delta"], sort=False):
        c = cases[(cases.system == system) & (cases.operator == op) & (cases.delta == delta)]
        tie = c.n_observed >= 2
        tp = int((g.can & g.observed).sum())
        preds.append({
            "system": system, "operator": op, "delta": delta,
            "services": len(g), "services_saturated": int(g.observed.sum()),
            "auc_bound": auc(g.bound_score, g.observed), "auc_out_degree": auc(g.out_degree, g.observed),
            "auc_row_sum": auc(g.row_sum, g.observed),
            "bound_precision": tp / int(g.can.sum()) if g.can.any() else float("nan"),
            "bound_recall": tp / int(g.observed.sum()) if g.observed.any() else float("nan"),
            "cases": len(c), "cases_tied": int(tie.sum()),
            "case_auc_bound": auc(c.n_possible, tie), "case_auc_out_degree": auc(c.max_out_degree, tie),
            "case_auc_row_sum": auc(c.max_row_sum, tie),
        })
    preds = pd.DataFrame(preds).round(4)
    preds.to_csv(args.out / "saturation_predictors.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(summ[(summ.system == "re1-tt")].to_string(index=False)); print()
        print(preds[(preds.delta == 0.85)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
