"""RE1-TT failure-mechanism instrumentation and the Section 5.7 ceiling derivation.

Durable regeneration of the per-case measurement behind Section 5.6's mechanism
split and Section 5.7's rescue ceiling. Original output lived in a session
scratchpad and was lost; see paper/notes/provenance_audit_2026-08.md.

Emits results/tt_mechanism_instrumentation.csv with, per case: the propagated
confidence of the top block, the block's composition, the ground truth's local
Mamdani confidence H, the mechanism class, and the strict/loose rescue tests.

Deterministic; no RNG on this path.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods._onset import detect_onset
from evaluation.methods.foda_fcp import (
    FodaFCPMethod, _fuzzify_service, _infer_hypothesis, _infer_topology,
    _has_cycle, _propagate_iterative, _propagate_damped, _rank,
)
from evaluation.metrics import accuracy_at_k


def classify(ac1: float, block_size: int, c_max: float) -> str:
    if ac1 == 1.0:
        return "correct"
    if block_size > 1 and c_max >= 0.99:
        return "saturation"
    if block_size > 1 and c_max <= 0.01:
        return "system_silence"
    return "residual"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RE1-TT system directory")
    ap.add_argument("--out", type=Path, default=Path("results/tt_mechanism_instrumentation.csv"))
    args = ap.parse_args()

    method = FodaFCPMethod()
    rows = []
    for case in RCAEvalLoader(args.data.expanduser()).iter_cases():
        norm = normalize_case(case, window_seconds=method.window_seconds)
        onset = detect_onset(norm.case_window, norm.services)
        fuzzy = {s: _fuzzify_service(norm.case_window, s, onset) for s in norm.services}
        hyp = {s: _infer_hypothesis(v) for s, v in fuzzy.items()}
        edges = _infer_topology(
            case_window=norm.case_window, services=norm.services, hypotheses=hyp,
            onset_time=onset, threshold=method.topology_threshold, lag=method.lag,
        )
        if _has_cycle(norm.services, edges):
            C = _propagate_iterative(hypotheses=hyp, services=norm.services, edges=edges,
                                     delta=method.damping_factor, max_iter=method.max_iterations)
        else:
            C = _propagate_damped(hypotheses=hyp, services=norm.services, edges=edges,
                                  delta=method.damping_factor)
        ranked = _rank(C, hyp, norm.services)
        gt = case.ground_truth_root_cause
        H = {s: (hyp[s].local_confidence if s in hyp else 0.0) for s in norm.services}
        ac1 = 1.0 if accuracy_at_k(ranked, gt, 1) else 0.0
        c_max = ranked[0][1]
        block = [s for s, c in ranked if abs(c - c_max) < 1e-12]
        gt_in_block = gt in block
        if gt_in_block:
            others = [H[s] for s in block if s != gt]
            strict = (not others) or (H[gt] > max(others))
            loose = (not others) or (H[gt] >= max(others))
            h_ties = sum(1 for s in block if s != gt and abs(H[s] - H[gt]) < 1e-12)
        else:
            strict = loose = False
            h_ties = 0
        rows.append({
            "case_id": case.id, "fault": case.ground_truth_fault_type,
            "ground_truth": gt, "top1": ranked[0][0], "ac1": ac1,
            "c_max": c_max, "block_size": len(block),
            "gt_in_block": int(gt_in_block), "gt_H": H.get(gt, float("nan")),
            "block_H_max": max((H[s] for s in block), default=float("nan")),
            "strict_rescue": int(strict and ac1 == 0.0),
            "loose_rescue": int(loose and ac1 == 0.0),
            "n_H_ties_with_gt": h_ties,
            "mechanism": classify(ac1, len(block), c_max),
        })

    df = pd.DataFrame(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)

    fails = df[df.ac1 == 0.0]
    print(f"cases={len(df)}  AC@1={df.ac1.mean():.4f}  failures={len(fails)}")
    print("mechanism split:", df[df.ac1 == 0.0].mechanism.value_counts().to_dict())
    print(f"distinct top-1 among failures: {fails.top1.nunique()}"
          f"  most-frequent share: {fails.top1.value_counts().iloc[0]/len(fails):.3f}")
    sat = df[(df.ac1 == 0.0) & (df.mechanism == "saturation")]
    print(f"saturation: n={len(sat)} gt_in_block={int(sat.gt_in_block.sum())} "
          f"loose={int(sat.loose_rescue.sum())} strict={int(sat.strict_rescue.sum())} "
          f"lost_to_H_ties={int(sat.loose_rescue.sum()-sat.strict_rescue.sum())}")
    print(f"gt_H median on saturation failures: {sat.gt_H.median():.3f}")
    base = int(df.ac1.sum()); n_strict = int(df[df.ac1 == 0.0].strict_rescue.sum())
    print(f"CEILING = ({base}+{n_strict})/{len(df)} = {(base+n_strict)/len(df):.4f}")
    print(f"system-silence per fault: {df[df.mechanism=='system_silence'].groupby('fault').size().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
