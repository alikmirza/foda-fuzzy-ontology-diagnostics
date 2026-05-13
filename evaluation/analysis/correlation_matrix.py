"""Week 5 — pairwise Spearman correlation matrices.

Two outputs:

* ``matrix_overall`` — a single 5×5 Spearman matrix across all 875
  (method, case) pairs, columns = (AC@1, SG, SC, EC, ECE_proxy). The
  off-diagonal cells say "how much does metric X predict metric Y on
  this benchmark, ignoring method identity?".

* ``matrix_per_method`` — one 5×5 matrix per method (7 × 25 cells),
  computed across the 125 cases within that method. Reveals whether
  the overall correlations are method-driven or robust to
  conditioning on method.

ECE is represented in both matrices by ``ece_proxy = |confidence −
correct|`` (the per-case Brier-style proxy), not the aggregate ECE.
The aggregate ECE has no per-case decomposition, so it can't enter a
per-case correlation matrix — see DEVIATIONS.md → "Aggregate-only
contract" for the reasoning.

The CSV format is long-form so downstream consumers can pivot
arbitrarily::

    scope, method, x, y, rho

with ``scope ∈ {overall, per_method}`` and ``method == "ALL"`` for
the overall scope. 5 + 7×5 = 40 cells per matrix (excluding self
correlations), 25 + 7×25 = 200 raw cells including self-correlations
of 1.0.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .load_phase2_results import load_all_phase2_results


#: Column order for the matrix. Same as the headline-table convention.
METRIC_COLUMNS: tuple[str, ...] = ("ac1", "sg", "sc", "ec", "ece_proxy")

#: Display labels (markdown / printout).
METRIC_DISPLAY: dict[str, str] = {
    "ac1":       "AC@1",
    "sg":        "SG",
    "sc":        "SC",
    "ec":        "EC",
    "ece_proxy": "ECE_proxy",
}

#: Method order for per-method matrices. Same family-grouped order
#: as the headline table.
METHOD_ORDER: tuple[str, ...] = (
    "DejaVu", "BARO", "CR", "MR", "Micro", "yRCA", "FODA-FCP",
)


def compute_overall_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Single 5×5 Spearman matrix across all 875 rows."""
    return df[list(METRIC_COLUMNS)].corr(method="spearman")


def compute_per_method_matrices(
    df: pd.DataFrame,
) -> dict[str, pd.DataFrame]:
    """One 5×5 Spearman matrix per method, keyed by method label."""
    out: dict[str, pd.DataFrame] = {}
    for method in METHOD_ORDER:
        subset = df[df["method"] == method]
        if subset.empty:
            continue
        out[method] = subset[list(METRIC_COLUMNS)].corr(method="spearman")
    return out


def to_long_form(
    overall: pd.DataFrame,
    per_method: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    """Stack the matrices into a long-form DataFrame.

    Schema: ``scope, method, x, y, rho``. ``scope == "overall"``
    holds the global matrix (``method == "ALL"``); ``scope ==
    "per_method"`` holds the conditional matrices.
    """
    rows: list[dict[str, object]] = []
    for x in METRIC_COLUMNS:
        for y in METRIC_COLUMNS:
            rows.append({
                "scope": "overall",
                "method": "ALL",
                "x": METRIC_DISPLAY[x],
                "y": METRIC_DISPLAY[y],
                "rho": float(overall.loc[x, y]),
            })
    for method, mat in per_method.items():
        for x in METRIC_COLUMNS:
            for y in METRIC_COLUMNS:
                rows.append({
                    "scope": "per_method",
                    "method": method,
                    "x": METRIC_DISPLAY[x],
                    "y": METRIC_DISPLAY[y],
                    "rho": float(mat.loc[x, y]),
                })
    return pd.DataFrame(rows)


def format_markdown_matrix(matrix: pd.DataFrame, title: str) -> str:
    """Render a 5×5 matrix as a markdown table with a header row."""
    labels = [METRIC_DISPLAY[c] for c in METRIC_COLUMNS]
    lines = [
        f"**{title}**",
        "",
        "| | " + " | ".join(labels) + " |",
        "| --- | " + " | ".join("---:" for _ in labels) + " |",
    ]
    for r in METRIC_COLUMNS:
        cells = [
            f"{matrix.loc[r, c]:+.3f}" if r != c else "1.000"
            for c in METRIC_COLUMNS
        ]
        lines.append(f"| **{METRIC_DISPLAY[r]}** | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_csv(long_form: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    long_form.to_csv(path, index=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_correlation_matrices.csv"),
    )
    args = parser.parse_args(argv)

    df = load_all_phase2_results()
    overall = compute_overall_matrix(df)
    per_method = compute_per_method_matrices(df)
    long_form = to_long_form(overall, per_method)
    write_csv(long_form, args.out)

    print(format_markdown_matrix(overall, "Overall (n = 875)"))
    print()
    for method, mat in per_method.items():
        print(format_markdown_matrix(mat, f"{method} (n = 125)"))
        print()
    print(f"Wrote {len(long_form)} cells to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
