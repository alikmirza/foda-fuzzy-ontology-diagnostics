"""Tests for ``evaluation.metrics.confidence_calibration``.

ECE is an aggregate metric — see the module docstring for why the
Week 4 contract is a standalone analyzer rather than a
:class:`SemanticMetric` subclass. These tests exercise:

* the analytic ECE definition on synthetic perfect / worst-case /
  known cases,
* the reliability-diagram shape and the over/under-confidence-bin
  counters,
* the bucket-index edge case at confidence == 1.0,
* the per-case calibration-error proxy used for cross-metric Spearman.
"""

from __future__ import annotations

import math

import pytest

from evaluation.metrics.confidence_calibration import (
    ConfidenceCalibration,
    compute_ece,
    compute_reliability_diagram,
    per_case_calibration_error,
)


def _row(confidence: float, correct: bool, **extra: object) -> dict[str, object]:
    """Helper: a case-result mapping with the two required keys."""
    return {"confidence": confidence, "correct": correct, **extra}


# ---- 1. ECE on synthetic perfect / worst / known cases --------------------


class TestECEAnalyticCases:
    def test_perfect_calibration_is_zero(self):
        """All-correct cases at confidence 1.0 and all-wrong cases at
        confidence 0.0 → every non-empty bucket has accuracy == avg
        confidence → ECE = 0."""
        rows = (
            [_row(1.0, True)] * 10
            + [_row(0.0, False)] * 10
        )
        assert compute_ece(rows, n_bins=10) == pytest.approx(0.0)

    def test_worst_calibration_high_conf_all_wrong(self):
        """All cases at confidence 1.0 but all wrong: the single
        populated bucket has avg_conf 1.0 and accuracy 0.0 → ECE = 1.0."""
        rows = [_row(1.0, False)] * 20
        assert compute_ece(rows, n_bins=10) == pytest.approx(1.0)

    def test_worst_calibration_low_conf_all_right(self):
        """Symmetric: confidence 0.0 but all correct → gap of 1.0 in
        the leftmost bucket → ECE = 1.0."""
        rows = [_row(0.0, True)] * 20
        assert compute_ece(rows, n_bins=10) == pytest.approx(1.0)

    def test_known_two_bucket_perfectly_calibrated(self):
        """Two populated buckets, each on-average calibrated → ECE = 0.

        Bucket 1 (0.1 ≤ c < 0.2): 10 cases at conf 0.1, 1 correct
        → avg_conf 0.1, accuracy 0.1.

        Bucket 9 (0.9 ≤ c ≤ 1.0): 10 cases at conf 0.9, 9 correct
        → avg_conf 0.9, accuracy 0.9.

        Both gaps are 0 → ECE = 0.
        """
        rows = (
            [_row(0.1, True)] * 1 + [_row(0.1, False)] * 9
            + [_row(0.9, True)] * 9 + [_row(0.9, False)] * 1
        )
        assert compute_ece(rows, n_bins=10) == pytest.approx(0.0)

    def test_known_overconfident_single_bucket(self):
        """All four cases in bucket 0.8 (index 8), 2 correct of 4 →
        ECE = |0.8 − 0.5| = 0.3."""
        rows = [
            _row(0.8, True),  _row(0.8, True),
            _row(0.8, False), _row(0.8, False),
        ]
        assert compute_ece(rows, n_bins=10) == pytest.approx(0.3)

    def test_weighted_mixture_matches_hand_computation(self):
        """6 cases at conf 0.9 with 3 correct (gap 0.4, weight 6/10),
        4 cases at conf 0.1 with 1 correct (gap |0.1 - 0.25| = 0.15,
        weight 4/10) → ECE = 0.6·0.4 + 0.4·0.15 = 0.30."""
        rows = (
            [_row(0.9, True)] * 3
            + [_row(0.9, False)] * 3
            + [_row(0.1, True)] * 1
            + [_row(0.1, False)] * 3
        )
        assert compute_ece(rows, n_bins=10) == pytest.approx(0.30)


# ---- 2. ECE empty / invalid / parameter behaviour -------------------------


