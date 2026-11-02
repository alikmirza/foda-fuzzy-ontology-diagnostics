"""Analytical saturation bracket for damped Noisy-OR propagation, checked against the data.

For the shipped update C(s) = 1 - (1 - H(s)) * prod_t (1 - delta w(s,t) C(t)),
every computed confidence satisfies H(t) <= C(t) <= 1 (the iterates start at H
and never decrease). Substituting the two extremes gives, for every service s,

    L(s) = (1 - H(s)) * prod_t (1 - delta w(s,t))         <= 1 - C(s)
    U(s) = (1 - H(s)) * prod_t (1 - delta w(s,t) H(t))     >= 1 - C(s)

so with the saturation tolerance eps = 1e-12 used throughout:

    U(s) <= eps   =>  s saturates          (sufficient; needs no propagation)
    L(s) >  eps   =>  s cannot saturate    (necessary condition violated)

Both bounds depend only on the inferred graph, the local evidence H and delta,
so they predict saturation before propagation is run. Within a weight budget
sum_t w(s,t) <= 1, prod_t (1 - delta w) >= 1 - delta, so L(s) >= (1 - H(s))(1 - delta)
and no service with H(s) < 1 - eps / (1 - delta) can saturate.

Per (system, delta, case) the script records the number of services that the
bracket guarantees to saturate (n_sufficient), that it allows to saturate
(n_possible), and that actually saturate after propagation (n_observed); it
asserts n_sufficient <= n_observed <= n_possible for every case. A tie of
saturated services is guaranteed when n_sufficient >= 2 and possible only when
n_possible >= 2. Per service it also records the critical damping interval
[delta_nec, delta_suf]: below delta_nec saturation is impossible, at or above
delta_suf it is certain (grid search over the delta sweep values).

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

import pandas as pd

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset

SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
DELTAS = (0.001, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.75, 0.85, 0.95, 1.0)
EPS = 1e-12


def bounds(H, out, delta):
    L, U = {}, {}
    for s, h in H.items():
        lo = hi = 1.0 - h
        for t, w in out.get(s, []):
            lo *= 1.0 - delta * w
            hi *= 1.0 - delta * w * H[t]
        L[s], U[s] = lo, hi
    return L, U


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    method = fcp.FodaFCPMethod()
    rows, crit = [], []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            norm = normalize_case(case, window_seconds=method.window_seconds)
            services = norm.services
            onset = detect_onset(norm.case_window, services)
            hyp = {s: fcp._infer_hypothesis(fcp._fuzzify_service(norm.case_window, s, onset)) for s in services}
            edges = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                        onset_time=onset, threshold=method.topology_threshold, lag=method.lag)
            out = defaultdict(list)
            for (u, v), w in edges.items():
                out[u].append((v, w))
            H = {s: hyp[s].local_confidence for s in services}
            cyclic = fcp._has_cycle(services, edges)
            first_nec, first_suf = {}, {}
            for delta in DELTAS:
                C = (fcp._propagate_iterative(hypotheses=hyp, services=services, edges=edges, delta=delta,
                                              max_iter=method.max_iterations) if cyclic else
                     fcp._propagate_damped(hypotheses=hyp, services=services, edges=edges, delta=delta))
                L, U = bounds(H, out, delta)
                obs = {s for s in services if C[s] >= 1.0 - EPS}
                suf = {s for s in services if U[s] <= EPS}
                pos = {s for s in services if L[s] <= EPS}
                assert suf <= obs <= pos, f"{case.id} delta={delta}: bracket violated"
                for s in pos:
                    first_nec.setdefault(s, delta)
                for s in suf:
                    first_suf.setdefault(s, delta)
                rows.append({"system": tag, "delta": delta, "case_id": case.id,
                             "n_sufficient": len(suf), "n_observed": len(obs), "n_possible": len(pos)})
            for s in first_nec:
                crit.append({"system": tag, "case_id": case.id, "service": s, "H": round(H[s], 6),
                             "out_degree": len(out.get(s, [])),
                             "row_sum": round(sum(w for _, w in out.get(s, [])), 6),
                             "delta_nec": first_nec[s], "delta_suf": first_suf.get(s, math.nan)})
        print(f"[{tag}] done; bracket holds on every case and delta", flush=True)

    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "saturation_bounds_per_case.csv", index=False)
    pd.DataFrame(crit).to_csv(args.out / "saturation_critical_delta.csv", index=False)
    summ = (df.assign(tie_guaranteed=df.n_sufficient >= 2, tie_observed=df.n_observed >= 2,
                      tie_possible=df.n_possible >= 2)
              .groupby(["system", "delta"])[["tie_guaranteed", "tie_observed", "tie_possible"]].sum()
              .astype(int).reset_index())
    summ.to_csv(args.out / "saturation_bounds_summary.csv", index=False)
    print(summ.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
