"""Per-case audit of FODA-FCP at the shipped configuration (delta = 0.85).

Re-runs the deterministic FODA-FCP pipeline on all 375 RE1 cases and records,
per case, three things the headline tables do not show.

1. Tie conventions for AC@1. The canonical score is pessimistic: the ground
   truth scores only if it is alone at the top. Also recorded: optimistic
   (it shares the top score) and expected (1 / size of the top tie block when
   it shares the top score, i.e. AC@1 under uniformly random tie-breaking).
   Ties are exact score equality, the same rule as
   evaluation.metrics.ranking_metrics.

2. Fault-type agreement with the injected fault. RCAEval injects cpu, mem,
   disk, delay and loss. MAPPING_STRICT names the one DiagnosticKB prototype
   that matches each fault; MAPPING_LENIENT also accepts prototypes that
   plausibly describe the same symptom. Both mappings are a judgement and are
   stated here so they can be reviewed. Recorded types:
     top1_type      class of the first emitted atom (fallback included)
     gt_rule_type   prototype the rule base assigns to the true root cause,
                    whatever its rank (None when no rule fires there)
     gt_any_type    the same, with the fuzzy-term fallback applied
   DejaVu's predicted fault type (results/week2_dejavu_validation*.csv) is
   summarised alongside as the one baseline that predicts a type.

3. The fuzzy-term fallback (DEVIATIONS.md, FODA-FCP Deviation 5): how many
   head atoms take their class from it, and SG/SC/EC with it switched off
   (atoms with no fired rule then carry the abstract ContributingFactor class).

Cross-checks, each fatal on mismatch: pessimistic AC@1 equals the week2
FODA-FCP file and the delta-sweep file at delta = 0.85, and the shipped SG, SC
and EC equal the delta-sweep values.

Deterministic: no RNG. Re-running reproduces byte-identical output for a given
commit.

Usage:
    PYTHONPATH=. python3 scripts/regenerate_fcp_case_audit.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import evaluation.methods.foda_fcp as fcp
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.metrics import (
    SemanticGroundedness, SemanticCoherence, ExplanationCompleteness,
    OntologyAdapter, accuracy_at_k,
)

RESULTS = Path(__file__).resolve().parent.parent / "results"
SYSTEMS = (("RE1-OB", "re1-ob", ""), ("RE1-SS", "re1-ss", "_re1-ss"), ("RE1-TT", "re1-tt", "_re1-tt"))

MAPPING_STRICT = {
    "cpu": {"CpuSaturation"},
    "mem": {"MemoryLeak"},
    "disk": {"DiskIoBottleneck"},
    "delay": {"LatencySpike"},
    "loss": {"NetworkCongestion"},
}
MAPPING_LENIENT = {
    "cpu": {"CpuSaturation", "ResourceContention"},
    "mem": {"MemoryLeak", "ResourceContention"},
    "disk": {"DiskIoBottleneck", "ResourceContention"},
    "delay": {"LatencySpike", "NetworkCongestion"},
    "loss": {"NetworkCongestion", "HighErrorRate", "LatencySpike"},
}
RULE_REACHABLE = set(fcp.CATEGORY_TO_FAULT.values())


def local(uri: str | None) -> str | None:
    return uri.rsplit("#", 1)[-1] if uri else None


def match(mapping: dict, fault: str, proto: str | None) -> bool:
    return proto is not None and proto in mapping[fault]


def audit_case(tag: str, case, method, ont, metrics) -> dict:
    sg, sc, ec = metrics
    norm = normalize_case(case, window_seconds=method.window_seconds)
    services, gt, fault = norm.services, case.ground_truth_root_cause, case.ground_truth_fault_type
    onset = detect_onset(norm.case_window, services)
    fuzzy = {s: fcp._fuzzify_service(norm.case_window, s, onset) for s in services}
    hyp = {s: fcp._infer_hypothesis(v) for s, v in fuzzy.items()}
    edges = fcp._infer_topology(
        case_window=norm.case_window, services=services, hypotheses=hyp,
        onset_time=onset, threshold=method.topology_threshold, lag=method.lag,
    )
    if fcp._has_cycle(services, edges):
        C = fcp._propagate_iterative(hypotheses=hyp, services=services, edges=edges,
                                     delta=method.damping_factor, max_iter=method.max_iterations)
    else:
        C = fcp._propagate_damped(hypotheses=hyp, services=services, edges=edges,
                                  delta=method.damping_factor)
    ranked = fcp._rank(C, hyp, services)

    top_score = ranked[0][1]
    block = [s for s, c in ranked if c == top_score]
    pessimistic = 1.0 if accuracy_at_k(ranked, gt, 1) else 0.0
    assert pessimistic == (1.0 if block == [gt] else 0.0), case.id

    def explain():
        return fcp._build_explanation(services_ranked=ranked, hypotheses=hyp, fuzzy_vectors=fuzzy,
                                      edges=edges, delta=method.damping_factor, top_k=method.top_k)

    expl = explain()
    head = ranked[: method.top_k]
    fallback_atoms = sum(
        1 for s, _ in head
        if fcp.CATEGORY_TO_FAULT.get(hyp[s].dominant_category) is None
        and fcp._infer_fault_prototype_from_fuzzy(fuzzy[s]) is not None
    )
    original = fcp._infer_fault_prototype_from_fuzzy
    fcp._infer_fault_prototype_from_fuzzy = lambda fv: None
    try:
        expl_nofb = explain()
    finally:
        fcp._infer_fault_prototype_from_fuzzy = original

    atoms = list(expl.atoms())
    top1_type = local(atoms[0].ontology_class) if atoms else None
    gt_rule = fcp.CATEGORY_TO_FAULT.get(hyp[gt].dominant_category) if gt in hyp else None
    gt_any = gt_rule or (fcp._infer_fault_prototype_from_fuzzy(fuzzy[gt]) if gt in fuzzy else None)
    return {
        "system": tag, "case_id": case.id, "fault": fault, "ground_truth": gt,
        "top1": ranked[0][0], "top_block_size": len(block),
        "ac1_pessimistic": pessimistic,
        "ac1_optimistic": 1.0 if gt in block else 0.0,
        "ac1_expected": round(1.0 / len(block), 6) if gt in block else 0.0,
        "top1_type": top1_type, "gt_rule_type": gt_rule, "gt_any_type": gt_any,
        "fault_rule_reachable": bool(MAPPING_STRICT[fault] & RULE_REACHABLE),
        "top1_type_strict": match(MAPPING_STRICT, fault, top1_type),
        "top1_type_lenient": match(MAPPING_LENIENT, fault, top1_type),
        "gt_rule_type_strict": match(MAPPING_STRICT, fault, gt_rule),
        "gt_rule_type_lenient": match(MAPPING_LENIENT, fault, gt_rule),
        "gt_any_type_strict": match(MAPPING_STRICT, fault, gt_any),
        "gt_any_type_lenient": match(MAPPING_LENIENT, fault, gt_any),
        "head_fallback_atoms": fallback_atoms,
        "root_fallback": fallback_atoms > 0 and fcp.CATEGORY_TO_FAULT.get(hyp[head[0][0]].dominant_category) is None,
        "sg": sg.score(expl, ont), "sc": sc.score(expl, ont),
        "ec": ec.score(expl, ont, case_services=services),
        "sg_no_fallback": sg.score(expl_nofb, ont), "sc_no_fallback": sc.score(expl_nofb, ont),
        "ec_no_fallback": ec.score(expl_nofb, ont, case_services=services),
    }


def cross_check(df: pd.DataFrame, tag: str, suffix: str) -> None:
    week2 = pd.read_csv(RESULTS / f"week2_foda_fcp_validation{suffix}.csv").set_index("case_id")["AC@1"]
    sweep = pd.read_csv(RESULTS / f"delta_sweep_per_case_{tag}.csv")
    sweep = sweep[sweep["delta"] == 0.85].set_index("case_id")
    d = df.set_index("case_id")
    assert d["ac1_pessimistic"].equals(week2.reindex(d.index).astype(float)), f"{tag}: AC@1 != week2"
    assert d["ac1_pessimistic"].equals(sweep["ac1_shipped"].reindex(d.index)), f"{tag}: AC@1 != sweep"
    for col in ("sg", "sc", "ec"):
        gap = (d[col] - sweep[col].reindex(d.index)).abs().max()
        assert gap < 1e-9, f"{tag}: {col} differs from sweep by {gap}"


def summarise(df: pd.DataFrame, suffix_by_tag: dict) -> pd.DataFrame:
    rows = []
    for tag, g in df.groupby("system", sort=False):
        dv = pd.read_csv(RESULTS / f"week2_dejavu_validation{suffix_by_tag[tag]}.csv")
        rows.append({
            "system": tag, "n_cases": len(g),
            "ac1_pessimistic": g["ac1_pessimistic"].mean(),
            "ac1_expected": g["ac1_expected"].mean(),
            "ac1_optimistic": g["ac1_optimistic"].mean(),
            "median_top_block_size": g["top_block_size"].median(),
            "cases_fault_rule_reachable": int(g["fault_rule_reachable"].sum()),
            "top1_type_strict": g["top1_type_strict"].mean(),
            "top1_type_lenient": g["top1_type_lenient"].mean(),
            "gt_rule_type_strict": g["gt_rule_type_strict"].mean(),
            "gt_rule_type_lenient": g["gt_rule_type_lenient"].mean(),
            "gt_any_type_strict": g["gt_any_type_strict"].mean(),
            "gt_any_type_lenient": g["gt_any_type_lenient"].mean(),
            "dejavu_type_accuracy": (dv["predicted_fault_type"] == dv["fault"]).mean(),
            "cases_with_fallback_atom": int((g["head_fallback_atoms"] > 0).sum()),
            "cases_root_fallback": int(g["root_fallback"].sum()),
            "sg": g["sg"].mean(), "sg_no_fallback": g["sg_no_fallback"].mean(),
            "sc": g["sc"].mean(), "sc_no_fallback": g["sc_no_fallback"].mean(),
            "ec": g["ec"].mean(), "ec_no_fallback": g["ec_no_fallback"].mean(),
        })
    return pd.DataFrame(rows).round(6)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RCAEval RE1 data root")
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    method, ont = fcp.FodaFCPMethod(), OntologyAdapter()
    metrics = (SemanticGroundedness(), SemanticCoherence(), ExplanationCompleteness())
    frames = []
    for sysdir, tag, suffix in SYSTEMS:
        rows = [audit_case(tag, case, method, ont, metrics)
                for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases()]
        df = pd.DataFrame(rows)
        cross_check(df, tag, suffix)
        frames.append(df)
        print(f"[{tag}] done, cross-checks passed", flush=True)

    per_case = pd.concat(frames, ignore_index=True)
    per_case.to_csv(args.out / "fcp_case_audit_per_case.csv", index=False)
    summary = summarise(per_case, {tag: suffix for _, tag, suffix in SYSTEMS})
    summary.to_csv(args.out / "fcp_case_audit_summary.csv", index=False)
    print(summary.T.to_string(header=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
