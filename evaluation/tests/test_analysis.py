"""Smoke tests for the Week 5 analysis package.

Tests exercise the headline-table, correlation-matrix, and
scatter-plot builders end-to-end on a synthetic fixture so they're
fast and don't require the live ``results/`` CSVs. A separate
``requires_csvs``-gated run-through verifies the builders also work
on the real Phase 2 outputs when they exist (the same gate used by
``test_load_phase2_results.py``).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd
import pytest

matplotlib.use("Agg")

from evaluation.analysis.correlation_matrix import (
    METRIC_COLUMNS as MATRIX_METRIC_COLUMNS,
    compute_overall_matrix,
    compute_per_method_matrices,
    format_markdown_matrix,
    to_long_form,
)
from evaluation.analysis.headline_table import (
    METHOD_ORDER as TABLE_METHOD_ORDER,
    METRIC_COLUMNS as TABLE_METRIC_COLUMNS,
    build_headline_table,
    format_markdown,
)
from evaluation.analysis.scatter_plots import (
    METHOD_COLOR,
    METHOD_ORDER as PLOT_METHOD_ORDER,
    generate as generate_scatter_plots,
)


RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"


def _csvs_available() -> bool:
    return (
        (RESULTS_DIR / "phase2_explanation_completeness.csv").exists()
        and (RESULTS_DIR / "phase2_confidence_calibration_per_case.csv").exists()
        and (RESULTS_DIR / "phase2_confidence_calibration.csv").exists()
    )


requires_csvs = pytest.mark.skipif(
    not _csvs_available(),
    reason="Phase 2 CSVs not present — run the harnesses first",
)


# ---- synthetic fixture ----------------------------------------------------


def _synthetic_per_case() -> pd.DataFrame:
    """4 methods × 3 cases — small enough to hand-check correlations."""
    rows = []
    for m, ac1_pattern, sg_pattern, conf_pattern in [
        ("DejaVu",   [1.0, 1.0, 0.0], [0.0, 0.0, 0.0], [0.9, 0.9, 0.1]),
        ("BARO",     [1.0, 0.0, 1.0], [0.0, 0.0, 0.0], [0.5, 0.5, 0.5]),
        ("MR",       [0.0, 1.0, 0.0], [0.0, 0.0, 0.0], [0.3, 0.3, 0.3]),
        ("FODA-FCP", [1.0, 1.0, 0.0], [1.0, 1.0, 1.0], [0.7, 0.7, 0.2]),
    ]:
        for i, (a, s, c) in enumerate(zip(ac1_pattern, sg_pattern, conf_pattern)):
            correct = bool(a)
            rows.append({
                "method": m,
                "case_id": f"{m}_case_{i}",
                "fault": "cpu",
                "ac1": a,
                "sg": s,
                "sc": s * 0.5,
                "ec": (s + a) / 2.0,
                "ece_proxy": abs(c - (1.0 if correct else 0.0)),
                "confidence": c,
                "correct": correct,
            })
    return pd.DataFrame(rows)


def _synthetic_aggregate_ece() -> pd.DataFrame:
    return pd.DataFrame([
        {"method": "DejaVu",   "ece": 0.10, "mean_confidence": 0.6,
         "mean_accuracy": 0.67, "overconfidence_bins": 1, "underconfidence_bins": 0},
        {"method": "BARO",     "ece": 0.50, "mean_confidence": 0.5,
         "mean_accuracy": 0.67, "overconfidence_bins": 0, "underconfidence_bins": 1},
        {"method": "MR",       "ece": 0.30, "mean_confidence": 0.3,
         "mean_accuracy": 0.33, "overconfidence_bins": 0, "underconfidence_bins": 1},
        {"method": "FODA-FCP", "ece": 0.20, "mean_confidence": 0.5,
         "mean_accuracy": 0.67, "overconfidence_bins": 0, "underconfidence_bins": 1},
    ])


# ---- headline_table -------------------------------------------------------


def test_method_order_lists_match():
    """The headline table and the scatter plots must agree on
    method order; that's how the colour palette stays aligned."""
    assert tuple(TABLE_METHOD_ORDER) == tuple(PLOT_METHOD_ORDER)


def test_headline_table_columns_and_rows():
    per_case = _synthetic_per_case()
    agg = _synthetic_aggregate_ece()
    table = build_headline_table(per_case=per_case, aggregate_ece=agg)
    assert list(table.columns) == ["method", *TABLE_METRIC_COLUMNS]
    # Synthetic fixture only has 4 methods, so the table has 4 rows
    # after the inner-join. The full ordering category isn't material
    # to the contract.
    assert len(table) == 4