class TestECEEdgeCases:
    def test_empty_input_returns_nan(self):
        assert math.isnan(compute_ece([], n_bins=10))

    def test_n_bins_zero_raises(self):
        with pytest.raises(ValueError, match="n_bins"):
            compute_ece([_row(0.5, True)], n_bins=0)

    def test_n_bins_negative_raises(self):
        with pytest.raises(ValueError, match="n_bins"):
            compute_ece([_row(0.5, True)], n_bins=-3)

    def test_n_bins_resolution_changes_ece(self):
        """A miscalibrated population that's hidden inside one bucket
        at low resolution should expand the gap at higher resolution.

        Pattern: 5 cases at conf 0.05 all wrong (lives in bucket 0
        regardless of n_bins) plus 5 cases at conf 0.15 all correct.
        At n_bins=5, both fall in bucket 0 (0.0-0.2): avg_conf = 0.10,
        accuracy = 0.5 → gap 0.40, weight 1.0 → ECE 0.40.
        At n_bins=10, they separate into buckets 0 and 1:
          bucket 0: conf 0.05 / acc 0.0 → gap 0.05, weight 0.5
          bucket 1: conf 0.15 / acc 1.0 → gap 0.85, weight 0.5
          ECE = 0.5·0.05 + 0.5·0.85 = 0.45.
        Higher resolution exposes the gap → 10-bin ECE > 5-bin ECE.
        """
        rows = (
            [_row(0.05, False)] * 5
            + [_row(0.15, True)] * 5
        )
        ece5 = compute_ece(rows, n_bins=5)
        ece10 = compute_ece(rows, n_bins=10)
        assert ece5 == pytest.approx(0.40)
        assert ece10 == pytest.approx(0.45)
        assert ece10 > ece5

    def test_rejects_out_of_range_confidence(self):
        with pytest.raises(ValueError, match="confidence"):
            compute_ece([_row(1.5, True)], n_bins=10)

    def test_rejects_negative_confidence(self):
        with pytest.raises(ValueError, match="confidence"):
            compute_ece([_row(-0.1, True)], n_bins=10)


# ---- 3. Bucket index edge cases -------------------------------------------


class TestBucketIndex:
    def test_confidence_at_one_is_right_edge_inclusive(self):
        """A confidence of exactly 1.0 must land in the last bucket
        (index n_bins - 1), not in a non-existent bucket index
        n_bins. Otherwise calibration on top1-confident cases would
        silently drop them."""
        rows = [_row(1.0, True)] * 5 + [_row(1.0, False)] * 5
        diag = compute_reliability_diagram(rows, n_bins=10)
        assert diag["bin_counts"][-1] == 10
        assert sum(diag["bin_counts"]) == 10
        assert diag["bin_counts"][9] == 10

    def test_confidence_at_zero_lands_in_first_bucket(self):
        rows = [_row(0.0, False)] * 5
        diag = compute_reliability_diagram(rows, n_bins=10)
        assert diag["bin_counts"][0] == 5
        assert sum(diag["bin_counts"]) == 5


# ---- 4. Reliability diagram structure -------------------------------------


class TestReliabilityDiagram:
    def test_structure_keys_and_lengths(self):
        rows = [_row(0.5, True), _row(0.5, False)]
        diag = compute_reliability_diagram(rows, n_bins=10)
        assert set(diag.keys()) == {
            "bin_edges", "bin_centers", "bin_counts",
            "bin_avg_confidence", "bin_accuracy",
            "overconfidence_bins", "underconfidence_bins",
        }
        assert len(diag["bin_edges"]) == 11
        assert len(diag["bin_centers"]) == 10
        assert len(diag["bin_counts"]) == 10
        assert len(diag["bin_avg_confidence"]) == 10
        assert len(diag["bin_accuracy"]) == 10

    def test_edges_and_centers_uniform(self):
        diag = compute_reliability_diagram([], n_bins=4)
        assert diag["bin_edges"] == [0.0, 0.25, 0.5, 0.75, 1.0]
        assert diag["bin_centers"] == [0.125, 0.375, 0.625, 0.875]

    def test_empty_bins_report_nan(self):
        """A single case populates one bucket; the other 9 must
        report NaN for avg_conf/accuracy (a 0.0 would be confusable
        with a calibration extreme)."""
        rows = [_row(0.55, True)]
        diag = compute_reliability_diagram(rows, n_bins=10)
        # Bucket 5 (0.5 ≤ c < 0.6) is populated.
        for i in range(10):
            if i == 5:
                assert diag["bin_counts"][i] == 1
                assert diag["bin_avg_confidence"][i] == pytest.approx(0.55)
                assert diag["bin_accuracy"][i] == pytest.approx(1.0)
            else:
                assert diag["bin_counts"][i] == 0
                assert math.isnan(diag["bin_avg_confidence"][i])
                assert math.isnan(diag["bin_accuracy"][i])

    def test_overconfidence_and_underconfidence_counts(self):
        """Construct rows so 2 buckets are overconfident, 1 is
        underconfident, 1 is exactly calibrated, and the rest are
        empty."""
        rows = (
            # bucket index 1 — avg_conf 0.15, accuracy 0.0 → over
            [_row(0.15, False)] * 4
            # bucket index 3 — avg_conf 0.35, accuracy 0.0 → over
            + [_row(0.35, False)] * 2
            # bucket index 5 — avg_conf 0.55, accuracy 1.0 → under
            + [_row(0.55, True)] * 2
            # bucket index 8 — avg_conf 0.85, accuracy 0.5 → 1 right
            #                                          → 1 wrong (in 2)
            #                  → mean 0.5, gap |0.85 - 0.5| ≠ 0 → over
            + [_row(0.85, True), _row(0.85, False)]
        )
        diag = compute_reliability_diagram(rows, n_bins=10)
        # 3 buckets over, 1 under (no exactly-calibrated populated bucket).
        assert diag["overconfidence_bins"] == 3
        assert diag["underconfidence_bins"] == 1

    def test_perfectly_calibrated_bucket_counts_neither(self):
        """A bucket where avg_conf == accuracy should NOT increment
        the over- or under-confidence counter."""
        # 2 cases at conf 0.5, 1 correct → mean conf 0.5, accuracy 0.5.
        rows = [_row(0.5, True), _row(0.5, False)]
        diag = compute_reliability_diagram(rows, n_bins=10)
        assert diag["overconfidence_bins"] == 0
        assert diag["underconfidence_bins"] == 0


