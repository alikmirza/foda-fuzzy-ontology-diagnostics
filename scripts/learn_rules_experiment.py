"""Crisp, learned and fuzzy rule bases for local evidence: a controlled comparison.

The expert rule base (16 Mamdani rules) is silent on 25-37 % of RCAEval cases and
types most CPU, memory and disk faults as resource contention. This experiment
asks whether small rules learned from labelled cases do better, and what each
step from crisp to fuzzy adds. All variants see the same inputs: the five signed
post-vs-baseline z-scores per service (cpu, mem, latency, error, traffic) that
the shipped fuzzifier computes. Services are ranked by local evidence only
(C = H, no propagation), which the propagation study showed loses nothing.

Features for the learned rules are the z-scores clipped to [-CLIP, CLIP] with
CLIP = 10. A column that is constant before the onset has a baseline spread of
rounding residue, which gives z-scores of 1e3 to 1e15 whose size is meaningless
and platform-dependent; without the clip, trees split on those values. The
unclipped variants (suffix _rawz) are reported as a sensitivity check only.

Rule bases
  anomaly_max    no rules: rank by the largest clipped |z| over the five
                 features. The reference any rule base has to beat.
  expert_fuzzy   the shipped rule base (graded memberships, min, CF, max)
  expert_crisp   the same 16 rules with every term cut at membership 0.5:
                 a rule fires fully or not at all
  tree_crisp     one decision tree, depth <= 3 (rules of at most 3 conditions),
                 classes {none, cpu, mem, disk, delay, loss}; a leaf is a rule
                 whose certainty factor is 1 - P(none | leaf)
  tree_fuzzy     the same tree with each threshold "z <= t" replaced by a linear
                 ramp of half-width TAU around t; a rule's strength is the
                 minimum membership on its path and H = max over rules of
                 CF * strength (Mamdani style)
  forest_crisp   50 trees of depth <= 2 (rules of at most 2 conditions),
                 H = mean over trees
  forest_fuzzy   the same forest with ramps

Depths, forest size, minimum leaf size and TAU = 0.5 were fixed before any result
was seen; TAU in {0.25, 1.0} is reported as a sensitivity check only.

Protocols (no case is ever scored by rules that saw it)
  loso     learn on two systems, test on the third
  within   per system, 5-fold cross-validation grouped by fault scenario
           (root-cause service x fault type), so the five repetitions of a
           scenario stay together: about 100 labelled cases to learn from
  within_service
           per system, leave-one-root-service-out: every case whose root cause
           is the held-out service is scored by rules that never saw that
           service as a root cause. Each system injects faults into only five
           services, so "within" can learn those services' signatures; this
           protocol cannot.

Per case: AC@1 with pessimistic ties, expected AC@1 under random tie-breaking,
AC@3, reciprocal rank, size of the top tie block, whether the rule base is
silent (every service scores the same), and whether the fault type assigned to
the true root cause matches the injected fault (strict mapping, as in
scripts/regenerate_fcp_case_audit.py).

Cross-check, fatal on mismatch: expert_fuzzy must reproduce the "local" row of
results/propagation_variants_per_case.csv.gz case by case.

Also written: paired exact McNemar tests between rule bases
(rule_learning_tests.csv) and, for the unclipped anomaly_max reference, its
case-by-case agreement with the re-implemented baselines' AC@1
(rule_learning_baseline_agreement.csv).

Deterministic: fixed random_state everywhere.

Usage:
    PYTHONPATH=. python3 scripts/learn_rules_experiment.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from scripts.regenerate_ranking_statistics import mcnemar_exact
from scripts.run_propagation_variants import prepare

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
FEATURES = ("cpu", "mem", "latency", "error", "traffic")
CLASSES = ("none", "cpu", "mem", "disk", "delay", "loss")
TAU, TAU_SENSITIVITY, CLIP = 0.5, (0.25, 1.0), 10.0
TREE_DEPTH, FOREST_DEPTH, FOREST_SIZE, MIN_LEAF, SEED = 3, 2, 50, 5, 0
PROTOTYPE_TO_FAULT = {"CpuSaturation": "cpu", "MemoryLeak": "mem", "DiskIoBottleneck": "disk",
                      "LatencySpike": "delay", "NetworkCongestion": "loss"}
CRISP_CUT = 0.5


# ---- dataset ---------------------------------------------------------------

def build_dataset(data: Path) -> pd.DataFrame:
    method, rows = fcp.FodaFCPMethod(), []
    for sysdir, tag in SYSTEMS:
        for case in RCAEvalLoader(data / sysdir).iter_cases():
            norm, _onset, fuzzy, hyp = prepare(case, method)
            gt, fault = case.ground_truth_root_cause, case.ground_truth_fault_type
            for s in norm.services:
                crisp_fv = fcp._ServiceFuzzyVector(
                    service=s, z_signed=fuzzy[s].z_signed,
                    memberships={k: (1.0 if v >= CRISP_CUT else 0.0) for k, v in fuzzy[s].memberships.items()})
                crisp = fcp._infer_hypothesis(crisp_fv)
                row = {"system": tag, "case_id": case.id, "service": s, "fault": fault,
                       "is_root": s == gt, "scenario": f"{gt}_{fault}", "root": gt,
                       "expert_fuzzy": hyp[s].local_confidence,
                       "expert_fuzzy_type": PROTOTYPE_TO_FAULT.get(
                           fcp.CATEGORY_TO_FAULT.get(hyp[s].dominant_category), "other"
                       ) if hyp[s].local_confidence > 0 else "none",
                       "expert_crisp": crisp.local_confidence,
                       "expert_crisp_type": PROTOTYPE_TO_FAULT.get(
                           fcp.CATEGORY_TO_FAULT.get(crisp.dominant_category), "other"
                       ) if crisp.local_confidence > 0 else "none"}
                row.update({f"z_{f}": fuzzy[s].z_signed[f] for f in FEATURES})
                row.update({f"zc_{f}": float(np.clip(fuzzy[s].z_signed[f], -CLIP, CLIP)) for f in FEATURES})
                rows.append(row)
        print(f"[{tag}] features extracted", flush=True)
    df = pd.DataFrame(rows)
    df["label"] = np.where(df["is_root"], df["fault"], "none")
    df["anomaly_max"] = df[[f"zc_{f}" for f in FEATURES]].abs().max(axis=1)
    df["anomaly_max_rawz"] = df[[f"z_{f}" for f in FEATURES]].abs().max(axis=1)
    df["anomaly_max_type"] = df["anomaly_max_rawz_type"] = "none"
    return df


# ---- learned rule bases ----------------------------------------------------

def leaf_rules(tree, classes=None) -> list[dict]:
    """Every leaf as a rule: path conditions, certainty factor, fault type.
    A forest's sub-trees index classes by number, so the forest passes the names."""
    t, classes, rules = tree.tree_, list(tree.classes_ if classes is None else classes), []
    none_ix = classes.index("none")

    def walk(node, path):
        if t.children_left[node] == -1:
            dist = t.value[node][0] / t.value[node][0].sum()
            fault_ix = [i for i in range(len(classes)) if i != none_ix]
            best = max(fault_ix, key=lambda i: dist[i])
            rules.append({"path": path, "cf": 1.0 - dist[none_ix],
                          "type": classes[best] if dist[best] > 0 else "none"})
            return
        f, thr = t.feature[node], t.threshold[node]
        walk(t.children_left[node], path + [(f, thr, True)])
        walk(t.children_right[node], path + [(f, thr, False)])

    walk(0, [])
    return rules


