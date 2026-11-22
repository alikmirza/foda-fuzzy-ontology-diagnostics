"""Tests for the trace-measured call graphs (scripts/run_tracegraph_variants.py).

Reads results/tracegraph_variants_per_case.csv.gz and writes

  results/tracegraph_tests.csv
      Planned comparisons with local evidence, per system and graph, for the
      probabilistic sum without guidance: the configuration fixed in advance
      (reversed, unit weights, delta = 0.3; chosen across Online Boutique and
      Sock Shop on the earlier call graphs), its forward counterpart, and both
      at delta = 0.85. Difference in expected AC@1, pessimistic AC@1, AC@3 and
      expected Avg@5, with a cluster bootstrap over the 25 fault scenarios
      (10,000 resamples, seed 42) and Holm adjustment within system and graph.
  results/tracegraph_by_fault.csv
      Expected AC@1 by injected fault type for the same configurations.
  results/tracegraph_tie_order.csv
      Among cases whose root cause shares the top non-zero local evidence, the
      probability that the propagated score puts it first, against chance.
  results/tracegraph_grid.csv
      Expected AC@1 over direction x weights x delta (probabilistic sum, no
      guidance), with the best cell per system and graph. Descriptive only.
  results/tracegraph_selection.csv
      Configuration chosen on one application's trace graph and scored on the
      other's.

Usage:
    PYTHONPATH=. python3 scripts/analyse_tracegraph_variants.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.analyse_kes_revision import add_metrics, boot, holm

RESULTS = Path(__file__).resolve().parent.parent / "results"
PLANNED = (("reversed", 0.3, "fixed in advance"), ("forward", 0.3, "counterpart"),
           ("reversed", 0.85, "counterpart"), ("forward", 0.85, "counterpart"))
MEASURES = (("ac1_expected", "e1"), ("ac1", "p1"), ("ac3", "p3"), ("avg5_expected", "avg5_expected"))


def main() -> int:
    df = add_metrics(pd.read_csv(RESULTS / "tracegraph_variants_per_case.csv.gz"))
    plain = df[(df.operator == "probsum") & (df.guidance == "none")]
    tests, faults, ties, grid, selection = [], [], [], [], []
    for system in ("re1-ob", "re1-tt"):
        loc = df[(df.system == system) & (df.operator == "local")].set_index("case_id")
        for graph in ("trace", "trace_db"):
            g = plain[(plain.system == system) & (plain.graph == graph)]
            block = []
            for direction, delta, role in PLANNED:
                c = g[(g.direction == direction) & (g.weights == "unit") & np.isclose(g.delta, delta)].set_index("case_id")
                assert len(c) == 125, (system, graph, direction, delta, len(c))
                c = c.reindex(loc.index)
                row = {"system": system, "graph": graph, "direction": direction, "weights": "unit", "delta": delta,
                       "role": role, "n_edges": int(c.n_edges.median())}
                for name, col in MEASURES:
                    d, lo, hi, p = boot(c[col] - loc[col], loc.scenario)
                    row.update({name: c[col].mean(), f"{name}_local": loc[col].mean(), f"{name}_diff": d,
                                f"{name}_lo": lo, f"{name}_hi": hi, f"{name}_p": p})
                block.append(row)
                for fault, idx in loc.groupby("fault").groups.items():
                    faults.append({"system": system, "graph": graph, "direction": direction, "delta": delta,
                                   "fault": fault, "cases": len(idx), "ac1_expected_local": loc.loc[idx, "e1"].mean(),
                                   "ac1_expected": c.loc[idx, "e1"].mean()})
                t = c[(c.local_block > 1) & c.any_fired]          # non-zero ties only, as in analyse_kes_revision
                if len(t):
                    d, lo, hi, p = boot(t.p_first_in_local_block - 1.0 / t.local_block, loc.scenario.reindex(t.index))
                    ties.append({"system": system, "graph": graph, "direction": direction, "delta": delta,
                                 "tied_cases": len(t), "p_first": t.p_first_in_local_block.mean(),
                                 "chance": (1.0 / t.local_block).mean(), "gain": d, "gain_lo": lo, "gain_hi": hi, "p": p})
            adj = holm([r["ac1_expected_p"] for r in block])
            for r, a in zip(block, adj):
                r["ac1_expected_p_holm"] = a
            tests += block
            cells = (g.groupby(["direction", "weights", "delta"]).agg(ac1_expected=("e1", "mean"), ac1=("p1", "mean"),
                                                                        saturated=("n_saturated", "mean")).reset_index())
            cells.insert(0, "graph", graph); cells.insert(0, "system", system)
            cells["ac1_expected_local"] = loc.e1.mean()
            cells["best"] = cells.ac1_expected == cells.ac1_expected.max()
            grid.append(cells)
    grid = pd.concat(grid, ignore_index=True)
    for graph in ("trace", "trace_db"):
        for held, chosen_on in (("re1-ob", "re1-tt"), ("re1-tt", "re1-ob")):
            src = grid[(grid.system == chosen_on) & (grid.graph == graph)]
            top = src.sort_values(["ac1_expected", "delta"], ascending=[False, False]).iloc[0]   # ties: larger delta
            loc = df[(df.system == held) & (df.operator == "local")].set_index("case_id")
            c = plain[(plain.system == held) & (plain.graph == graph) & (plain.direction == top.direction)
                      & (plain.weights == top.weights) & np.isclose(plain.delta, top.delta)].set_index("case_id")
            d, lo, hi, p = boot(c.e1.reindex(loc.index) - loc.e1, loc.scenario)
            selection.append({"graph": graph, "held_out": held, "selected_on": chosen_on, "direction": top.direction,
                              "weights": top.weights, "delta": top.delta, "ac1_expected": c.e1.mean(),
                              "ac1_expected_local": loc.e1.mean(), "diff": d, "lo": lo, "hi": hi, "p": p})
    out = {"tests": pd.DataFrame(tests), "by_fault": pd.DataFrame(faults), "tie_order": pd.DataFrame(ties),
           "grid": grid, "selection": pd.DataFrame(selection)}
    for name, t in out.items():
        t.round(4).to_csv(RESULTS / f"tracegraph_{name}.csv", index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    cols = ["system", "graph", "direction", "delta", "role", "n_edges", "ac1_expected", "ac1_expected_local",
            "ac1_expected_diff", "ac1_expected_lo", "ac1_expected_hi", "ac1_expected_p_holm", "ac1", "ac1_local", "ac3", "ac3_local"]
    print(out["tests"][cols].round(3).to_string(index=False))
    print(out["tie_order"].round(3).to_string(index=False))
    print(out["selection"].round(3).to_string(index=False))
    print(grid[grid.best].round(3).to_string(index=False))
    f = out["by_fault"]
    print(f[(f.direction == "reversed") & (f.delta == 0.3)].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
