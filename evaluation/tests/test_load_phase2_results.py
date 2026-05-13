"""Tests for the Week 5 integration loader.

The loader is an end-of-Phase-2 stitcher: it inner-joins the EC
harness's per-case CSV with the CC harness's per-case CSV to produce
a single 875-row DataFrame for headline / scatter / correlation
analysis.

Tests run against the actual results CSVs in ``results/`` (not
fixtures), because the whole point of the loader is to verify those
files form a coherent set. If the CSVs are stale, these tests fail
loudly — exactly the signal we want for downstream paper work.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from evaluation.analysis.load_phase2_results import (
    _EXPECTED_METHODS,
    _EXPECTED_PER_METHOD,
    _EXPECTED_TOTAL_ROWS,
    load_aggregate_ece,
    load_all_phase2_results,
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
    reason=(
        "Phase 2 CSVs not present — run "
        "`python -m evaluation.experiments.run_phase2_ec` and "
        "`python -m evaluation.experiments.run_phase2_cc` first"
    ),
)


@requires_csvs
def test_total_row_count_is_875():
    df = load_all_phase2_results()
    assert len(df) == _EXPECTED_TOTAL_ROWS == 875


@requires_csvs
def test_all_seven_methods_present():
    df = load_all_phase2_results()
    assert set(df["method"].unique()) == _EXPECTED_METHODS


@requires_csvs
def test_125_cases_per_method():
    df = load_all_phase2_results()
    counts = df.groupby("method").size().to_dict()
    assert all(c == _EXPECTED_PER_METHOD for c in counts.values()), counts


@requires_csvs
def test_no_nan_in_metric_columns():
    df = load_all_phase2_results()
    for col in ("ac1", "sg", "sc", "ec", "ece_proxy", "confidence"):
        assert df[col].isna().sum() == 0, f"{col} has NaN entries"


@requires_csvs
def test_ece_proxy_in_unit_interval():
    df = load_all_phase2_results()
    assert df["ece_proxy"].between(0.0, 1.0).all()


@requires_csvs
def test_ece_proxy_matches_definition():
    """``ece_proxy == |confidence − (1.0 if correct else 0.0)|``.

    Spot-check on a random subsample; the loader copies cal_error
    from the CC CSV, which the CC harness computes via
    :func:`per_case_calibration_error` — same formula.
    """
    df = load_all_phase2_results().sample(20, random_state=0)
    target = df["correct"].astype(float)
    expected = (df["confidence"] - target).abs()
    pd.testing.assert_series_equal(
        df["ece_proxy"].reset_index(drop=True),
        expected.reset_index(drop=True),
        check_names=False,
        rtol=1e-9, atol=1e-9,
    )


@requires_csvs
def test_columns_in_expected_order():
    df = load_all_phase2_results()
    assert list(df.columns) == [
        "method", "case_id", "fault",
        "ac1", "sg", "sc", "ec",
        "ece_proxy",
        "confidence", "correct",
    ]


@requires_csvs
def test_correct_column_matches_ac1():
    df = load_all_phase2_results()
    # ac1 is 0.0/1.0; correct is bool.
    assert (df["correct"] == (df["ac1"] == 1.0)).all()


@requires_csvs
def test_aggregate_ece_loader_returns_seven_rows():
    df = load_aggregate_ece()
    assert len(df) == 7
    assert set(df["method"]) == _EXPECTED_METHODS


@requires_csvs
def test_aggregate_ece_values_in_unit_interval():
    df = load_aggregate_ece()
    assert df["ece"].between(0.0, 1.0).all()


@requires_csvs
def test_loader_validates_loud_on_stale_subset(tmp_path):
    """If we feed it a CSV with the wrong row count, it raises.

    Smoke-tests the :func:`_validate` invariants by constructing a
    minimally-broken pair of inputs.
    """
    # Copy the real EC CSV but truncate to 100 rows.
    src_ec = RESULTS_DIR / "phase2_explanation_completeness.csv"
    src_cc = RESULTS_DIR / "phase2_confidence_calibration_per_case.csv"
    src_agg = RESULTS_DIR / "phase2_confidence_calibration.csv"
    (tmp_path / "phase2_confidence_calibration.csv").write_text(
        src_agg.read_text()
    )
    ec = pd.read_csv(src_ec).head(100)
    cc = pd.read_csv(src_cc).head(100)
    ec.to_csv(tmp_path / "phase2_explanation_completeness.csv", index=False)
    cc.to_csv(
        tmp_path / "phase2_confidence_calibration_per_case.csv", index=False,
    )
    with pytest.raises(RuntimeError, match="875"):
        load_all_phase2_results(results_dir=tmp_path)