def fire(rules: list[dict], X: np.ndarray, tau: float):
    """H and fault type per row: max over rules of CF * min(path memberships)."""
    best = np.full(len(X), -1.0)
    kind = np.empty(len(X), dtype=object)
    for r in rules:
        strength = np.ones(len(X))
        for f, thr, left in r["path"]:
            if tau == 0.0:
                m = (X[:, f] <= thr).astype(float)
            else:
                m = np.clip((thr + tau - X[:, f]) / (2.0 * tau), 0.0, 1.0)
            strength = np.minimum(strength, m if left else 1.0 - m)
        score = r["cf"] * strength
        better = score > best
        best[better], kind[better] = score[better], r["type"]
    return best, kind


def fit_predict(train: pd.DataFrame, test: pd.DataFrame, taus=(0.0, TAU) + TAU_SENSITIVITY, prefix="zc", suffix=""):
    Xtr, ytr = train[[f"{prefix}_{f}" for f in FEATURES]].to_numpy(), train["label"].to_numpy()
    Xte = test[[f"{prefix}_{f}" for f in FEATURES]].to_numpy()
    tree = DecisionTreeClassifier(max_depth=TREE_DEPTH, min_samples_leaf=MIN_LEAF,
                                  class_weight="balanced", random_state=SEED).fit(Xtr, ytr)
    forest = RandomForestClassifier(n_estimators=FOREST_SIZE, max_depth=FOREST_DEPTH, min_samples_leaf=MIN_LEAF,
                                    class_weight="balanced_subsample", random_state=SEED).fit(Xtr, ytr)
    out, tree_rules = {}, leaf_rules(tree)
    forest_rules = [leaf_rules(est, forest.classes_) for est in forest.estimators_]
    for tau in taus:
        name = {0.0: "crisp", TAU: "fuzzy"}.get(tau, f"fuzzy_tau{tau}") + suffix
        h, k = fire(tree_rules, Xte, tau)
        out[f"tree_{name}"], out[f"tree_{name}_type"] = h, k
        hs = np.zeros(len(Xte)); votes = [dict() for _ in range(len(Xte))]
        for rules in forest_rules:
            h, k = fire(rules, Xte, tau)
            hs += h
            for i, (hi, ki) in enumerate(zip(h, k)):
                votes[i][ki] = votes[i].get(ki, 0.0) + hi
        out[f"forest_{name}"] = hs / len(forest_rules)
        out[f"forest_{name}_type"] = np.array([max(v, key=v.get) if v else "none" for v in votes], dtype=object)
    text = export_text(tree, feature_names=[f"{prefix}_{f}" for f in FEATURES], decimals=2)
    n_rules = sum(1 for r in tree_rules if r["cf"] >= 0.5)
    return out, text, len(tree_rules), n_rules