def test_headline_table_means_match_groupby():
    per_case = _synthetic_per_case()
    agg = _synthetic_aggregate_ece()
    table = build_headline_table(per_case=per_case, aggregate_ece=agg)
    # Reconstruct per-method means and compare.
    expected = (
        per_case.groupby("method")[["ac1", "sg", "sc", "ec"]].mean()
    )
    for _, row in table.iterrows():
        m = str(row["method"])
        for col, alias in (("ac1", "AC@1"), ("sg", "SG"),
                           ("sc", "SC"), ("ec", "EC")):
            assert row[alias] == pytest.approx(expected.loc[m, col])


def test_headline_markdown_bolds_best_per_column():
    per_case = _synthetic_per_case()
    agg = _synthetic_aggregate_ece()
    table = build_headline_table(per_case=per_case, aggregate_ece=agg)
    md = format_markdown(table, bold_best_per_column=True)
    # DejaVu has the lowest ECE (0.10) → bolded.
    assert "**0.100**" in md
    # BARO's 0.500 ECE is NOT the column min → its specific row line
    # should not contain a bolded ECE value. Locate the BARO row and
    # verify its ECE cell stays unbolded.
    baro_line = next(
        line for line in md.splitlines() if line.startswith("| BARO")
    )
    # The ECE cell is the rightmost numeric cell.
    assert "| 0.500 |" in baro_line  # not bolded
    assert "**0.500**" not in baro_line


def test_headline_markdown_marks_direction_in_header():
    per_case = _synthetic_per_case()
    agg = _synthetic_aggregate_ece()
    md = format_markdown(
        build_headline_table(per_case=per_case, aggregate_ece=agg),
    )
    assert "AC@1 ↑" in md
    assert "ECE ↓" in md


# ---- correlation_matrix ---------------------------------------------------


def test_overall_matrix_is_5x5_and_symmetric():
    df = _synthetic_per_case()
    mat = compute_overall_matrix(df)
    assert mat.shape == (5, 5)
    assert list(mat.columns) == list(MATRIX_METRIC_COLUMNS)
    # Spearman is symmetric.
    for r in mat.index:
        for c in mat.columns:
            assert mat.loc[r, c] == pytest.approx(mat.loc[c, r], abs=1e-9)


def test_overall_matrix_diagonals_are_one():
    df = _synthetic_per_case()
    mat = compute_overall_matrix(df)
    for col in MATRIX_METRIC_COLUMNS:
        assert mat.loc[col, col] == pytest.approx(1.0)


def test_per_method_matrices_one_per_method():
    df = _synthetic_per_case()
    matrices = compute_per_method_matrices(df)
    # Synthetic fixture has 4 methods.
    assert set(matrices.keys()) == {"DejaVu", "BARO", "MR", "FODA-FCP"}
    for m, mat in matrices.items():
        assert mat.shape == (5, 5)


def test_long_form_includes_all_cells():
    df = _synthetic_per_case()
    overall = compute_overall_matrix(df)
    per_method = compute_per_method_matrices(df)
    long_form = to_long_form(overall, per_method)
    # 5×5 overall + 4 methods × 5×5 = 25 + 100 = 125 rows.
    assert len(long_form) == 5 * 5 + 4 * 5 * 5
    assert set(long_form["scope"].unique()) == {"overall", "per_method"}


def test_format_markdown_matrix_has_header_and_rows():
    df = _synthetic_per_case()
    md = format_markdown_matrix(compute_overall_matrix(df), "test matrix")
    assert "**test matrix**" in md
    assert "AC@1" in md and "ECE_proxy" in md
    # 5 metric rows + 2 header lines + 1 title + 1 spacer = 9 lines.
    assert md.count("\n") == 8


# ---- scatter_plots --------------------------------------------------------


def test_scatter_palette_covers_all_methods():
    assert set(METHOD_COLOR.keys()) == {
        "MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP",
    }
    # All colors must be unique — no two methods share a hue.
    assert len(set(METHOD_COLOR.values())) == 7


@requires_csvs
def test_generate_writes_four_pngs(tmp_path):
    paths = generate_scatter_plots(out_dir=tmp_path)
    expected = {
        "scatter_ac1_vs_sg.png",
        "scatter_ac1_vs_sc.png",
        "scatter_ac1_vs_ec.png",
        "scatter_ac1_vs_ece_proxy.png",
    }
    assert {p.name for p in paths} == expected
    for p in paths:
        assert p.exists()
        # PNG magic bytes.
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# ---- integration on real CSVs ---------------------------------------------


@requires_csvs
def test_real_headline_table_has_seven_rows():
    table = build_headline_table()
    assert len(table) == 7
    assert set(table["method"]) == {
        "MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP",
    }


@requires_csvs
def test_real_correlation_matrix_overall_finite():
    from evaluation.analysis.load_phase2_results import load_all_phase2_results
    mat = compute_overall_matrix(load_all_phase2_results())
    assert mat.shape == (5, 5)
    for r in mat.index:
        for c in mat.columns:
            v = float(mat.loc[r, c])
            assert -1.0 <= v <= 1.0
