"""Threshold (tau) and calibration-bin (B) sensitivity sweeps for Section 5.9.

Durable regeneration; original output was scratchpad-only and lost. Runs each of
the seven methods once per case (the expensive part), then re-scores the captured
explanations at every tau, and re-bins the captured confidences at every B.

tau in {0.5, 0.6, 0.7, 0.8, 0.9} x SG and EC, all methods, all systems.
B   in {5, 10, 15, 20}          x ECE, all methods, all systems.

Correctness label for ECE is the pessimistic AC@1, matching the canonical
convention. Deterministic apart from DejaVu's fixed-seed training.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import evaluation.experiments.run_phase2_ec as ec_run
import evaluation.metrics.explanation_completeness as ec_mod
from evaluation.metrics import (
    SemanticGroundedness, ExplanationCompleteness, OntologyAdapter,
    accuracy_at_k, compute_ece,
)

TAUS = (0.5, 0.6, 0.7, 0.8, 0.9)
BINS = (5, 10, 15, 20)
SYSTEMS = (("RE1-OB", "re1-ob"), ("RE1-SS", "re1-ss"), ("RE1-TT", "re1-tt"))
CONF_FIELD = {"BARO": "peak_confidence"}


def capture(data_root: Path, sysdir: str):
    """Run the seven-method harness once, intercepting each (method, case) output."""
    captured = []
    original = ec_run._score_row

    def spy(label, case, norm, out, *a, **k):
        captured.append((label, case, norm, out))
        return original(label, case, norm, out, *a, **k)

    ec_run._score_row = spy
    try:
        ec_run.evaluate(data_root / sysdir)
    finally:
        ec_run._score_row = original
    return captured


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ont = OntologyAdapter()

    tau_rows, bin_rows = [], []
    for sysdir, tag in SYSTEMS:
        cap = capture(args.data.expanduser(), sysdir)
        print(f"[{tag}] captured {len(cap)} (method, case) outputs", flush=True)

        for tau in TAUS:
            sg = SemanticGroundedness(fuzzy_threshold=tau)
            ec_mod._text_matches_any_label.__defaults__ = (tau,)
            ecm = ExplanationCompleteness()
            for label, case, norm, out in cap:
                tau_rows.append({
                    "system": tag, "tau": tau, "method": label, "case_id": case.id,
                    "sg": sg.score(out.explanation_chain, ont),
                    "ec": ecm.score(out.explanation_chain, ont, case_services=norm.services),
                })
            print(f"[{tag}] tau={tau} done", flush=True)
        ec_mod._text_matches_any_label.__defaults__ = (ec_mod._TEXT_MATCH_THRESHOLD,)

        per_method: dict[str, list] = {}
        for label, case, norm, out in cap:
            conf = float(getattr(out, CONF_FIELD.get(label, "confidence")))
            correct = 1.0 if accuracy_at_k(out.ranked_list, case.ground_truth_root_cause, 1) else 0.0
            per_method.setdefault(label, []).append({"confidence": conf, "correct": correct})
        for label, pairs in per_method.items():
            for b in BINS:
                bin_rows.append({"system": tag, "method": label, "n_bins": b,
                                 "ece": compute_ece(pairs, n_bins=b)})
        print(f"[{tag}] bin sweep done", flush=True)

    tau_df = pd.DataFrame(tau_rows)
    tau_df.to_csv(args.out / "ablation_tau_per_case.csv", index=False)
    tau_agg = (tau_df.groupby(["system", "tau", "method"])[["sg", "ec"]]
                     .mean().round(6).reset_index())
    tau_agg.to_csv(args.out / "ablation_tau_summary.csv", index=False)

    bin_df = pd.DataFrame(bin_rows).round(6)
    bin_df.to_csv(args.out / "ablation_bins_summary.csv", index=False)

    print("\n=== tau x SG, RE1-OB ===")
    print(tau_agg[tau_agg.system == "re1-ob"].pivot(index="method", columns="tau", values="sg")
          .round(4).to_string(), flush=True)
    print("\n=== B x ECE, RE1-OB ===")
    print(bin_df[bin_df.system == "re1-ob"].pivot(index="method", columns="n_bins", values="ece")
          .round(4).to_string(), flush=True)
    print("\nTAU/BIN ABLATION REGENERATION COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
