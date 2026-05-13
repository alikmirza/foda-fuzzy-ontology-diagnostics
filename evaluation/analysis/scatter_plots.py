"""Week 5 — four AC@1-vs-semantic-metric scatter plots.

Paper 6 Section 4 will reference these directly. Each PNG is a single
6"×6" figure showing all 875 (method, case) points as small dots
plus per-method centroids as labelled diamonds. A consistent
7-colour palette is shared across all four plots so the reader can
track the same method's cluster across (SG, SC, EC, ECE_proxy) axes.

ECE_proxy is the per-case ``|confidence − correct|`` proxy (range
[0, 1], lower = better calibrated). To keep "up = better" consistent
with the other three plots, the ECE_proxy y-axis is inverted; the
title and axis label flag this.

Generated artefacts (4 files):

* ``paper/artifacts/scatter_ac1_vs_sg.png``
* ``paper/artifacts/scatter_ac1_vs_sc.png``
* ``paper/artifacts/scatter_ac1_vs_ec.png``
* ``paper/artifacts/scatter_ac1_vs_ece_proxy.png``

The matplotlib code is intentionally minimal — Paper 6 will need to
regenerate with venue-specific formatting (fonts, sizes, colour
schemes) later. Keep this script as the data-side baseline and
regenerate from it.
"""

from __future__ import annotations

import argparse
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .correlation_matrix import compute_overall_matrix
from .load_phase2_results import load_all_phase2_results


#: 7-colour palette. Tableau-10 minus orange/grey for accessibility.
#: Order matches METHOD_ORDER so the legend appears family-grouped.
METHOD_COLOR: dict[str, str] = {
    "DejaVu":   "#1f77b4",   # blue   (supervised)
    "BARO":     "#9467bd",   # purple (probabilistic)
    "CR":       "#2ca02c",   # green  (causal)
    "MR":       "#17becf",   # cyan   (graph-walk)
    "Micro":    "#bcbd22",   # olive  (graph-walk)
    "yRCA":     "#e377c2",   # pink   (rule-based)
    "FODA-FCP": "#d62728",   # red    (rule-based, dissertation centre)
}

#: Plot order — same family ordering as the headline table.
METHOD_ORDER: tuple[str, ...] = tuple(METHOD_COLOR.keys())


def _spearman_rho(df: pd.DataFrame, x: str, y: str) -> float:
    corr = compute_overall_matrix(df)
    return float(corr.loc[x, y])


def _scatter(
    ax,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    y_label: str,
    invert_y: bool = False,
) -> None:
    # Background: 875 per-case points.
    for method in METHOD_ORDER:
        subset = df[df["method"] == method]
        if subset.empty:
            continue
        ax.scatter(
            subset[x_col], subset[y_col],
            s=10, alpha=0.25, color=METHOD_COLOR[method],
            label=method, edgecolors="none",
        )

    # Foreground: per-method centroids as labelled diamonds.
    for method in METHOD_ORDER:
        subset = df[df["method"] == method]
        if subset.empty:
            continue
        cx = float(subset[x_col].mean())
        cy = float(subset[y_col].mean())
        ax.scatter(
            cx, cy, s=130, marker="D",
            color=METHOD_COLOR[method],
            edgecolors="black", linewidths=1.0, zorder=10,
        )
        ax.annotate(
            method, (cx, cy),
            xytext=(7, 7), textcoords="offset points",
            fontsize=9, fontweight="bold", zorder=11,
        )

    # Axes / framing.
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("AC@1 (top-1 accuracy)")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.grid(True, linestyle="--", alpha=0.4)
    if invert_y:
        ax.invert_yaxis()

    # Spearman ρ annotation in the corner that's least likely to overlap.
    rho = _spearman_rho(df, "ac1", x_col_to_metric(y_col))
    corner = (0.97, 0.97) if not invert_y else (0.97, 0.03)
    va = "top" if not invert_y else "bottom"
    ax.text(
        corner[0], corner[1],
        f"Spearman ρ = {rho:+.3f}",
        transform=ax.transAxes,
        ha="right", va=va,
        fontsize=10, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="grey", alpha=0.85,
                  boxstyle="round,pad=0.3"),
    )

    ax.legend(
        loc="lower left" if not invert_y else "upper left",
        fontsize=8, framealpha=0.85, markerscale=2.0,
        labelspacing=0.3,
    )


def x_col_to_metric(y_col: str) -> str:
    """Map a scatter y-axis column to the correlation-matrix label.

    The matrix uses lower-case metric names; scatter columns match
    the loader column names which are already lower-case. The map is
    identity for everything except future renamings — keep the
    indirection so the plot script and matrix don't drift.
    """
    return y_col


_PLOTS: tuple[tuple[str, str, str, bool], ...] = (
    # (y_col, title, y_label, invert_y)
    ("sg",
     "AC@1 vs SemanticGroundedness",
     "SG  (higher = better)",
     False),
    ("sc",
     "AC@1 vs SemanticCoherence",
     "SC  (higher = better)",
     False),
    ("ec",
     "AC@1 vs ExplanationCompleteness",
     "EC  (higher = better)",
     False),
    ("ece_proxy",
     "AC@1 vs ECE proxy  (lower-is-better — y-axis inverted)",
     "ECE proxy |conf − correct|  (lower = better)",
     True),
)


def generate(
    df: pd.DataFrame | None = None,
    out_dir: Path | None = None,
) -> list[Path]:
    """Generate all four PNGs. Returns the written paths."""
    df = df if df is not None else load_all_phase2_results()
    out_dir = (out_dir or Path("paper/artifacts")).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for y_col, title, y_label, invert_y in _PLOTS:
        fig, ax = plt.subplots(figsize=(6, 6))
        _scatter(ax, df, "ac1", y_col, title, y_label, invert_y=invert_y)
        fig.tight_layout()
        out_path = out_dir / f"scatter_ac1_vs_{y_col}.png"
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        paths.append(out_path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path,
        default=Path("paper/artifacts"),
    )
    args = parser.parse_args(argv)
    paths = generate(out_dir=args.out_dir)
    for p in paths:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
