"""Smoke test for the evaluate_baro harness.

Mirrors ``test_evaluate_microrca.py`` with two BARO-specific checks:

* ``--with-random-onset`` emits ``AC@1_random``.
* ``--with-zscore-onset`` emits ``AC@1_zscore_onset`` — the brief §9
  change-point-detector comparison column.

BARO does not read ``ground_truth``, so ``S(BARO) = 0`` is structural
and is asserted here on the fake fixture as well.
"""

from __future__ import annotations

import math
from pathlib import Path

from evaluation.experiments.evaluate_baro import evaluate

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
    """``S(BARO) = 0`` by construction (BARO does its own change-point
    detection from the data) — assert it empirically on every case."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        for shifted in (row["AC@1_shift_minus"], row["AC@1_shift_plus"]):
            if math.isnan(shifted):
                continue
            assert shifted == row["AC@1"], (
                f"case {row['case_id']}: shifted AC@1 ({shifted}) "
                f"differs from true AC@1 ({row['AC@1']}); BARO is "
                f"leaking inject_time"
            )
    overall = summary["overall"]
    if not math.isnan(overall["S"]):
        assert overall["S"] == 0.0
        assert overall["S_flag"] == 0.0


def test_with_random_onset_emits_decomposition_column():
    """Detector-vs-scoring decomposition: replace BARO's BOCPD with a
    uniformly-random in-band pivot."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,), with_random_onset=True)
    assert "AC@1_random" in summary["overall"]
    for row in per_case:
        assert "AC@1_random" in row
        assert 0.0 <= row["AC@1_random"] <= 1.0


def test_with_zscore_onset_emits_detector_comparison_column():
    """Brief §9 change-point-detector comparison: replace BARO's BOCPD
    with the shared z-score :func:`detect_onset` utility, keep BARO's
    scoring mechanism."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,), with_zscore_onset=True)
    assert "AC@1_zscore_onset" in summary["overall"]
    for row in per_case:
        assert "AC@1_zscore_onset" in row
        assert 0.0 <= row["AC@1_zscore_onset"] <= 1.0


def test_without_optional_flags_omits_columns():
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        assert "AC@1_random" not in row
        assert "AC@1_zscore_onset" not in row
    for row in summary.values():
        assert "AC@1_random" not in row
        assert "AC@1_zscore_onset" not in row


def test_with_both_decompositions_emits_both_columns():
    summary, per_case = evaluate(
        FIXTURE, top_ks=(1,),
        with_random_onset=True, with_zscore_onset=True,
    )
    for row in per_case:
        assert "AC@1_random" in row
        assert "AC@1_zscore_onset" in row
    for row in summary.values():
        assert "AC@1_random" in row
        assert "AC@1_zscore_onset" in row