# ---- 5. Per-case calibration-error proxy ----------------------------------


class TestPerCaseCalibrationError:
    def test_high_conf_correct_is_low_error(self):
        assert per_case_calibration_error(0.9, True) == pytest.approx(0.1)

    def test_high_conf_wrong_is_high_error(self):
        assert per_case_calibration_error(0.9, False) == pytest.approx(0.9)

    def test_low_conf_correct_is_high_error(self):
        assert per_case_calibration_error(0.1, True) == pytest.approx(0.9)

    def test_low_conf_wrong_is_low_error(self):
        assert per_case_calibration_error(0.1, False) == pytest.approx(0.1)

    def test_boundary_values(self):
        assert per_case_calibration_error(0.0, False) == 0.0
        assert per_case_calibration_error(1.0, True) == 0.0
        assert per_case_calibration_error(0.0, True) == 1.0
        assert per_case_calibration_error(1.0, False) == 1.0

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            per_case_calibration_error(1.1, True)


# ---- 6. ConfidenceCalibration class --------------------------------------


class TestConfidenceCalibrationClass:
    def test_name_attribute(self):
        assert ConfidenceCalibration().name == "confidence_calibration"

    def test_class_invalid_n_bins(self):
        with pytest.raises(ValueError):
            ConfidenceCalibration(n_bins=0)

    def test_class_summarize_matches_module_functions(self):
        rows = (
            [_row(0.9, True)] * 3
            + [_row(0.9, False)] * 3
            + [_row(0.1, True)] * 1
            + [_row(0.1, False)] * 3
        )
        cc = ConfidenceCalibration(n_bins=10)
        summary = cc.summarize(rows)
        assert summary["ece"] == pytest.approx(
            compute_ece(rows, n_bins=10)
        )
        assert summary["n_cases"] == 10
        assert summary["mean_confidence"] == pytest.approx(
            (0.9 * 6 + 0.1 * 4) / 10
        )
        assert summary["mean_accuracy"] == pytest.approx(4 / 10)

    def test_class_summarize_on_empty_input(self):
        cc = ConfidenceCalibration(n_bins=10)
        summary = cc.summarize([])
        assert summary["n_cases"] == 0
        assert math.isnan(summary["ece"])
        assert math.isnan(summary["mean_confidence"])
        assert math.isnan(summary["mean_accuracy"])
        assert summary["overconfidence_bins"] == 0
        assert summary["underconfidence_bins"] == 0

    def test_per_fault_subsetting_preserves_ece(self):
        """The harness aggregates a per-fault row by subsetting the
        full row list to that fault and calling compute_ece on the
        subset. This test verifies the subset path equals the
        analytic ECE on that subset."""
        rows = (
            [_row(0.9, True, fault="cpu")] * 3
            + [_row(0.9, False, fault="cpu")] * 1
            + [_row(0.1, False, fault="mem")] * 4
        )
        cpu_subset = [r for r in rows if r["fault"] == "cpu"]
        mem_subset = [r for r in rows if r["fault"] == "mem"]
        # cpu bucket 9: conf 0.9 / acc 0.75 → gap 0.15, weight 1.0
        assert compute_ece(cpu_subset, n_bins=10) == pytest.approx(0.15)
        # mem bucket 1: conf 0.1 / acc 0.0 → gap 0.1, weight 1.0
        assert compute_ece(mem_subset, n_bins=10) == pytest.approx(0.10)
