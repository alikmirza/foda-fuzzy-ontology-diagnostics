#!/usr/bin/env python3
"""Bootstrap 95% percentile CIs on AC@1 for 7 methods x 3 RCAEval systems.

Reviewers asked for confidence intervals on the contested ranking-accuracy
metric (AC@1) backing Paper 6 Tables 1a-c, which currently report point
estimates only.

This is a *consumer* of the per-case AC@1 values already produced by the
existing evaluation harness (results/week2_<method>_validation[_<system>].csv).
It does NOT refactor or re-run the harness -- it reads the per-case binary
correctness column ("AC@1", one row per case, 1.0/0.0 hit-rate) and computes
a percentile bootstrap CI on the mean.

Reproducibility: random_state=42 on every bootstrap call, so output is
byte-identical across runs.

Usage:
    python3 scripts/bootstrap_ac1_ci.py
"""

import csv
import os
from itertools import combinations

import numpy as np
from scipy.stats import bootstrap

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
N_RESAMPLES = 10_000
CONFIDENCE = 0.95
EXPECTED_CASES = 125

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(REPO_ROOT, "results")
OUTPUT_PATH = os.path.join(REPO_ROOT, "paper", "artifacts", "bootstrap_ac1_cis.md")

# (method_key, display_name) preserving the file naming and the paper labels.
METHODS = [
    ("baro", "BARO"),
    ("causalrca", "CR"),
    ("dejavu", "DejaVu"),
    ("foda_fcp", "FODA-FCP"),
    ("microrca", "Micro"),
    ("monitorrank", "MR"),
    ("yrca", "yRCA"),
]

# (system_id, file_suffix, table_label) -- re1-ob carries no suffix.
SYSTEMS = [
    ("RE1-OB", "", "Table 1a"),
    ("RE1-SS", "_re1-ss", "Table 1b"),
    ("RE1-TT", "_re1-tt", "Table 1c"),
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_per_case_ac1(method_key, suffix):
    """Return per-case AC@1 values (np.ndarray) read by column NAME.

    DejaVu places AC@1 in a different column index than the other methods, so
    we must address it by header name, never by position.
    """
    path = os.path.join(RESULTS_DIR, f"week2_{method_key}_validation{suffix}.csv")
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        if "AC@1" not in reader.fieldnames:
            raise KeyError(f"'AC@1' column not found in {path}")
        values = [float(row["AC@1"]) for row in reader]
    arr = np.array(values, dtype=float)
    if np.isnan(arr).any():
        raise ValueError(f"NaN in AC@1 column of {path}")
    if arr.size != EXPECTED_CASES:
        raise ValueError(
            f"{path}: expected {EXPECTED_CASES} cases, got {arr.size}"
        )
    return arr


def bootstrap_ci(per_case):
    """Percentile bootstrap 95% CI on mean AC@1 (seed-fixed)."""
    # Degenerate case: a constant array (all 0s or all 1s) has zero variance,
    # so the CI collapses to the point estimate. scipy warns on this; handle
    # it explicitly to keep output clean and deterministic.
    point = float(np.mean(per_case))
    if np.all(per_case == per_case[0]):
        return point, point, point
    res = bootstrap(
        (per_case,),
        statistic=np.mean,
        n_resamples=N_RESAMPLES,
        confidence_level=CONFIDENCE,
        method="percentile",
        random_state=SEED,
    )
    return point, float(res.confidence_interval.low), float(res.confidence_interval.high)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # results[system_id] = list of dicts sorted by point desc
    results = {}
    for system_id, suffix, _label in SYSTEMS:
        cells = []
        for method_key, display in METHODS:
            arr = load_per_case_ac1(method_key, suffix)
            point, low, high = bootstrap_ci(arr)
            cells.append(
                {"method": display, "n": arr.size, "point": point, "low": low, "high": high}
            )
        cells.sort(key=lambda c: c["point"], reverse=True)
        results[system_id] = cells

    lines = []
    lines.append("# Bootstrap 95% Confidence Intervals on AC@1")
    lines.append("")
    lines.append(
        f"Percentile bootstrap, n_resamples={N_RESAMPLES:,}, "
        f"confidence_level={CONFIDENCE}, random_state={SEED}. "
        f"Each cell aggregates {EXPECTED_CASES} per-case binary AC@1 (hit/miss) values "
        "from the existing evaluation harness "
        "(`results/week2_<method>_validation[_<system>].csv`)."
    )
    lines.append("")

    # (a) Markdown tables, one per system, sorted by AC@1 desc.
    lines.append("## (a) Markdown tables")
    lines.append("")
    for system_id, _suffix, label in SYSTEMS:
        lines.append(f"### {system_id} ({label})")
        lines.append("")
        lines.append("| Method | AC@1 (point) | 95% CI low | 95% CI high |")
        lines.append("|--------|-------------:|-----------:|------------:|")
        for c in results[system_id]:
            lines.append(
                f"| {c['method']} | {c['point']:.3f} | {c['low']:.3f} | {c['high']:.3f} |"
            )
        lines.append("")

    # (b) LaTeX-style fragments, AC@1 reformatted as "point [low, high]".
    lines.append("## (b) LaTeX-ready fragments (Tables 1a-c)")
    lines.append("")
    lines.append(
        "Each AC@1 cell is rendered as `point [low, high]`. Drop-in replacement "
        "for the current AC@1 column."
    )
    lines.append("")
    for system_id, _suffix, label in SYSTEMS:
        lines.append(f"% {label} -- {system_id}")
        lines.append("\\begin{tabular}{lc}")
        lines.append("\\toprule")
        lines.append("Method & AC@1 (95\\% CI) \\\\")
        lines.append("\\midrule")
        for c in results[system_id]:
            method_tex = c["method"].replace("_", "\\_")
            lines.append(
                f"{method_tex} & {c['point']:.3f} [{c['low']:.3f}, {c['high']:.3f}] \\\\"
            )
        lines.append("\\bottomrule")
        lines.append("\\end{tabular}")
        lines.append("")

    # (5) Non-overlapping CI pairs (statistically distinguishable at 95%).
    lines.append("## Non-overlapping CI pairs (distinguishable at 95%)")
    lines.append("")
    summary_lines = []
    for system_id, _suffix, _label in SYSTEMS:
        cells = results[system_id]
        for a, b in combinations(cells, 2):
            # Sorted desc, so a["point"] >= b["point"]; non-overlap when the
            # lower method's high < the higher method's low.
            hi, lo = (a, b) if a["point"] >= b["point"] else (b, a)
            if lo["high"] < hi["low"]:
                line = (
                    f"[{system_id}] {hi['method']} ({hi['point']:.3f} "
                    f"[{hi['low']:.3f}, {hi['high']:.3f}]) > {lo['method']} "
                    f"({lo['point']:.3f} [{lo['low']:.3f}, {lo['high']:.3f}]) "
                    "- CIs do not overlap"
                )
                summary_lines.append(line)
    if summary_lines:
        for s in summary_lines:
            lines.append(f"- {s}")
    else:
        lines.append("- (none: every within-system method pair has overlapping CIs)")
    lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    # Console: one-line summary per non-overlapping pair.
    print(f"Wrote {OUTPUT_PATH}")
    print(
        f"Computed CIs for {len(METHODS)} methods x {len(SYSTEMS)} systems "
        f"= {len(METHODS) * len(SYSTEMS)} cells."
    )
    print(f"Non-overlapping CI pairs (distinguishable at 95%): {len(summary_lines)}")
    for s in summary_lines:
        print(f"  {s}")


if __name__ == "__main__":
    main()
