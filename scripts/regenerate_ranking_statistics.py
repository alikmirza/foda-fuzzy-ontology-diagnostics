"""Interval estimates and paired tests for the ranking results (Tables 1a-c, §5.9).

A consumer of committed per-case results only; nothing is re-run.

  results/week2_<method>_validation[_<system>].csv   per-case AC@1/3/5, MRR
  results/delta_sweep_per_case_<system>.csv         FODA-FCP at each delta

Outputs:

  results/stats_ranking_intervals.csv
      per method x system: AC@1, AC@3, AC@5, MRR; four 95 % intervals for AC@1
      (Clopper-Pearson exact, Wilson, the paper's case-level percentile
      bootstrap, and a cluster bootstrap that resamples the 25
      (root-cause service, fault type) scenarios rather than the 125 cases);
      exact two-sided binomial test of AC@1 against the 1/|services| chance rate.
  results/stats_paired_comparisons.csv
      per system: FODA-FCP (delta = 0.85 shipped, and delta = 0.001, the
      no-propagation limit) against each baseline, and the two FODA-FCP
      settings against each other. Exact McNemar test on the discordant
      cases, Holm-adjusted within each (system, FODA-FCP setting) family,
      and a paired percentile-bootstrap CI on the AC@1 difference.

AC@1 is the canonical pessimistic-tie value throughout (RESULTS_PROVENANCE.md).
The script asserts that the delta-sweep file at delta = 0.85 agrees case by
case with the week2 FODA-FCP file before using either.

Deterministic: every bootstrap uses seed 42 and 10,000 resamples, so output is
byte-identical across runs.

Usage:
    PYTHONPATH=. python3 scripts/regenerate_ranking_statistics.py --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

from scripts.bootstrap_ac1_ci import METHODS, N_RESAMPLES, SEED, bootstrap_ci

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("re1-ob", "", 12), ("re1-ss", "_re1-ss", 15), ("re1-tt", "_re1-tt", 64))
DISPLAY = dict(METHODS)
BASELINES = [k for k, _ in METHODS if k != "foda_fcp"]


def load(method: str, suffix: str) -> pd.DataFrame:
    df = pd.read_csv(RESULTS / f"week2_{method}_validation{suffix}.csv")
    assert len(df) == 125 and df["case_id"].is_unique, method + suffix
    return df.set_index("case_id")


def scenario(case_id: str) -> str:
    """'re1-tt_ts-auth-service_cpu_1' -> 'ts-auth-service_cpu' (rep dropped)."""
    body = case_id.split("_", 1)[1]
    return body.rsplit("_", 1)[0]


def cluster_bootstrap(hits: pd.Series) -> tuple[float, float]:
    groups = [g.to_numpy() for _, g in hits.groupby(hits.index.map(scenario))]
    rng = np.random.default_rng(SEED)
    means = np.empty(N_RESAMPLES)
    for i in range(N_RESAMPLES):
        pick = rng.integers(0, len(groups), len(groups))
        means[i] = np.concatenate([groups[j] for j in pick]).mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_bootstrap(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(a), (N_RESAMPLES, len(a)))
    diffs = a[idx].mean(axis=1) - b[idx].mean(axis=1)
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def mcnemar_exact(a: np.ndarray, b: np.ndarray) -> tuple[int, int, float]:
    a_only = int(((a == 1) & (b == 0)).sum())
    b_only = int(((a == 0) & (b == 1)).sum())
    if a_only + b_only == 0:
        return a_only, b_only, 1.0
    return a_only, b_only, float(binomtest(a_only, a_only + b_only, 0.5).pvalue)


def holm(pvals: list[float]) -> list[float]:
    order = np.argsort(pvals)
    adjusted, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adjusted[i] = running
    return adjusted


def intervals(system: str, suffix: str, n_services: int) -> list[dict]:
    rows = []
    for method, _ in METHODS:
        df = load(method, suffix)
        hits = df["AC@1"].astype(float)
        k, n = int(hits.sum()), len(hits)
        test = binomtest(k, n, 1.0 / n_services)
        exact, wilson = test.proportion_ci(method="exact"), test.proportion_ci(method="wilson")
        _, boot_lo, boot_hi = bootstrap_ci(hits.to_numpy())
        cl_lo, cl_hi = cluster_bootstrap(hits)
        rows.append({
            "system": system, "method": DISPLAY[method], "n": n, "hits": k,
            "ac1": round(k / n, 6), "ac3": round(df["AC@3"].mean(), 6),
            "ac5": round(df["AC@5"].mean(), 6), "mrr": round(df["MRR"].mean(), 6),
            "cp_lo": round(exact.low, 6), "cp_hi": round(exact.high, 6),
            "wilson_lo": round(wilson.low, 6), "wilson_hi": round(wilson.high, 6),
            "boot_lo": round(boot_lo, 6), "boot_hi": round(boot_hi, 6),
            "cluster_lo": round(cl_lo, 6), "cluster_hi": round(cl_hi, 6),
            "chance": round(1.0 / n_services, 6), "binom_p_vs_chance": round(test.pvalue, 6),
        })
    return rows


def comparisons(system: str, suffix: str) -> list[dict]:
    fcp = load("foda_fcp", suffix)["AC@1"].astype(float)
    sweep = pd.read_csv(RESULTS / f"delta_sweep_per_case_{system}.csv")
    shipped = sweep[sweep["delta"] == 0.85].set_index("case_id")["ac1_shipped"]
    limit = sweep[sweep["delta"] == 0.001].set_index("case_id")["ac1_shipped"]
    assert shipped.reindex(fcp.index).equals(fcp), f"{system}: sweep at 0.85 != week2 FODA-FCP"
    limit = limit.reindex(fcp.index)

    rows = []
    for label, a in (("FODA-FCP (delta=0.85)", fcp), ("FODA-FCP (delta=0.001)", limit)):
        family = []
        for base in BASELINES:
            b = load(base, suffix)["AC@1"].astype(float).reindex(fcp.index)
            family.append((DISPLAY[base], b))
        ps = []
        for name, b in family:
            a_only, b_only, p = mcnemar_exact(a.to_numpy(), b.to_numpy())
            lo, hi = paired_bootstrap(a.to_numpy(), b.to_numpy())
            ps.append(p)
            rows.append({"system": system, "a": label, "b": name, "acc_a": round(a.mean(), 6),
                         "acc_b": round(b.mean(), 6), "diff": round(a.mean() - b.mean(), 6),
                         "diff_lo": round(lo, 6), "diff_hi": round(hi, 6),
                         "a_only": a_only, "b_only": b_only, "mcnemar_p": round(p, 6)})
        for row, adj in zip(rows[-len(family):], holm(ps)):
            row["holm_p"] = round(adj, 6)

    a_only, b_only, p = mcnemar_exact(limit.to_numpy(), fcp.to_numpy())
    lo, hi = paired_bootstrap(limit.to_numpy(), fcp.to_numpy())
    rows.append({"system": system, "a": "FODA-FCP (delta=0.001)", "b": "FODA-FCP (delta=0.85)",
                 "acc_a": round(limit.mean(), 6), "acc_b": round(fcp.mean(), 6),
                 "diff": round(limit.mean() - fcp.mean(), 6), "diff_lo": round(lo, 6),
                 "diff_hi": round(hi, 6), "a_only": a_only, "b_only": b_only,
                 "mcnemar_p": round(p, 6), "holm_p": round(p, 6)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    iv, cmp_ = [], []
    for system, suffix, n_services in SYSTEMS:
        iv += intervals(system, suffix, n_services)
        cmp_ += comparisons(system, suffix)
    iv_df, cmp_df = pd.DataFrame(iv), pd.DataFrame(cmp_)
    iv_df.to_csv(args.out / "stats_ranking_intervals.csv", index=False)
    cmp_df.to_csv(args.out / "stats_paired_comparisons.csv", index=False)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(iv_df.round(3).to_string(index=False))
        print()
        print(cmp_df.round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
