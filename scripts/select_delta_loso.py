"""Leave-one-system-out selection of the damping factor delta.

The delta sweep (results/delta_sweep_per_case_<system>.csv) shows where the
optimum lies on the very systems it is measured on, so reading the best delta
off it is optimistic. This script removes that bias: for each held-out system
it picks delta on the other two systems only (highest mean AC@1 over their
250 cases; ties go to the larger delta, the one closer to the shipped
setting) and reports AC@1 at that delta on the held-out system, next to the
shipped delta = 0.85 and the held-out system's own best.

A consumer of committed files only; nothing is re-run. Deterministic.

Usage:
    python3 scripts/select_delta_loso.py --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = ("re1-ob", "re1-ss", "re1-tt")
SHIPPED = 0.85


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()

    sweep = pd.concat(pd.read_csv(RESULTS / f"delta_sweep_per_case_{s}.csv") for s in SYSTEMS)
    by = sweep.groupby(["system", "delta"])["ac1_shipped"].agg(["sum", "count"]).reset_index()

    rows = []
    for held in SYSTEMS:
        train = by[by["system"] != held].groupby("delta")[["sum", "count"]].sum()
        train["ac1"] = train["sum"] / train["count"]
        best = train["ac1"].max()
        chosen = max(d for d, a in train["ac1"].items() if a == best)
        test = by[by["system"] == held].set_index("delta")
        test_ac1 = test["sum"] / test["count"]
        rows.append({
            "held_out": held,
            "delta_chosen": chosen,
            "train_ac1_at_chosen": round(best, 6),
            "heldout_ac1_at_chosen": round(test_ac1[chosen], 6),
            "heldout_ac1_shipped": round(test_ac1[SHIPPED], 6),
            "heldout_ac1_own_best": round(test_ac1.max(), 6),
            "heldout_delta_own_best": max(d for d, a in test_ac1.items() if a == test_ac1.max()),
        })
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "delta_selection_loso.csv", index=False)
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
