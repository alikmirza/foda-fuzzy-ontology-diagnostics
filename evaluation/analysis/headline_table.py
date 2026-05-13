"""Week 5 — the 7-method × 5-metric headline table.

Builds the table Paper 6 Section 4 will quote directly:

* Per-case means for AC@1 / SG / SC / EC (all four are per-case
  scorers, so a mean is a meaningful summary).
* Per-method aggregate ECE pulled from
  ``phase2_confidence_calibration.csv``'s ``ALL`` rows — ECE is
  aggregate by mathematical necessity (see DEVIATIONS.md →
  "Aggregate-only contract").

Method ordering is **by family**, not alphabetically — Paper 6's
Table 1 groups methods so readers can scan supervised vs. probabilistic
vs. causal vs. graph-walk vs. rule-based without re-sorting:

* Supervised:    DejaVu
* Probabilistic: BARO
* Causal:        CR (CausalRCA)
* Graph-walk:    MR (MonitorRank), Micro (MicroRCA)
* Rule-based:    yRCA, FODA-FCP

The harness produces two artefacts:

* ``results/phase2_integration_headline.csv`` — machine-readable
  table for downstream notebook consumption.
* A markdown block (returned by :func:`format_markdown`, also
  printed by :func:`main`) — paste into ``paper/notes/findings.md``
  or copy into the manuscript.

Direction note: the four left-hand metrics are higher-is-better;
**ECE is lower-is-better**. Tables flag this in the header row to
prevent a misread.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .load_phase2_results import load_aggregate_ece, load_all_phase2_results


#: Method ordering for the headline table — Paper 6 Section 4's
#: row-order convention. Grouped by methodological family.
METHOD_ORDER: tuple[str, ...] = (
    "DejaVu",       # Supervised
    "BARO",         # Probabilistic
    "CR",           # Causal
    "MR",           # Graph-walk
    "Micro",        # Graph-walk
    "yRCA",         # Rule-based
    "FODA-FCP",     # Rule-based
)

#: Headers for the markdown / CSV output. Columns mirror the four
#: per-case means + the aggregate ECE. AC@1 first (the Paper-1-style
#: ranking baseline), then SG / SC / EC (the structural-quality
#: triple), then ECE (the calibration axis).
METRIC_COLUMNS: tuple[str, ...] = ("AC@1", "SG", "SC", "EC", "ECE")


def build_headline_table(
    per_case: pd.DataFrame | None = None,
    aggregate_ece: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return a 7-row DataFrame with ``method`` + the five metric
    columns. Per-case metrics are means across 125 cases; ECE is the
    aggregate value loaded from the Week 4 CC summary.
    """
    if per_case is None:
        per_case = load_all_phase2_results()
    if aggregate_ece is None:
        aggregate_ece = load_aggregate_ece()

    per_method_means = (
        per_case.groupby("method")[["ac1", "sg", "sc", "ec"]]
        .mean()
        .reset_index()
    )
    merged = per_method_means.merge(
        aggregate_ece[["method", "ece"]],
        on="method",
        how="inner",
        validate="one_to_one",
    )

    # Apply the family-grouped ordering.
    merged["method"] = pd.Categorical(
        merged["method"], categories=list(METHOD_ORDER), ordered=True,
    )
    merged = merged.sort_values("method").reset_index(drop=True)

    merged = merged.rename(columns={
        "ac1": "AC@1", "sg": "SG", "sc": "SC", "ec": "EC", "ece": "ECE",
    })
    return merged[["method", *METRIC_COLUMNS]]


def write_csv(table: pd.DataFrame, path: Path) -> None:
    """Persist the table at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(path, index=False)


def format_markdown(
    table: pd.DataFrame,
    bold_best_per_column: bool = True,
) -> str:
    """Return a paper-ready markdown table.

    ``bold_best_per_column`` highlights the leader for each metric:
    highest value for AC@1 / SG / SC / EC; **lowest** for ECE (the
    one direction-flipped metric).
    """
    family_label: dict[str, str] = {
        "DejaVu":   "supervised",
        "BARO":     "probabilistic",
        "CR":       "causal",
        "MR":       "graph-walk",
        "Micro":    "graph-walk",
        "yRCA":     "rule-based",
        "FODA-FCP": "rule-based",
    }
    best: dict[str, str] = {}
    if bold_best_per_column:
        for col in METRIC_COLUMNS:
            best[col] = (
                table["method"].iloc[int(table[col].idxmin())]
                if col == "ECE"
                else table["method"].iloc[int(table[col].idxmax())]
            )

    lines = [
        "| Method (family)       | "
        + " | ".join(f"{c} ↑" if c != "ECE" else "ECE ↓" for c in METRIC_COLUMNS)
        + " |",
        "| --------------------- | "
        + " | ".join("----:" for _ in METRIC_COLUMNS)
        + " |",
    ]
    for _, row in table.iterrows():
        method = str(row["method"])
        family = family_label.get(method, "")
        method_cell = f"{method} ({family})" if family else method
        cells = []
        for col in METRIC_COLUMNS:
            v = float(row[col])
            cell = f"{v:.3f}"
            if bold_best_per_column and best.get(col) == method:
                cell = f"**{cell}**"
            cells.append(cell)
        lines.append(f"| {method_cell:<21} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_integration_headline.csv"),
    )
    args = parser.parse_args(argv)

    table = build_headline_table()
    write_csv(table, args.out)
    print(format_markdown(table))
    print(f"\nWrote {len(table)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
