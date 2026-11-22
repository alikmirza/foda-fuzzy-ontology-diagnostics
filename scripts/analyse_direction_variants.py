"""Does the direction of propagation, or a real call graph, change the conclusion?

Reads results/direction_variants_per_case.csv.gz and writes:

  results/direction_variants_tests.csv
      Planned comparisons against local evidence alone (C = H), per system, for
      the probabilistic sum at delta = 0.85 without guidance:
        inferred graph:  forward / reversed  x  raw / rownorm / capped
        call graph:      forward / reversed  x  unit / equal / share
      plus ontology guidance (s2r, r2s) against no guidance for each of those.
      For AC@1 and expected AC@1: the mean difference with a paired cluster
      bootstrap 95 % interval that resamples the 25 fault scenarios
      (root-cause service x fault type), not the 125 cases, because the five
      repetitions of a scenario are not independent (seed 42, 10,000 resamples).
      A two-sided bootstrap p-value and its Holm adjustment within each
      (system, metric) family are given.
  results/direction_variants_best.csv
      Descriptive only: per system and graph, the configuration with the highest
      expected AC@1 over every operator, weighting, direction, guidance and
      damping level, and its margin over local evidence. The maximum over
      hundreds of configurations is optimistic by construction.

  results/direction_variants_callgraph_selection.csv
      Call graphs only (two systems): the probabilistic-sum configuration
      (direction, weighting, damping; no guidance) with the highest expected
      AC@1 on one system is scored on the other, against local evidence, with
      the same cluster bootstrap. Ties in the selection go to the larger
      damping. This is the unbiased version of "best configuration".

Deterministic.

Usage:
    python3 scripts/analyse_direction_variants.py --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

RESULTS = Path(__file__).resolve().parent.parent / "results"
SEED, N_RESAMPLES = 42, 10_000
KEYS = ["graph", "direction", "weights", "guidance", "operator", "delta"]


def cluster_bootstrap(diff: pd.Series, clusters: pd.Series):
    """Mean of a paired per-case difference, CI and p-value resampling clusters."""
    groups = [g.to_numpy() for _, g in diff.groupby(clusters)]
    sums = np.array([g.sum() for g in groups]); sizes = np.array([len(g) for g in groups])
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(groups), (N_RESAMPLES, len(groups)))
    means = sums[pick].sum(axis=1) / sizes[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    p = 2 * min((means <= 0).mean(), (means >= 0).mean())
    return float(diff.mean()), float(lo), float(hi), float(min(1.0, p))


def holm(pvals):
    order = np.argsort(pvals); adj = np.empty(len(pvals)); running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i])); adj[i] = running
    return adj


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    df = pd.read_csv(RESULTS / "direction_variants_per_case.csv.gz")
    df["scenario"] = df["root"] + "_" + df["fault"]

    def sel(system, graph, direction, weights, guidance, operator="probsum", delta=0.85):
        s = df[(df.system == system) & (df.graph == graph) & (df.direction == direction) & (df.weights == weights)
               & (df.guidance == guidance) & (df.operator == operator) & (df.delta == delta)]
        assert len(s) == 125, (system, graph, direction, weights, guidance, len(s))
        return s.set_index("case_id").sort_index()

    tests = []
    for system in ("re1-ob", "re1-ss", "re1-tt"):
        local = df[(df.system == system) & (df.operator == "local")].set_index("case_id").sort_index()
        plans = [("inferred", d, w) for d in ("forward", "reversed") for w in ("raw", "rownorm", "capped")]
        if system != "re1-tt":
            plans += [("callgraph", d, w) for d in ("forward", "reversed") for w in ("unit", "equal", "share")]
        rows = []
        for graph, direction, weights in plans:
            base = sel(system, graph, direction, weights, "none")
            comps = [("vs local", base, local, "none")]
            for g in ("s2r", "r2s"):
                comps.append((f"guidance {g} vs none", sel(system, graph, direction, weights, g), base, g))
            for label, a, b, guidance in comps:
                for metric in ("ac1", "ac1_expected"):
                    d, lo, hi, p = cluster_bootstrap(a[metric] - b[metric], local["scenario"])
                    rows.append({"system": system, "graph": graph, "direction": direction, "weights": weights,
                                 "comparison": label, "metric": metric, "mean_a": round(a[metric].mean(), 4),
                                 "mean_b": round(b[metric].mean(), 4), "diff": round(d, 4),
                                 "diff_lo": round(lo, 4), "diff_hi": round(hi, 4), "p": round(p, 4)})
        t = pd.DataFrame(rows)
        t["p_holm"] = np.nan
        for metric in ("ac1", "ac1_expected"):
            m = t.metric == metric
            t.loc[m, "p_holm"] = holm(t.loc[m, "p"].to_numpy()).round(4)
        tests.append(t)
    tests = pd.concat(tests, ignore_index=True)

    summ = pd.read_csv(RESULTS / "direction_variants_summary.csv")
    best = []
    for (system, graph), g in summ[summ.operator != "local"].groupby(["system", "graph"], sort=False):
        loc = summ[(summ.system == system) & (summ.operator == "local")].iloc[0]
        b = g.loc[g.ac1_expected.idxmax()]
        best.append({"system": system, "graph": graph, "configs": len(g), "local_ac1_expected": loc.ac1_expected,
                     **{k: b[k] for k in KEYS if k != "graph"}, "best_ac1_expected": b.ac1_expected,
                     "margin": round(b.ac1_expected - loc.ac1_expected, 4), "best_ac1": b.ac1, "local_ac1": loc.ac1})
    best = pd.DataFrame(best)

    selection = []
    cg = summ[(summ.graph == "callgraph") & (summ.operator == "probsum") & (summ.guidance == "none")]
    for held, train in (("re1-ob", "re1-ss"), ("re1-ss", "re1-ob")):
        g = cg[cg.system == train]
        top = g[g.ac1_expected == g.ac1_expected.max()].sort_values("delta").iloc[-1]
        a = sel(held, "callgraph", top.direction, top.weights, "none", delta=top.delta)
        local = df[(df.system == held) & (df.operator == "local")].set_index("case_id").sort_index()
        row = {"held_out": held, "selected_on": train, "direction": top.direction, "weights": top.weights,
               "delta": top.delta}
        for metric in ("ac1", "ac1_expected", "ac3"):
            d, lo, hi, p = cluster_bootstrap(a[metric] - local[metric], local["scenario"])
            row.update({f"{metric}": round(a[metric].mean(), 4), f"{metric}_local": round(local[metric].mean(), 4),
                        f"{metric}_diff": round(d, 4), f"{metric}_lo": round(lo, 4), f"{metric}_hi": round(hi, 4),
                        f"{metric}_p": round(p, 4)})
        selection.append(row)
    selection = pd.DataFrame(selection)
    selection.to_csv(args.out / "direction_variants_callgraph_selection.csv", index=False)

    args.out.mkdir(parents=True, exist_ok=True)
    tests.to_csv(args.out / "direction_variants_tests.csv", index=False)
    best.to_csv(args.out / "direction_variants_best.csv", index=False)
    with pd.option_context("display.width", 230, "display.max_columns", 30, "display.max_rows", 300):
        v = tests[(tests.comparison == "vs local") & (tests.metric == "ac1_expected")]
        print(v.drop(columns=["comparison", "metric"]).to_string(index=False)); print()
        print(best.to_string(index=False)); print()
        print(selection.T.to_string(header=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
