"""Numerical check of the KES paper's Propositions 1-3 and corollary on the benchmark cases.

For every RE1 case, on its inferred graph (forward direction, the evaluated
one) with raw, normalised and capped weights and at every damping level of the
grid, the propagation update is iterated synchronously from C = H (at most 100
rounds, tolerance 1e-6, as in the experiments) and these statements are tested:

  P1a  monotone      each iterate is >= the previous one, for the five t-conorm
                     compositions, the two dual pairings and the weighted mean
  P1b  contraction   probabilistic sum, weight sums <= 1 (normalised or capped)
                     and delta < 1: the change of each round is at most delta
                     times the change of the round before
  P1d  uninorm       how often an iterate falls below the previous one, and how
                     often the result is below H (the proposition excludes it)
  P2   top block     maximum with the product t-norm, delta*w < 1 on every
                     edge: the services with C = max C are exactly those with
                     H = max H, and no value exceeds max H
  P3   bracket       probabilistic sum: both sides of Eq. (2) for every service
                     after the first round and at the end
  P4   ordering      max <= probabilistic sum <= Einstein sum <= bounded sum,
                     service by service, at every round both runs reached
  COR  budget        probabilistic sum, weight sums <= 1, delta < 1:
                     1 - C >= (1 - max H) * (1 - delta) > 1e-12 for every service

Floating-point slack is 1e-12 throughout. Writes results/proposition_checks.csv
(one row per statement and system: runs or service-checks tested, violations,
worst margin).

Usage:
    PYTHONPATH=. python3 scripts/check_propositions.py --data ~/research/rcaeval-tools/RCAEval/data/RE1
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import pandas as pd

from scripts import run_direction_variants as dv
from scripts.run_propagation_variants import DELTAS, EPSILON, MAX_ITER, prepare

fcp = dv.fcp
RESULTS = Path(__file__).resolve().parent.parent / "results"
TOL = 1e-12
MONOTONE_OPS = ("probsum", "max", "supmin", "bounded", "einstein", "bounded_dual", "einstein_dual", "mean")


def iterate(op, services, H, out, delta):
    """Synchronous iteration from C = H; returns the list of iterates."""
    C, history = dict(H), [dict(H)]
    for _ in range(MAX_ITER):
        nxt = {s: dv.receive(op, H[s], out.get(s, []), C, delta) for s in services}
        history.append(nxt)
        residual = max(abs(nxt[s] - C[s]) for s in services)
        C = nxt
        if residual < EPSILON:
            break
    return history


class Tally:
    def __init__(self):
        self.n = defaultdict(int); self.bad = defaultdict(int); self.worst = defaultdict(float)
        self.runs = defaultdict(int); self.hits = defaultdict(int)

    def count(self, key, happened):
        """A phenomenon that is expected, not a violation: how many runs show it."""
        self.runs[key] += 1
        self.hits[key] += bool(happened)

    def add(self, key, margin):
        """margin >= 0 means the statement holds; the most negative margin is kept."""
        self.n[key] += 1
        if margin < -TOL:
            self.bad[key] += 1
        self.worst[key] = min(self.worst[key], margin)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    args = ap.parse_args()
    method, ont, tally = fcp.FodaFCPMethod(), dv.OntologyAdapter(), Tally()
    for sysdir, tag in dv.SYSTEMS:
        for case in dv.RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            norm, onset, _, hyp = prepare(case, method)
            services = list(norm.services)
            H = {s: hyp[s].local_confidence for s in services}
            h_max = max(H.values())
            edges = fcp._infer_topology(case_window=norm.case_window, services=services, hypotheses=hyp,
                                        onset_time=onset, threshold=method.topology_threshold, lag=method.lag)
            for weights in ("raw", "rownorm", "capped"):
                out, _ = dv.senders_of(edges, "forward", weights, "none", hyp, ont)
                budget = all(sum(w for _, w, _ in row) <= 1.0 + TOL for row in out.values())
                for delta in DELTAS:
                    final = {}
                    for op in MONOTONE_OPS:
                        hist = iterate(op, services, H, out, delta)
                        final[op] = hist
                        tally.add(("P1a monotone", tag), min(b[s] - a[s] for a, b in zip(hist, hist[1:]) for s in services))
                        if op == "probsum":
                            if budget and delta < 1.0:
                                steps = [max(abs(b[s] - a[s]) for s in services) for a, b in zip(hist, hist[1:])]
                                for prev, cur in zip(steps, steps[1:]):
                                    tally.add(("P1b contraction", tag), delta * prev - cur)
                                floor = (1.0 - h_max) * (1.0 - delta)
                                for s in services:
                                    tally.add(("COR budget: 1-C >= (1-maxH)(1-delta)", tag), (1.0 - hist[-1][s]) - floor)
                                tally.add(("COR budget: floor > 1e-12", tag), floor - 1e-12)
                                tally.add(("COR budget: max H <= 0.95", tag), 0.95 - h_max)
                            for C in (hist[1], hist[-1]):
                                for s in services:
                                    lo = hi = 1.0 - H[s]
                                    for t, w, _ in out.get(s, []):
                                        lo *= 1.0 - delta * w
                                        hi *= 1.0 - delta * w * H[t]
                                    tally.add(("P3 bracket, necessary side", tag), (1.0 - C[s]) - lo)
                                    tally.add(("P3 bracket, sufficient side", tag), hi - (1.0 - C[s]))
                        if op == "max" and all(delta * w < 1.0 for row in out.values() for _, w, _ in row):
                            C = hist[-1]
                            same = {s for s in services if C[s] == max(C.values())} == {s for s in services if H[s] == h_max}
                            tally.add(("P2 top block unchanged", tag), 0.0 if same else -1.0)
                            tally.add(("P2 no value above max H", tag), h_max - max(C.values()))
                    for lower, upper in (("max", "probsum"), ("probsum", "einstein"), ("einstein", "bounded")):
                        # round by round: the runs stop at different rounds (tolerance 1e-6), so only
                        # iterates of the same round are comparable
                        tally.add((f"P4 {lower} <= {upper}", tag),
                                  min(b[s] - a[s] for a, b in zip(final[lower], final[upper]) for s in services))
                    hist = iterate("uninorm", services, H, out, delta)
                    drop = min(b[s] - a[s] for a, b in zip(hist, hist[1:]) for s in services)
                    tally.count(("P1d uninorm: runs with a decreasing step", tag), drop < -TOL)
                    below = min(hist[-1][s] - H[s] for s in services)
                    tally.count(("P1d uninorm: runs ending below H at some service", tag), below < -TOL)
        print(f"[{tag}] done", flush=True)
    rows = []
    for (name, tag), n in tally.n.items():
        rows.append({"statement": name, "system": tag, "checks": n, "violations": tally.bad[(name, tag)],
                     "worst_margin": tally.worst[(name, tag)]})
    for (name, tag), n in tally.runs.items():            # expected phenomena: counts, not violations
        rows.append({"statement": name, "system": tag, "checks": n, "runs_showing_it": tally.hits[(name, tag)]})
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "proposition_checks.csv", index=False)
    pd.set_option("display.width", 200)
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
