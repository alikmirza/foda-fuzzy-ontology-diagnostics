"""Paired tests, unbiased delta selection and the density sweep for the propagation variants.

Reads results/propagation_variants_per_case.csv.gz (scripts/run_propagation_variants.py)
and writes:

  results/propagation_variants_tests.csv
      per system, paired comparisons of AC@1 on the same 125 cases: exact
      McNemar test on the discordant cases and a paired percentile-bootstrap
      95 % CI on the difference (seed 42, 10,000 resamples). Comparisons:
        A  Noisy-OR delta=0.001          vs  no propagation (C = H)
        B  Noisy-OR rownorm delta=0.85   vs  no propagation
        C  Noisy-OR rownorm delta=0.85   vs  Noisy-OR raw delta=0.85 (shipped)
        D  Noisy-OR delta=0.001          vs  Noisy-OR rownorm delta=0.85
        E  ontology-guided delta=0.85    vs  unguided delta=0.85 (raw weights)
        F  max delta=0.85                vs  no propagation
      plus the same comparisons on expected AC@1 (random tie-breaking) for A.
  results/propagation_variants_loso.csv
      leave-one-system-out choice of delta for Noisy-OR with raw and with
      row-normalised weights (highest mean AC@1 on the other two systems; ties
      to the larger delta), scored on the held-out system.
  results/propagation_threshold_sweep.csv
      Noisy-OR with raw weights at each correlation threshold and delta:
      mean edge count, AC@1, expected AC@1, saturated services per case.

Deterministic.

Usage:
    python3 scripts/analyse_propagation_variants.py --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from scripts.regenerate_ranking_statistics import mcnemar_exact, paired_bootstrap

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = ("re1-ob", "re1-ss", "re1-tt")
SHIP_THR = 0.5


def pick(df, system, op, weights, guidance, delta, thr=SHIP_THR):
    sel = df[(df.system == system) & (df.threshold == thr) & (df.operator == op) & (df.weights == weights)
             & (df.guidance == guidance) & (df.delta == delta)]
    assert len(sel) == 125, (system, op, weights, guidance, delta, len(sel))
    return sel.set_index("case_id").sort_index()


COMPARISONS = [
    ("A", ("probsum", "raw", "none", 0.001), ("local", "raw", "none", 0.0)),
    ("B", ("probsum", "rownorm", "none", 0.85), ("local", "raw", "none", 0.0)),
    ("C", ("probsum", "rownorm", "none", 0.85), ("probsum", "raw", "none", 0.85)),
    ("D", ("probsum", "raw", "none", 0.001), ("probsum", "rownorm", "none", 0.85)),
    ("E", ("probsum", "raw", "ontology", 0.85), ("probsum", "raw", "none", 0.85)),
    ("F", ("max", "raw", "none", 0.85), ("local", "raw", "none", 0.0)),
]


def label(cfg):
    op, w, g, d = cfg
    return "no propagation" if op == "local" else f"{op}/{w}/{g}/delta={d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    df = pd.read_csv(RESULTS / "propagation_variants_per_case.csv.gz")

    tests = []
    for system in SYSTEMS:
        for key, a_cfg, b_cfg in COMPARISONS:
            a, b = pick(df, system, *a_cfg), pick(df, system, *b_cfg)
            metrics = ["ac1", "ac1_expected"] if key == "A" else ["ac1"]
            for m in metrics:
                x, y = a[m].to_numpy(), b[m].to_numpy()
                lo, hi = paired_bootstrap(x, y)
                row = {"system": system, "comparison": key, "metric": m, "a": label(a_cfg), "b": label(b_cfg),
                       "mean_a": round(x.mean(), 6), "mean_b": round(y.mean(), 6),
                       "diff": round(x.mean() - y.mean(), 6), "diff_lo": round(lo, 6), "diff_hi": round(hi, 6)}
                if m == "ac1":
                    a_only, b_only, p = mcnemar_exact(x, y)
                    row.update(a_only=a_only, b_only=b_only, mcnemar_p=round(p, 6))
                tests.append(row)
    tests = pd.DataFrame(tests)

    main_grid = df[df.threshold == SHIP_THR]
    loso = []
    for weights in ("raw", "rownorm"):
        grid = (main_grid[(main_grid.operator == "probsum") & (main_grid.weights == weights)
                          & (main_grid.guidance == "none")]
                .groupby(["system", "delta"])["ac1"].agg(["sum", "count"]).reset_index())
        for held in SYSTEMS:
            train = grid[grid.system != held].groupby("delta")[["sum", "count"]].sum()
            train_ac1 = train["sum"] / train["count"]
            chosen = max(d for d, v in train_ac1.items() if v == train_ac1.max())
            test = grid[grid.system == held].set_index("delta")
            loso.append({"weights": weights, "held_out": held, "delta_chosen": chosen,
                         "heldout_ac1_at_chosen": round(test.loc[chosen, "sum"] / test.loc[chosen, "count"], 6),
                         "heldout_ac1_at_0.85": round(test.loc[0.85, "sum"] / test.loc[0.85, "count"], 6)})
    loso = pd.DataFrame(loso)

    thr = (df[(df.operator == "probsum") & (df.weights == "raw") & (df.guidance == "none")]
           .groupby(["system", "threshold", "delta"])[["n_edges", "ac1", "ac1_expected", "n_saturated"]]
           .mean().round(6).reset_index())

    args.out.mkdir(parents=True, exist_ok=True)
    tests.to_csv(args.out / "propagation_variants_tests.csv", index=False)
    loso.to_csv(args.out / "propagation_variants_loso.csv", index=False)
    thr.to_csv(args.out / "propagation_threshold_sweep.csv", index=False)
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(tests.round(3).to_string(index=False)); print()
        print(loso.to_string(index=False)); print()
        print(thr[thr.delta.isin([0.001, 0.85])].pivot_table(index=["system", "threshold"], columns="delta",
              values=["n_edges", "ac1", "n_saturated"]).round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
