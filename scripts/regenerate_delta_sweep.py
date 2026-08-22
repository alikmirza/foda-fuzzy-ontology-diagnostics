"""Extended damping (delta) sweep — durable regeneration for Section 5.9.

Recreates the dose-response measurement whose original CSVs were written to a
session-local scratchpad and lost (see paper/notes/provenance_audit_2026-08.md).

Grid: 11 delta values x 3 RCAEval systems x 125 cases, FODA-FCP only.
Per (delta, case) it records:
  ac1_shipped  -- pessimistic AC@1 over C-tie blocks (the canonical convention)
  ac1_refined  -- pessimistic AC@1 over (C,H)-tie blocks (Section 5.7's eps->0
                  lexicographic refinement)
  sg, sc, ec   -- crisp semantic metrics on the emitted explanation
delta=0.001 stands for the delta->0 limit (local-Mamdani-only ranking).

Deterministic: no RNG anywhere in this path. Re-running reproduces byte-identical
output for a given commit.

Usage:
    PYTHONPATH=. python3 scripts/regenerate_delta_sweep.py \
        --data ~/research/rcaeval-tools/RCAEval/data/RE1 --out results
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
    _has_cycle, _propagate_iterative, _propagate_damped, _rank, _build_explanation,
)
from evaluation.metrics import (
    SemanticGroundedness, SemanticCoherence, ExplanationCompleteness,
    OntologyAdapter, accuracy_at_k,
)

DELTAS = (0.001, 0.1, 0.2, 0.3, 0.4, 0.5, 0.65, 0.75, 0.85, 0.95, 1.0)
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))


def _refined_hit(services, C, H, gt) -> float:
    """Pessimistic AC@1 over (C, H)-tie blocks: the ground truth scores only
    when it is the unique maximum of the lexicographic key."""
    keyed = sorted(
        ((s, (round(C.get(s, 0.0), 12), round(H.get(s, 0.0), 12))) for s in services),
        key=lambda kv: (-kv[1][0], -kv[1][1]),
    )
    best = keyed[0][1]
    block = [s for s, k in keyed if k == best]
    return 1.0 if block == [gt] else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True, help="RCAEval RE1 data root")
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    method = FodaFCPMethod()
    ont = OntologyAdapter()
    sg, sc, ec = SemanticGroundedness(), SemanticCoherence(), ExplanationCompleteness()

    for sysdir, tag in SYSTEMS:
        # Phase 1 -- fuzzify / infer / build topology once per case; these do not
        # depend on delta, so the sweep only repeats propagation and scoring.
        prepared = []
        for case in RCAEvalLoader(args.data.expanduser() / sysdir).iter_cases():
            norm = normalize_case(case, window_seconds=method.window_seconds)
            onset = detect_onset(norm.case_window, norm.services)
            fuzzy = {s: _fuzzify_service(norm.case_window, s, onset) for s in norm.services}
            hyp = {s: _infer_hypothesis(v) for s, v in fuzzy.items()}
            edges = _infer_topology(
                case_window=norm.case_window, services=norm.services, hypotheses=hyp,
                onset_time=onset, threshold=method.topology_threshold, lag=method.lag,
            )
            prepared.append((case, norm, fuzzy, hyp, edges, _has_cycle(norm.services, edges)))

        rows = []
        for delta in DELTAS:
            for case, norm, fuzzy, hyp, edges, cyclic in prepared:
                if cyclic:
                    C = _propagate_iterative(
                        hypotheses=hyp, services=norm.services, edges=edges,
                        delta=delta, max_iter=method.max_iterations,
                    )
                else:
                    C = _propagate_damped(
                        hypotheses=hyp, services=norm.services, edges=edges, delta=delta,
                    )
                ranked = _rank(C, hyp, norm.services)
                gt = case.ground_truth_root_cause
                H = {s: (hyp[s].local_confidence if s in hyp else 0.0) for s in norm.services}
                expl = _build_explanation(
                    services_ranked=ranked, hypotheses=hyp, fuzzy_vectors=fuzzy,
                    edges=edges, delta=delta, top_k=method.top_k,
                )
                rows.append({
                    "system": tag,
                    "delta": delta,
                    "case_id": case.id,
                    "fault": case.ground_truth_fault_type,
                    "ac1_shipped": 1.0 if accuracy_at_k(ranked, gt, 1) else 0.0,
                    "ac1_refined": _refined_hit(norm.services, C, H, gt),
                    "sg": sg.score(expl, ont),
                    "sc": sc.score(expl, ont),
                    "ec": ec.score(expl, ont, case_services=norm.services),
                })
            print(f"[{tag}] delta={delta} done", flush=True)

        df = pd.DataFrame(rows)
        per_case = args.out / f"delta_sweep_per_case_{tag}.csv"
        df.to_csv(per_case, index=False)
        agg = (df.groupby("delta")[["ac1_shipped", "ac1_refined", "sg", "sc", "ec"]]
                 .mean().round(6).reset_index())
        agg.insert(0, "system", tag)
        agg.to_csv(args.out / f"delta_sweep_summary_{tag}.csv", index=False)
        print(f"\n=== {tag} ===\n{agg.round(4).to_string(index=False)}\n", flush=True)

    print("DELTA SWEEP REGENERATION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