# ---- scoring ---------------------------------------------------------------

def score_cases(df: pd.DataFrame, variant: str) -> pd.DataFrame:
    rows = []
    for (system, case_id), g in df.groupby(["system", "case_id"], sort=False):
        g = g.sort_values([variant, "service"], ascending=[False, True])
        scores, services = g[variant].to_numpy(), g["service"].tolist()
        gt_pos = int(np.flatnonzero(g["is_root"].to_numpy())[0])
        gt_score = scores[gt_pos]
        worst = int(np.flatnonzero(scores == gt_score)[-1]) + 1          # pessimistic rank
        block = int((scores == scores[0]).sum())
        in_block = gt_score == scores[0]
        rows.append({"system": system, "case_id": case_id, "fault": g["fault"].iloc[0], "variant": variant,
                     "ac1": float(worst == 1), "ac1_expected": 1.0 / block if in_block else 0.0,
                     "ac3": float(worst <= 3), "rr": 1.0 / worst, "top_block": block,
                     "silent": block == len(services),
                     "gt_type_correct": g[f"{variant}_type"].iloc[gt_pos] == g["fault"].iloc[0]})
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    data = build_dataset(args.data.expanduser())
    data.to_csv(args.out / "rule_learning_dataset.csv.gz", index=False)

    ref = pd.read_csv(RESULTS / "propagation_variants_per_case.csv.gz")
    ref = ref[(ref.operator == "local") & (ref.threshold == 0.5)].set_index("case_id")
    mine = score_cases(data, "expert_fuzzy").set_index("case_id")
    for col in ("ac1", "ac1_expected", "ac3"):
        gap = (mine[col] - ref[col].reindex(mine.index)).abs().max()
        assert gap < 1e-9, f"expert_fuzzy {col} differs from the committed local-evidence results by {gap}"
    print("cross-check against the committed local-evidence results passed", flush=True)

    learned_cols = None
    frames, rule_dump, rule_counts = [], [], []
    for protocol in ("loso", "within", "within_service"):
        parts = []
        for _, tag in SYSTEMS:
            test_sys = data[data.system == tag]
            if protocol == "loso":
                folds = [(data[data.system != tag], test_sys, f"held-out {tag}")]
            else:
                cases = test_sys.drop_duplicates("case_id")
                gkf = GroupKFold(n_splits=5)
                folds = []
                group_col = "scenario" if protocol == "within" else "root"
                for k, (tr, te) in enumerate(gkf.split(cases, groups=cases[group_col])):
                    tr_ids, te_ids = set(cases.iloc[tr].case_id), set(cases.iloc[te].case_id)
                    folds.append((test_sys[test_sys.case_id.isin(tr_ids)], test_sys[test_sys.case_id.isin(te_ids)],
                                  f"{tag} fold {k}"))
            for train, test, label in folds:
                assert not set(train.case_id) & set(test.case_id)
                preds, text, n_leaves, n_rules = fit_predict(train, test)
                raw, _, _, _ = fit_predict(train, test, taus=(0.0,), prefix="z", suffix="_rawz")
                preds.update(raw)
                part = test.copy()
                for k, v in preds.items():
                    part[k] = v
                learned_cols = [k for k in preds if not k.endswith("_type")]
                parts.append(part)
                rule_dump.append(f"=== {protocol}: {label} (train cases: {train.case_id.nunique()}) ===\n{text}")
                rule_counts.append({"protocol": protocol, "fold": label, "leaves": n_leaves, "rules_cf_ge_0.5": n_rules})
        scored_in = pd.concat(parts, ignore_index=True)
        for variant in ["anomaly_max", "anomaly_max_rawz", "expert_fuzzy", "expert_crisp"] + learned_cols:
            s = score_cases(scored_in, variant); s.insert(0, "protocol", protocol); frames.append(s)

    per_case = pd.concat(frames, ignore_index=True)
    per_case.to_csv(args.out / "rule_learning_per_case.csv", index=False)
    summary = (per_case.groupby(["protocol", "system", "variant"], sort=False)
               .agg(ac1=("ac1", "mean"), ac1_expected=("ac1_expected", "mean"), ac3=("ac3", "mean"),
                    mrr=("rr", "mean"), top_block=("top_block", "mean"), silent=("silent", "mean"),
                    gt_type_correct=("gt_type_correct", "mean")).round(4).reset_index())
    summary.to_csv(args.out / "rule_learning_summary.csv", index=False)
    pd.DataFrame(rule_counts).to_csv(args.out / "rule_learning_rule_counts.csv", index=False)
    (args.out / "rule_learning_trees.txt").write_text("\n".join(rule_dump))
    def hits(protocol, system, variant):
        sel = per_case[(per_case.protocol == protocol) & (per_case.system == system) & (per_case.variant == variant)]
        return sel.set_index("case_id")["ac1"].sort_index()

    pairs = [("forest_crisp", "expert_fuzzy"), ("forest_crisp", "anomaly_max_rawz"), ("expert_fuzzy", "expert_crisp"),
             ("forest_crisp", "forest_fuzzy"), ("forest_crisp", "tree_crisp"), ("tree_crisp", "expert_fuzzy")]
    tests = []
    for protocol in ("loso", "within", "within_service"):
        for _, tag in SYSTEMS:
            for a, b in pairs:
                x, y = hits(protocol, tag, a), hits(protocol, tag, b)
                a_only, b_only, p = mcnemar_exact(x.to_numpy(), y.to_numpy())
                tests.append({"protocol": protocol, "system": tag, "a": a, "b": b, "acc_a": round(x.mean(), 4),
                              "acc_b": round(y.mean(), 4), "a_only": a_only, "b_only": b_only, "mcnemar_p": round(p, 6)})
    pd.DataFrame(tests).to_csv(args.out / "rule_learning_tests.csv", index=False)

    agree = []
    for (_, tag), suffix in zip(SYSTEMS, ("", "_re1-ss", "_re1-tt")):
        ref_hits = hits("loso", tag, "anomaly_max_rawz")
        for method in ("microrca", "monitorrank", "causalrca", "baro", "yrca"):
            b = pd.read_csv(RESULTS / f"week2_{method}_validation{suffix}.csv").set_index("case_id")["AC@1"]
            b = b.reindex(ref_hits.index)
            agree.append({"system": tag, "baseline": method, "baseline_ac1": round(b.mean(), 4),
                          "anomaly_max_rawz_ac1": round(ref_hits.mean(), 4),
                          "same_outcome_share": round(float((b == ref_hits).mean()), 4)})
    pd.DataFrame(agree).to_csv(args.out / "rule_learning_baseline_agreement.csv", index=False)

    main_variants = ["anomaly_max", "expert_fuzzy", "expert_crisp", "tree_crisp", "tree_fuzzy", "forest_crisp", "forest_fuzzy"]
    with pd.option_context("display.width", 200):
        print(summary[summary.variant.isin(main_variants)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
