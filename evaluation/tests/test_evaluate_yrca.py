"""Smoke test for the evaluate_yrca harness.

Mirrors ``test_evaluate_baro.py`` with two yRCA-specific checks:

* ``--with-random-onset`` emits ``AC@1_random``.
* ``--with-offset-robustness`` emits the five offset-robustness
  columns (``AC@1_a_standard``, ``AC@1_b_edge_left``,
  ``AC@1_b_edge_right``, ``AC@1_b_edges_mean``,
  ``AC@1_c_centered``) — the Paper 6 §4 standard reporting axis.

yRCA does not read ``ground_truth``, so ``S(yRCA) = 0`` is
structural and is asserted here on the fake fixture as well.
"""

from __future__ import annotations

import math
from pathlib import Path

from evaluation.experiments.evaluate_yrca import evaluate


FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def test_evaluate_runs_against_fake_fixture():
    summary, per_case = evaluate(FIXTURE, top_ks=(1, 3))
    assert "CPU" in summary
    assert "MEM" in summary
    assert "overall" in summary
    for row in summary.values():
        assert "AC@1" in row
        assert "AC@3" in row
        assert "MRR" in row
        assert "S" in row
        assert "S_flag" in row
        assert 0.0 <= row["AC@1"] <= 1.0
        assert row["n"] >= 1
    assert len(per_case) == int(summary["overall"]["n"])


def test_overall_aggregates_all_cases():
    summary, _ = evaluate(FIXTURE, top_ks=(1,))
    n_overall = summary["overall"]["n"]
    n_per_fault = sum(
        v["n"] for k, v in summary.items() if k != "overall"
    )
    assert n_overall == n_per_fault


def test_shift_invariance_on_clean_method():
    """``S(yRCA) = 0`` by construction (yRCA detects its own onset
    from ``case_window``) — assert it empirically on every case."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        for shifted in (row["AC@1_shift_minus"], row["AC@1_shift_plus"]):
            if math.isnan(shifted):
                continue
            assert shifted == row["AC@1"], (
                f"case {row['case_id']}: shifted AC@1 ({shifted}) "
                f"differs from true AC@1 ({row['AC@1']}); yRCA is "
                f"leaking inject_time"
            )
    overall = summary["overall"]
    if not math.isnan(overall["S"]):
        assert overall["S"] == 0.0
        assert overall["S_flag"] == 0.0


def test_with_random_onset_emits_decomposition_column():
    """Detector-vs-rule-engine decomposition: replace yRCA's
    :func:`detect_onset` with a uniformly-random in-band pivot."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,), with_random_onset=True)
    assert "AC@1_random" in summary["overall"]
    for row in per_case:
        assert "AC@1_random" in row
        assert 0.0 <= row["AC@1_random"] <= 1.0


def test_with_offset_robustness_emits_three_regimes():
    summary, per_case = evaluate(
        FIXTURE, top_ks=(1,), with_offset_robustness=True,
    )
    for col in (
        "AC@1_a_standard", "AC@1_b_edge_left", "AC@1_b_edge_right",
        "AC@1_b_edges_mean", "AC@1_c_centered",
    ):
        assert col in summary["overall"], col
        for row in per_case:
            assert col in row
            v = row[col]
            assert math.isnan(v) or 0.0 <= v <= 1.0


def test_without_optional_flags_omits_columns():
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        assert "AC@1_random" not in row
        assert "AC@1_a_standard" not in row
    for row in summary.values():
        assert "AC@1_random" not in row
        assert "AC@1_a_standard" not in row


def test_with_both_decompositions_emits_both():
    summary, per_case = evaluate(
        FIXTURE, top_ks=(1,),
        with_random_onset=True, with_offset_robustness=True,
    )
    for row in per_case:
        assert "AC@1_random" in row
        assert "AC@1_a_standard" in row
    for row in summary.values():
        assert "AC@1_random" in row
        assert "AC@1_a_standard" in row
