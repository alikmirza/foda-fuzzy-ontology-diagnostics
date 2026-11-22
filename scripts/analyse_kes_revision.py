"""Tables for the revised KES paper, from committed per-case results only.

Inputs: results/direction_variants_per_case.csv.gz (scripts/run_direction_variants.py),
results/rule_learning_dataset.csv.gz and results/rule_learning_per_case.csv
(scripts/learn_rules_experiment.py), results/week2_<method>_validation*.csv.

Every interval and p-value resamples the 25 fault scenarios of a system
(root-cause service x fault type), not its 125 cases (seed 42, 10,000 resamples).
Expected AC@k is the score under random tie-breaking,
clip((k - n_above) / gt_block, 0, 1); pessimistic AC@k uses the worst rank in the
ground truth's tie block. Avg@5 is the mean of AC@1..AC@5.

Outputs (all under --out, prefix kes_):
  operators.csv        every operator x weighting on the inferred graph, forward,
                       delta = 0.85: both tie conventions, AC@3, AC@5, MRR, Avg@5,
                       saturation, runs at the iteration cap; difference from
                       local evidence in expected AC@1 with interval and
                       Holm-adjusted p within the system
  budget_vs_damping.csv  raw weights at delta = 0.001, normalised and capped at
                       0.85, against local evidence
  loso.csv             leave-one-system-out choice of delta by expected AC@1
  breakdown.csv        key configurations by fault type, by root-cause service and
                       by whether any rule fired
  failures.csv         every case of the key configurations assigned to: correct,
                       no rule fired, inside the saturated block (the ground truth
                       is itself saturated, to 1e-12, but not alone at the top),
                       below a saturated block, tied at the top without
                       saturation, overtaken by an unsaturated service
  evidence_ties.csv    distribution of local evidence H and of its ties
  tie_order.csv        within the top tie block of H (non-zero ties only; when no
                       rule fires nothing can be ordered): does propagation put
                       the ground truth first more often than chance?
  baselines.csv        non-fuzzy local score (largest |z|), the re-implemented
                       baselines and the FCP variants on the same cases
  explanations.csv     fault-type agreement of the explained prototype with the
                       injected fault, fallback share, SC and EC

Deterministic.

Usage:
    PYTHONPATH=. python3 scripts/analyse_kes_revision.py --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import evaluation.methods.foda_fcp as fcp

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = ("re1-ob", "re1-ss", "re1-tt")
SEED, N_RESAMPLES = 42, 10_000
PROTOTYPE_TO_FAULT = {"CpuSaturation": "cpu", "MemoryLeak": "mem", "LatencySpike": "delay",
                      "DiskIoBottleneck": "disk", "NetworkCongestion": "loss"}
TYPEABLE = ("cpu", "mem", "delay")        # faults whose prototype the rule base can assign
KEY = {  # name -> (graph, direction, weights, guidance, operator, delta)
    "local": ("none", "none", "none", "none", "local", 0.0),
    "shipped": ("inferred", "forward", "raw", "none", "probsum", 0.85),
    "normalised": ("inferred", "forward", "rownorm", "none", "probsum", 0.85),
    "capped": ("inferred", "forward", "capped", "none", "probsum", 0.85),
    "max": ("inferred", "forward", "rownorm", "none", "max", 0.85),
    "callgraph_forward": ("callgraph", "forward", "unit", "none", "probsum", 0.85),
    "callgraph_reversed": ("callgraph", "reversed", "unit", "none", "probsum", 0.3),
}


def boot(diff: pd.Series, clusters: pd.Series):
    groups = [g.to_numpy() for _, g in diff.groupby(clusters)]
    sums = np.array([g.sum() for g in groups]); sizes = np.array([len(g) for g in groups])
    pick = np.random.default_rng(SEED).integers(0, len(groups), (N_RESAMPLES, len(groups)))
    means = sums[pick].sum(axis=1) / sizes[pick].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), float(lo), float(hi), float(min(1.0, 2 * min((means <= 0).mean(), (means >= 0).mean())))


def holm(p):
    p = np.asarray(p, dtype=float); order = np.argsort(p); adj = np.empty(len(p)); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(p) - rank) * p[i])); adj[i] = run
    return adj


def add_metrics(df: pd.DataFrame) -> pd.DataFrame:
    for k in range(1, 6):
        df[f"e{k}"] = ((k - df.n_above) / df.gt_block).clip(0, 1)
        df[f"p{k}"] = (df["rank"] <= k).astype(float)
    df["avg5_expected"] = df[[f"e{k}" for k in range(1, 6)]].mean(axis=1)
    df["avg5"] = df[[f"p{k}" for k in range(1, 6)]].mean(axis=1)
    df["scenario"] = df["root"] + "_" + df["fault"]
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    df = add_metrics(pd.read_csv(RESULTS / "direction_variants_per_case.csv.gz"))
    assert np.allclose(df.e1, df.ac1_expected), "expected AC@1 does not match n_above / gt_block"

    def pick(system, graph, direction, weights, guidance, operator, delta):
        s = df[(df.system == system) & (df.graph == graph) & (df.direction == direction) & (df.weights == weights)
               & (df.guidance == guidance) & (df.operator == operator) & (df.delta == delta)]
        return s.set_index("case_id").sort_index()

    def key(system, name):
        s = pick(system, *KEY[name])
        return s if len(s) == 125 else None

    local = {s: key(s, "local") for s in SYSTEMS}
    out = {}

    # ---- operators at delta = 0.85 -----------------------------------------
    rows = []
    for system in SYSTEMS:
        sys_rows = []
        g = df[(df.system == system) & (df.graph == "inferred") & (df.direction == "forward")
               & (df.guidance == "none") & (df.delta == 0.85)]
        for (op, w), c in g.groupby(["operator", "weights"], sort=False):
            c = c.set_index("case_id").sort_index()
            d, lo, hi, p = boot(c.e1 - local[system].e1, local[system].scenario)
            sys_rows.append({"system": system, "operator": op, "weights": w, "ac1": c.p1.mean(),
                             "ac1_expected": c.e1.mean(), "ac3": c.p3.mean(), "ac5": c.p5.mean(), "mrr": c.rr.mean(),
                             "avg5": c.avg5.mean(), "avg5_expected": c.avg5_expected.mean(),
                             "saturated_per_case": c.n_saturated.mean(), "runs_at_cap": int(c.hit_cap.sum()),
                             "diff_vs_local": d, "diff_lo": lo, "diff_hi": hi, "p": p})
        t = pd.DataFrame(sys_rows); t["p_holm"] = holm(t.p)
        loc = local[system]
        t = pd.concat([pd.DataFrame([{"system": system, "operator": "local", "weights": "-", "ac1": loc.p1.mean(),
                                      "ac1_expected": loc.e1.mean(), "ac3": loc.p3.mean(), "ac5": loc.p5.mean(),
                                      "mrr": loc.rr.mean(), "avg5": loc.avg5.mean(),
                                      "avg5_expected": loc.avg5_expected.mean(), "saturated_per_case": 0.0,
                                      "runs_at_cap": 0}]), t], ignore_index=True)
        rows.append(t)
    out["operators"] = pd.concat(rows, ignore_index=True)

    # ---- weight budget against damping --------------------------------------
    rows = []
    for system in SYSTEMS:
        for name, cfg in (("raw, delta=0.001", ("inferred", "forward", "raw", "none", "probsum", 0.001)),
                          ("raw, delta=0.85", KEY["shipped"]), ("normalised, delta=0.85", KEY["normalised"]),
                          ("capped, delta=0.85", KEY["capped"]),
                          ("normalised, delta=0.001", ("inferred", "forward", "rownorm", "none", "probsum", 0.001))):
            c = pick(system, *cfg)
            d, lo, hi, p = boot(c.e1 - local[system].e1, local[system].scenario)
            rows.append({"system": system, "configuration": name, "ac1": c.p1.mean(), "ac1_expected": c.e1.mean(),
                         "local_expected": local[system].e1.mean(), "diff": d, "diff_lo": lo, "diff_hi": hi, "p": p})
    out["budget_vs_damping"] = pd.DataFrame(rows)

    # ---- leave-one-system-out damping, selected on expected AC@1 ------------
    rows = []
    for w in ("raw", "rownorm", "capped"):
        g = df[(df.graph == "inferred") & (df.direction == "forward") & (df.guidance == "none")
               & (df.operator == "probsum") & (df.weights == w)]
        for held in SYSTEMS:
            train = g[g.system != held].groupby("delta").e1.mean()
            chosen = max(d for d, v in train.items() if np.isclose(v, train.max()))
            c = g[(g.system == held) & (g.delta == chosen)].set_index("case_id").sort_index()
            d, lo, hi, p = boot(c.e1 - local[held].e1, local[held].scenario)
            rows.append({"weights": w, "held_out": held, "delta_chosen": chosen, "ac1_expected": c.e1.mean(),
                         "ac1": c.p1.mean(), "local_expected": local[held].e1.mean(),
                         "diff": d, "diff_lo": lo, "diff_hi": hi, "p": p})
    out["loso"] = pd.DataFrame(rows)

    # ---- breakdowns ----------------------------------------------------------
    rows = []
    for system in SYSTEMS:
        for name in KEY:
            c = key(system, name)
            if c is None:
                continue
            for by, col in (("fault", "fault"), ("root", "root"), ("rule fired anywhere", "any_fired"),
                            ("rule fired at root cause", "gt_fired")):
                for value, part in c.groupby(col):
                    rows.append({"system": system, "configuration": name, "by": by, "value": value,
                                 "cases": len(part), "ac1": part.p1.mean(), "ac1_expected": part.e1.mean(),
                                 "ac3": part.p3.mean()})
            rows.append({"system": system, "configuration": name, "by": "all", "value": "all", "cases": len(c),
                         "ac1": c.p1.mean(), "ac1_expected": c.e1.mean(), "ac3": c.p3.mean()})
    out["breakdown"] = pd.DataFrame(rows)

    # ---- failure split ---------------------------------------------------------
    def category(r):
        if r["rank"] == 1:
            return "correct"
        if not r["any_fired"]:
            return "no rule fired"
        if r["n_saturated"] > 0:
            # the saturated services are the top n_saturated ones (C >= 1 - 1e-12)
            return "inside the saturated block" if r["n_above"] < r["n_saturated"] else "below a saturated block"
        return "tied at the top, unsaturated" if r["n_above"] == 0 else "overtaken by an unsaturated service"
    rows = []
    for system in SYSTEMS:
        for name in KEY:
            c = key(system, name)
            if c is None:
                continue
            counts = c.apply(category, axis=1).value_counts()
            for cat, n in counts.items():
                rows.append({"system": system, "configuration": name, "category": cat, "cases": int(n)})
    out["failures"] = pd.DataFrame(rows)

    # ---- distribution of H and its ties ---------------------------------------
    ds = pd.read_csv(RESULTS / "rule_learning_dataset.csv.gz")
    cfs = sorted({round(r.cf, 6) for r in fcp.RULE_BASE})
    rows = []
    for system in SYSTEMS:
        s = ds[ds.system == system]; h = s.expert_fuzzy
        loc = local[system]
        fired = loc[loc.any_fired]
        rows.append({
            "system": system, "services": len(s), "share_H_zero": (h == 0).mean(),
            "distinct_nonzero_H": h[h > 0].round(12).nunique(),
            "share_nonzero_H_equal_to_a_CF": h[h > 0].round(6).isin(cfs).mean(),
            "cases": len(loc), "cases_no_rule": int((~loc.any_fired).sum()),
            "cases_unique_top": int((fired.top_block == 1).sum()),
            "cases_tied_top": int((fired.top_block > 1).sum()),
            "median_tied_block": float(fired[fired.top_block > 1].top_block.median()) if (fired.top_block > 1).any() else 0.0,
            "tied_top_at_a_CF": int(((fired.top_block > 1) & fired.gt_H.round(6).isin(cfs) & (fired.n_above == 0)).sum()),
            "gt_in_tied_top": int(((fired.top_block > 1) & (fired.n_above == 0)).sum()),
        })
    out["evidence_ties"] = pd.DataFrame(rows)

    # ---- do propagated scores order tied services better than chance? ---------
    rows = []
    tests = {"inferred forward raw": ("inferred", "forward", "raw", "none", "probsum"),
             "inferred forward normalised": ("inferred", "forward", "rownorm", "none", "probsum"),
             "inferred reversed normalised": ("inferred", "reversed", "rownorm", "none", "probsum"),
             "callgraph forward unit": ("callgraph", "forward", "unit", "none", "probsum"),
             "callgraph reversed unit": ("callgraph", "reversed", "unit", "none", "probsum")}
    for system in SYSTEMS:
        for name, cfg in tests.items():
            for delta in (0.001, 0.3, 0.85):
                c = pick(system, *cfg, delta)
                if len(c) != 125:
                    continue
                t = c[(c.local_block > 1) & c.any_fired]        # ties at a non-zero H only
                if t.empty:
                    continue
                gain = t.p_first_in_local_block - 1.0 / t.local_block
                d, lo, hi, p = boot(gain, t.scenario)
                rows.append({"system": system, "configuration": name, "delta": delta, "tied_cases": len(t),
                             "chance": (1.0 / t.local_block).mean(), "p_first": t.p_first_in_local_block.mean(),
                             "gain_over_chance": d, "gain_lo": lo, "gain_hi": hi, "p": p})
    out["tie_order"] = pd.DataFrame(rows)

    # ---- baselines --------------------------------------------------------------
    rl = pd.read_csv(RESULTS / "rule_learning_per_case.csv")
    rl = rl[rl.protocol == "loso"]
    rows = []
    for system, suffix in zip(SYSTEMS, ("", "_re1-ss", "_re1-tt")):
        loc = local[system]

        def line(name, a1, e1=None, a3=None, a5=None, mrr=None):
            d, lo, hi, p = boot(a1.reindex(loc.index) - loc.p1, loc.scenario)
            rows.append({"system": system, "method": name, "ac1": a1.mean(),
                         "ac1_expected": np.nan if e1 is None else e1.mean(),
                         "ac3": np.nan if a3 is None else a3.mean(), "ac5": np.nan if a5 is None else a5.mean(),
                         "mrr": np.nan if mrr is None else mrr.mean(),
                         "ac1_diff_vs_local": d, "diff_lo": lo, "diff_hi": hi})
        for name in ("local", "shipped", "normalised", "capped", "callgraph_reversed"):
            c = key(system, name)
            if c is not None:
                line(f"FCP {name}", c.p1, c.e1, c.p3, c.p5, c.rr)
        for variant, label in (("anomaly_max_rawz", "largest |z|, unbounded"), ("anomaly_max", "largest |z|, clipped at 10")):
            v = rl[(rl.system == system) & (rl.variant == variant)].set_index("case_id")
            line(label, v.ac1, v.ac1_expected, v.ac3, None, v.rr)
        for m, label in (("baro", "BARO"), ("causalrca", "CausalRCA"), ("microrca", "MicroRCA"),
                         ("monitorrank", "MonitorRank"), ("yrca", "yRCA"), ("dejavu", "DejaVu (supervised)")):
            b = pd.read_csv(RESULTS / f"week2_{m}_validation{suffix}.csv").set_index("case_id")
            line(f"{label} (re-implemented)", b["AC@1"], None, b["AC@3"], b["AC@5"], b["MRR"])
    out["baselines"] = pd.DataFrame(rows)

    # ---- explanations -------------------------------------------------------------
    rows = []
    for system in SYSTEMS:
        for name in KEY:
            c = key(system, name)
            if c is None:
                continue
            explained = c.top1_type.map(PROTOTYPE_TO_FAULT)
            match = (explained == c.fault)
            typeable = c.fault.isin(TYPEABLE)
            row = {"system": system, "configuration": name,
                   "type_match_all": match.mean(), "type_match_typeable_faults": match[typeable].mean(),
                   "type_match_when_top1_correct": match[c["rank"] == 1].mean() if (c["rank"] == 1).any() else np.nan,
                   "top1_fallback_share": c.top1_fallback.mean(),
                   "top1_no_type_share": (c.top1_type == "none").mean()}
            if c.sc.notna().all():
                fb = c.top1_fallback | (c.top1_type == "none")
                row.update({"sc": c.sc.mean(), "ec": c.ec.mean(), "sg": c.sg.mean(),
                            "sc_rule_typed": c.sc[~fb].mean(), "sc_fallback": c.sc[fb].mean() if fb.any() else np.nan,
                            "ec_rule_typed": c.ec[~fb].mean(), "ec_fallback": c.ec[fb].mean() if fb.any() else np.nan})
            rows.append(row)
    out["explanations"] = pd.DataFrame(rows)

    args.out.mkdir(parents=True, exist_ok=True)
    for name, table in out.items():
        table.round(4).to_csv(args.out / f"kes_{name}.csv", index=False)
    with pd.option_context("display.width", 240, "display.max_columns", 40, "display.max_rows", 400):
        for name in ("operators", "budget_vs_damping", "loso", "failures", "evidence_ties", "tie_order",
                     "baselines", "explanations"):
            print(f"\n===== {name}"); print(out[name].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
