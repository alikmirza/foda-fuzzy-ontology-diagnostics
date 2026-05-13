"""Smoke tests for the Phase 2 Week 4 ConfidenceCalibration harness.

Mirrors :mod:`evaluation.tests.test_run_phase2_ec`'s shape. Covers the
per-method ECE aggregation, the per-fault row breakdown, CSV
round-trip, the per-case Spearman path, and an end-to-end run against
the 2-case fake RCAEval fixture (so the test stays second-fast and
does not require the real RE1-OB data).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

from evaluation.experiments.run_phase2_cc import (
    _ALL_FAULTS_LABEL,
    _compute_correlations,
    _summarize,
    spearman,
    write_csv,
)
from evaluation.metrics.confidence_calibration import ConfidenceCalibration


FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def _fake_rows() -> list[dict[str, object]]:
    """Two methods × two faults × small per-bucket variation.

    Method A is perfectly calibrated (conf 0.9 + correct, conf 0.1 +
    wrong); method B is overconfident (conf 0.9 + wrong on both
    cases).
    """
    return [
        {"method": "A", "case_id": "a", "fault": "cpu",
         "confidence": 0.9, "correct": 1, "cal_error": 0.1,
         "ac1": 1.0, "sg": 1.0, "sc": 0.5, "ec_overall": 1.0},
        {"method": "A", "case_id": "b", "fault": "mem",
         "confidence": 0.1, "correct": 0, "cal_error": 0.1,
         "ac1": 0.0, "sg": 1.0, "sc": 0.3, "ec_overall": 1.0},
        {"method": "B", "case_id": "a", "fault": "cpu",
         "confidence": 0.9, "correct": 0, "cal_error": 0.9,
         "ac1": 0.0, "sg": 0.0, "sc": 0.0, "ec_overall": 1.0 / 3.0},
        {"method": "B", "case_id": "b", "fault": "mem",
         "confidence": 0.9, "correct": 0, "cal_error": 0.9,
         "ac1": 0.0, "sg": 0.0, "sc": 0.0, "ec_overall": 1.0 / 3.0},
    ]


# ---- aggregation ----------------------------------------------------------


def test_summarize_per_method_ece_aggregates():
    cc = ConfidenceCalibration(n_bins=10)
    summary, per_method = _summarize(_fake_rows(), cc)
    # Method A: bucket 9 has 1 case (conf 0.9, correct) → avg_conf 0.9,
    #          accuracy 1.0, gap 0.1, weight 0.5.
    #          Bucket 1 has 1 case (conf 0.1, wrong) → avg_conf 0.1,
    #          accuracy 0.0, gap 0.1, weight 0.5.
    #          ECE = 0.5·0.1 + 0.5·0.1 = 0.1.
    assert per_method["A"]["ece"] == pytest.approx(0.1)
    # Method B: bucket 9 has 2 cases at conf 0.9 both wrong → gap 0.9,
    #          weight 1.0 → ECE = 0.9.
    assert per_method["B"]["ece"] == pytest.approx(0.9)


def test_summarize_emits_aggregate_and_per_fault_rows():
    cc = ConfidenceCalibration(n_bins=10)
    summary, _ = _summarize(_fake_rows(), cc)
    by_method_fault = {(r["method"], r["fault"]): r for r in summary}
    # Each method gets an ALL aggregate row + one row per observed fault.
    assert ("A", _ALL_FAULTS_LABEL) in by_method_fault
    assert ("A", "cpu") in by_method_fault
    assert ("A", "mem") in by_method_fault
    assert ("B", _ALL_FAULTS_LABEL) in by_method_fault
    # Aggregate row has n_cases = sum of per-fault n_cases.
    assert by_method_fault[("A", _ALL_FAULTS_LABEL)]["n_cases"] == 2
    assert by_method_fault[("A", "cpu")]["n_cases"] == 1
    assert by_method_fault[("A", "mem")]["n_cases"] == 1


def test_summarize_per_method_reliability_diagram_attached():
    cc = ConfidenceCalibration(n_bins=10)
    _, per_method = _summarize(_fake_rows(), cc)
    diag = per_method["A"]["reliability"]
    assert set(diag.keys()) >= {
        "bin_edges", "bin_centers", "bin_counts",
        "bin_avg_confidence", "bin_accuracy",
        "overconfidence_bins", "underconfidence_bins",
    }
    # Method A populates bucket 1 and bucket 9.
    assert diag["bin_counts"][1] == 1
    assert diag["bin_counts"][9] == 1


def test_summarize_carries_sg_sc_ec_means():
    cc = ConfidenceCalibration(n_bins=10)
    _, per_method = _summarize(_fake_rows(), cc)
    assert per_method["A"]["sg_mean"] == 1.0
    assert per_method["A"]["sc_mean"] == 0.4
    assert per_method["A"]["ec_mean"] == 1.0


# ---- IO -------------------------------------------------------------------


def test_write_csv_round_trip(tmp_path):
    cc = ConfidenceCalibration(n_bins=10)
    rows = _fake_rows()
    summary, _ = _summarize(rows, cc)
    path = tmp_path / "cc.csv"
    write_csv(summary, path)
    with path.open() as fh:
        loaded = list(csv.DictReader(fh))
    assert len(loaded) == len(summary)
    assert set(loaded[0].keys()) == {
        "method", "fault", "n_cases", "ece",
        "mean_confidence", "mean_accuracy",
        "overconfidence_bins", "underconfidence_bins",
    }


# ---- Spearman -------------------------------------------------------------


def test_spearman_ac1_vs_cal_error_negative_on_fake_rows():
    """The fake rows are constructed so AC@1 = 1 → cal_error = 0.1
    (low), AC@1 = 0 → cal_error ∈ {0.1, 0.9}. Across 4 rows the rank
    correlation must be ≤ 0 (high AC@1 maps to low cal_error)."""
    rows = _fake_rows()
    corr = spearman(rows, "ac1", "cal_error")
    assert corr <= 0.0


def test_compute_correlations_returns_all_four_keys():
    rows = _fake_rows()
    corr = _compute_correlations(rows)
    assert set(corr.keys()) == {"ac1", "sg", "sc", "ec"}
    for v in corr.values():
        assert isinstance(v, float)


# ---- end-to-end on fake fixture ------------------------------------------


def test_end_to_end_on_fake_fixture():
    """2 cases × 7 methods over the fake RCAEval fixture.

    Verifies that every method emits a finite confidence and that
    ECE aggregates without raising.
    """
    from evaluation.experiments.run_phase2_cc import evaluate
    per_case_rows, summary_rows, per_method = evaluate(FIXTURE)
    assert len(per_case_rows) == 14
    for r in per_case_rows:
        assert 0.0 <= r["confidence"] <= 1.0
        assert r["correct"] in (0, 1)
        assert 0.0 <= r["cal_error"] <= 1.0
    # Each method gets an aggregate row + ≥ 1 per-fault row.
    methods = {r["method"] for r in summary_rows}
    assert methods == {"MR", "CR", "Micro", "BARO", "yRCA", "FODA-FCP", "DejaVu"}
    for m in methods:
        m_rows = [r for r in summary_rows if r["method"] == m]
        assert any(r["fault"] == _ALL_FAULTS_LABEL for r in m_rows)
    # Every per-method ECE is finite or nan (nan only if a method
    # produced no rows — the assertion catches accidental drop-throughs).
    for m, rec in per_method.items():
        assert rec["n"] >= 1
        assert isinstance(rec["ece"], float)
        assert not math.isinf(rec["ece"])
