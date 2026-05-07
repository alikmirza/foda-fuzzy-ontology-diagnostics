"""Tests for evaluation.metrics.ranking_metrics."""

from __future__ import annotations

import pytest

from evaluation.metrics.ranking_metrics import (
    accuracy_at_k,
    mean_reciprocal_rank,
)


# ---------- accuracy_at_k ----------


def test_ac_at_1_top_match():
    ranked = [("svc-a", 0.9), ("svc-b", 0.5), ("svc-c", 0.1)]
    assert accuracy_at_k(ranked, "svc-a", 1) is True


def test_ac_at_1_not_top():
    ranked = [("svc-a", 0.9), ("svc-b", 0.5), ("svc-c", 0.1)]
    assert accuracy_at_k(ranked, "svc-b", 1) is False


def test_ac_at_3_in_top_3():
    ranked = [("a", 0.9), ("b", 0.5), ("c", 0.4), ("d", 0.1)]
    assert accuracy_at_k(ranked, "c", 3) is True


def test_ac_at_3_outside_top_3():
    ranked = [("a", 0.9), ("b", 0.5), ("c", 0.4), ("d", 0.1)]
    assert accuracy_at_k(ranked, "d", 3) is False


def test_ac_at_k_empty_list():
    assert accuracy_at_k([], "a", 1) is False
    assert accuracy_at_k([], "a", 5) is False


def test_ac_at_k_ground_truth_missing():
    ranked = [("a", 0.9), ("b", 0.5)]
    assert accuracy_at_k(ranked, "z", 1) is False
    assert accuracy_at_k(ranked, "z", 10) is False


def test_ac_at_k_invalid_k():
    ranked = [("a", 0.9)]
    with pytest.raises(ValueError):
        accuracy_at_k(ranked, "a", 0)
    with pytest.raises(ValueError):
        accuracy_at_k(ranked, "a", -1)


def test_ac_at_k_with_ties_uses_worst_rank():
    # Three services tied at 0.5 in ranks 1-3. Ground truth is the
    # tied entry — the conservative rank is 3, so AC@1 and AC@2 are
    # False but AC@3 is True.
    ranked = [("a", 0.5), ("b", 0.5), ("c", 0.5), ("d", 0.1)]
    assert accuracy_at_k(ranked, "a", 1) is False
    assert accuracy_at_k(ranked, "a", 2) is False
    assert accuracy_at_k(ranked, "a", 3) is True


def test_ac_at_k_tie_only_after_truth_counts():
    # Ties that come before the truth do not change its rank.
    ranked = [("a", 0.9), ("b", 0.9), ("gt", 0.7), ("c", 0.7)]
    # gt is at index 2 (rank 3); c also has 0.7, so worst tied rank is 4.
    assert accuracy_at_k(ranked, "gt", 3) is False
    assert accuracy_at_k(ranked, "gt", 4) is True


def test_ac_at_k_singleton():
    assert accuracy_at_k([("a", 1.0)], "a", 1) is True
    assert accuracy_at_k([("a", 1.0)], "b", 1) is False


# ---------- mean_reciprocal_rank ----------


def test_mrr_top():
    ranked = [("a", 0.9), ("b", 0.5)]
    assert mean_reciprocal_rank(ranked, "a") == 1.0


def test_mrr_second():
    ranked = [("a", 0.9), ("b", 0.5)]
    assert mean_reciprocal_rank(ranked, "b") == pytest.approx(0.5)


def test_mrr_third():
    ranked = [("a", 0.9), ("b", 0.5), ("c", 0.1)]
    assert mean_reciprocal_rank(ranked, "c") == pytest.approx(1.0 / 3.0)


def test_mrr_empty_list():
    assert mean_reciprocal_rank([], "a") == 0.0


def test_mrr_ground_truth_missing():
    ranked = [("a", 0.9), ("b", 0.5)]
    assert mean_reciprocal_rank(ranked, "z") == 0.0


def test_mrr_with_ties_uses_worst_rank():
    ranked = [("a", 0.5), ("b", 0.5), ("c", 0.5), ("d", 0.1)]
    # Conservative rank for any of the three tied entries is 3.
    assert mean_reciprocal_rank(ranked, "a") == pytest.approx(1.0 / 3.0)
    assert mean_reciprocal_rank(ranked, "b") == pytest.approx(1.0 / 3.0)
    assert mean_reciprocal_rank(ranked, "c") == pytest.approx(1.0 / 3.0)


def test_mrr_no_tie_after_truth():
    # Truth at rank 2 with no following tie -> 1/2.
    ranked = [("a", 0.9), ("gt", 0.5), ("c", 0.1)]
    assert mean_reciprocal_rank(ranked, "gt") == pytest.approx(0.5)
