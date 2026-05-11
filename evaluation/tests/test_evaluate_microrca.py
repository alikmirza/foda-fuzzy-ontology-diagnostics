"""Smoke test for the evaluate_microrca harness.

Mirrors ``test_evaluate_causalrca.py`` with an extra check that
``--with-collapsed-graph`` emits the attributed-graph-effect column.
"""

from __future__ import annotations

import math
from pathlib import Path

from evaluation.experiments.evaluate_microrca import evaluate

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
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        for shifted in (row["AC@1_shift_minus"], row["AC@1_shift_plus"]):
            if math.isnan(shifted):
                continue
            assert shifted == row["AC@1"], (
                f"case {row['case_id']}: shifted AC@1 ({shifted}) "
                f"differs from true AC@1 ({row['AC@1']}); MicroRCA "
                f"is leaking inject_time"
            )
    overall = summary["overall"]
    if not math.isnan(overall["S"]):
        assert overall["S"] == 0.0
        assert overall["S_flag"] == 0.0


def test_with_random_onset_emits_decomposition_column():
    summary, per_case = evaluate(FIXTURE, top_ks=(1,), with_random_onset=True)
    assert "AC@1_random" in summary["overall"]
    for row in per_case:
        assert "AC@1_random" in row
        assert 0.0 <= row["AC@1_random"] <= 1.0


def test_with_collapsed_graph_emits_attribute_effect_column():
    """The attributed-graph effect diagnostic (brief §9): AC@1 with
    the asymmetric graph replaced by a symmetric correlation graph.
    Required per-case so we can compute paired deltas, not just
    aggregate."""
    summary, per_case = evaluate(
        FIXTURE, top_ks=(1,), with_collapsed_graph=True
    )
    assert "AC@1_collapsed" in summary["overall"]
    for row in per_case:
        assert "AC@1_collapsed" in row
        assert 0.0 <= row["AC@1_collapsed"] <= 1.0


def test_without_optional_flags_omits_columns():
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        assert "AC@1_random" not in row
        assert "AC@1_collapsed" not in row
    for row in summary.values():
        assert "AC@1_random" not in row
        assert "AC@1_collapsed" not in row
