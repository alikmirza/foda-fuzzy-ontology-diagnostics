"""Faithfulness of FODA-FCP explanations: do they name what put the top service first?

For the probabilistic-sum (Noisy-OR) update the top service's confidence
decomposes exactly in log-complement space,

    -ln(1 - C(s1)) = -ln(1 - H(s1)) + sum_t -ln(1 - x(s1,t)),   x = delta * w * C(t),

into its own rule-base evidence H(s1), which the explanation cites through the
fired rules, and one term per callee t, which the explanation can only cite by
naming t as a contributing service. Per case and configuration this script
records:

  own_share       share of the top service's support from its own rules
  named_share     share from its own rules plus the callees the explanation
                  names (the other services of the reported head)
  driver_named    the single largest component (own rules, or one callee) is
                  cited by the explanation
  link_precision  share of the explanation's contributes_to links (head
                  service -> top service) that correspond to a propagation
                  edge, i.e. the named service actually transmitted evidence
                  into the top service

Cases where the top service has no support at all (C = 0: no rule fired
anywhere) are counted separately and excluded from the shares.
Configurations: shipped (Noisy-OR, raw weights, delta = 0.85), Noisy-OR with
row-normalised weights at delta = 0.85, Noisy-OR at delta = 0.001, and local
evidence only (C = H, for which own_share = 1 by definition).

Propagation reuses scripts/run_propagation_variants.py, whose shipped
configuration is asserted equal to the committed delta sweep. Deterministic.

Usage:
    PYTHONPATH=. python3 scripts/explanation_faithfulness.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.metrics import OntologyAdapter
from scripts.run_propagation_variants import edge_coefs, prepare, propagate

SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
CONFIGS = (("shipped", "probsum", "raw", 0.85), ("rownorm", "probsum", "rownorm", 0.85),
           ("delta0.001", "probsum", "raw", 0.001), ("local", "local", "raw", 0.0))


def nlog(x: float) -> float:
    """-ln(1 - x), finite for x < 1."""
    return math.inf if x >= 1.0 else -math.log1p(-x)


def case_rows(tag, case, method, ont):
    norm, onset, fuzzy, hyp = prepare(case, method)
    services = norm.services
    edges = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                onset_time=onset, threshold=method.topology_threshold, lag=method.lag)
    cyclic = fcp._has_cycle(services, edges)
    order = None if cyclic else fcp._reverse_topo_order(services, edges)
    H = {s: hyp[s].local_confidence for s in services}
    rows = []
    for name, op, weights, delta in CONFIGS:
        out = edge_coefs(edges, weights, "none", hyp, ont)
        C = propagate(op, services, H, out, delta, cyclic, order)
        ranked = fcp._rank(C, hyp, services)
        head = [s for s, _ in ranked[: method.top_k]]
        top, named = head[0], set(head[1:])
        row = {"system": tag, "config": name, "case_id": case.id,
               "top_is_gt": top == case.ground_truth_root_cause, "no_support": C[top] == 0.0}
        own = nlog(H[top])
        callee_terms = {} if op == "local" else {t: nlog(C.get(t, 0.0) * w * delta) for t, w, _ in out.get(top, [])}
        links = [t for t in head[1:]]
        row["link_precision"] = (sum(1 for t in links if (top, t) in edges) / len(links)) if links else math.nan
        total = own + sum(callee_terms.values())
        if C[top] == 0.0 or total == 0.0:
            row.update(own_share=math.nan, named_share=math.nan, driver_named=math.nan)
        elif math.isinf(total):
            inf_own = math.isinf(own)
            inf_named = any(math.isinf(v) for t, v in callee_terms.items() if t in named)
            row.update(own_share=1.0 if inf_own else 0.0, named_share=1.0 if (inf_own or inf_named) else 0.0,
                       driver_named=float(inf_own or inf_named))
        else:
            named_mass = own + sum(v for t, v in callee_terms.items() if t in named)
            driver = max([("own", own)] + list(callee_terms.items()), key=lambda kv: kv[1])[0]
            row.update(own_share=own / total, named_share=named_mass / total,
                       driver_named=float(driver == "own" or driver in named))
        rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method, ont = fcp.FodaFCPMethod(), OntologyAdapter()
    rows = []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            rows += case_rows(tag, case, method, ont)
        print(f"[{tag}] done", flush=True)
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "explanation_faithfulness_per_case.csv", index=False)
    summ = (df.groupby(["system", "config"], sort=False)
              .agg(cases=("case_id", "count"), no_support=("no_support", "sum"),
                   own_share=("own_share", "mean"), named_share=("named_share", "mean"),
                   driver_named=("driver_named", "mean"), link_precision=("link_precision", "mean"))
              .round(4).reset_index())
    summ.to_csv(args.out / "explanation_faithfulness_summary.csv", index=False)
    print(summ.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
