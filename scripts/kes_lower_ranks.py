"""Lower-rank measures for the KES 2027 paper, and the published baseline figures.

Writes

  results/kes_lower_ranks.csv
      AC@3, AC@5, MRR and Avg@5 (the mean of AC@1..AC@5) under the pessimistic
      tie rule, and expected AC@1 / Avg@5 under random tie-breaking where the
      per-case tie block is recorded, for the configurations the paper reports
      and for the non-fuzzy rankers run on the same cases.
  results/kes_published_baselines.csv
      Avg@5 per fault type as published by the datasets' authors (Pham, Ha and
      Zhang, ASE 2024, Table 5; arXiv:2408.13729v2, read 2026-11-23), with the
      per-system mean over the five fault types. Transcribed, not computed:
      those runs are given the failure time, ours withhold it.

Everything else is read from committed per-case results; nothing is re-run.
For the re-implemented baselines the per-case rank is recovered from the
recorded reciprocal rank and checked against the recorded AC@1/3/5.

Usage:
    PYTHONPATH=. python3 scripts/kes_lower_ranks.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SYSTEMS = ("re1-ob", "re1-ss", "re1-tt")

# (label, graph, direction, weights, guidance, operator, delta); delta None = local evidence
CONFIGS = (
    ("Local evidence only", "inferred", "forward", "raw", "none", "local", None),
    ("Probabilistic sum, raw (evaluated)", "inferred", "forward", "raw", "none", "probsum", 0.85),
    ("Probabilistic sum, normalised", "inferred", "forward", "rownorm", "none", "probsum", 0.85),
    ("Probabilistic sum, capped", "inferred", "forward", "capped", "none", "probsum", 0.85),
    ("Maximum, raw", "inferred", "forward", "raw", "none", "max", 0.85),
    ("Maximum, normalised", "inferred", "forward", "rownorm", "none", "max", 0.85),
    ("Weighted mean", "inferred", "forward", "raw", "none", "mean", 0.85),
    ("Call graph, reversed, unit, 0.3", "callgraph", "reversed", "unit", "none", "probsum", 0.3),
)

# Pham, Ha, Zhang (2024), ASE '24, Table 5: Avg@5 by fault type (CPU, MEM, DISK, DELAY, LOSS)
# on Online Boutique, Sock Shop 2 and Train Ticket (125 cases each; RCAEval calls these RE1).
# "t0": given the exact failure time; "t60": given that time plus 60 s.
PUBLISHED = {
    ("BARO", "t0"): {"re1-ob": (0.97, 1, 0.91, 0.98, 0.67), "re1-ss": (1, 0.98, 0.94, 0.98, 0.87),
                     "re1-tt": (0.90, 0.96, 0.84, 0.77, 0.66)},
    ("BARO", "t60"): {"re1-ob": (0.94, 0.99, 0.87, 0.99, 0.6), "re1-ss": (0.99, 0.98, 0.94, 1, 0.88),
                      "re1-tt": (0.81, 0.99, 0.77, 0.82, 0.72)},
    ("NSigma", "t0"): {"re1-ob": (0.94, 1, 0.9, 0.98, 0.67), "re1-ss": (0.98, 0.98, 0.94, 0.98, 0.9),
                       "re1-tt": (0.81, 0.96, 0.85, 0.61, 0.7)},
    ("CIRCA", "t0"): {"re1-ob": (0.94, 0.97, 0.7, 0.92, 0.55), "re1-ss": (0.97, 0.98, 0.92, 0.98, 0.88),
                      "re1-tt": (0.66, 0.93, 0.64, 0.64, 0.57)},
    ("RCD", "t0"): {"re1-ob": (0.91, 0.74, 0.67, 0.38, 0.47), "re1-ss": (0.62, 0.46, 0.62, 0.48, 0.37),
                    "re1-tt": (0.08, 0.01, 0.31, 0.09, 0.12)},
    ("CausalRCA", "none"): {"re1-ob": (0.97, 0.98, 0.71, 0.92, 0.52), "re1-ss": (0.49, 0.82, 0.74, 0.61, 0.47),
                            "re1-tt": (0.53, 0.3, 0.13, 0.17, 0.11)},
    ("Dummy", "none"): {"re1-ob": (0.25, 0.24, 0.26, 0.26, 0.25), "re1-ss": (0.37, 0.38, 0.33, 0.38, 0.37),
                        "re1-tt": (0.07, 0.08, 0.06, 0.07, 0.07)},
}


def from_rank(rank: pd.Series) -> dict:
    ac = {k: float((rank <= k).mean()) for k in range(1, 6)}
    return {"ac1": ac[1], "ac3": ac[3], "ac5": ac[5], "mrr": float((1.0 / rank).mean()),
            "avg5": float(np.mean([ac[k] for k in range(1, 6)]))}


def main() -> int:
    df = pd.read_csv(RESULTS / "direction_variants_per_case.csv.gz")
    # Train Ticket's call graph is the trace-measured one (scripts/run_tracegraph_variants.py)
    trace = pd.read_csv(RESULTS / "tracegraph_variants_per_case.csv.gz")
    trace = trace[(trace.system == "re1-tt") & (trace.graph == "trace")].assign(graph="callgraph")
    df = pd.concat([df, trace], ignore_index=True)
    rows = []
    for system in SYSTEMS:
        for label, graph, direction, weights, guidance, operator, delta in CONFIGS:
            c = df[(df.system == system) & (df.operator == operator)]
            if operator != "local":
                c = c[(c.graph == graph) & (c.direction == direction) & (c.weights == weights)
                      & (c.guidance == guidance) & np.isclose(c.delta, delta)]
            else:
                c = c.drop_duplicates("case_id")
            if c.empty:
                continue
            assert len(c) == 125, (system, label, len(c))
            e = {k: ((k - c.n_above) / c.gt_block).clip(0, 1).mean() for k in range(1, 6)}
            rows.append({"system": system, "method": label, **from_rank(c["rank"]),
                         "ac1_expected": float(e[1]), "avg5_expected": float(np.mean(list(e.values())))})

    rl = pd.read_csv(RESULTS / "rule_learning_per_case.csv")
    rl = rl[rl.protocol == "loso"]
    for system, suffix in zip(SYSTEMS, ("", "_re1-ss", "_re1-tt")):
        v = rl[(rl.system == system) & (rl.variant == "anomaly_max_rawz")]
        assert len(v) == 125
        rank = (1.0 / v.rr).round().astype(int)
        assert np.allclose(1.0 / rank, v.rr) and ((rank <= 1) == (v.ac1 > 0)).all() and ((rank <= 3) == (v.ac3 > 0)).all()
        rows.append({"system": system, "method": "Largest |z| (no rules)", **from_rank(rank),
                     "ac1_expected": float(v.ac1_expected.mean()), "avg5_expected": np.nan})
        for m, label in (("baro", "BARO"), ("causalrca", "CausalRCA"), ("microrca", "MicroRCA"),
                         ("monitorrank", "MonitorRank")):
            b = pd.read_csv(RESULTS / f"week2_{m}_validation{suffix}.csv")
            assert len(b) == 125
            rank = (1.0 / b["MRR"]).round().astype(int)
            assert np.allclose(1.0 / rank, b["MRR"]), (system, m)
            for k in (1, 3, 5):
                assert ((rank <= k) == (b[f"AC@{k}"] > 0)).all(), (system, m, k)
            rows.append({"system": system, "method": f"{label} (re-implemented)", **from_rank(rank),
                         "ac1_expected": np.nan, "avg5_expected": np.nan})
    out = pd.DataFrame(rows)[["system", "method", "ac1", "ac1_expected", "ac3", "ac5", "mrr", "avg5", "avg5_expected"]]
    out.round(4).to_csv(RESULTS / "kes_lower_ranks.csv", index=False)

    pub = []
    for (method, time), by_system in PUBLISHED.items():
        for system, vals in by_system.items():
            assert len(vals) == 5
            pub.append({"system": system, "method": method, "failure_time": time,
                        **dict(zip(("cpu", "mem", "disk", "delay", "loss"), vals)),
                        "mean_avg5": round(float(np.mean(vals)), 4)})
    pub = pd.DataFrame(pub)
    pub.to_csv(RESULTS / "kes_published_baselines.csv", index=False)

    pd.set_option("display.width", 220)
    print(out.round(3).to_string(index=False))
    print(pub.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
