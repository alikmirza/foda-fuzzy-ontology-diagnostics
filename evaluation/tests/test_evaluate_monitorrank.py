"""Smoke test for the evaluate_monitorrank harness.

CHANGED: ``evaluate()`` now returns ``(summary, per_case_rows)`` instead
of just ``summary`` — the per-case rows are needed by the CSV writer
and by future inspection tools. Tests below unpack the tuple.

CHANGED (was passing on leakage): the per-fault summary now also
carries ``AC@1_shift_minus``, ``AC@1_shift_plus``, ``S`` and
``S_flag`` columns introduced by the inject-time-removal redesign. We
assert the new columns are present and that ``S ≈ 0`` on the fake
fixture (MonitorRank no longer reads ``inject_time``, so shifting it
must not move AC@1).
"""

from __future__ import annotations

import math
from pathlib import Path

from evaluation.experiments.evaluate_monitorrank import evaluate

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
    """MonitorRank doesn't read ``ground_truth.inject_time``, so the
    +/- 300 s shift must not move AC@1 for any case where the shifted
    offset stays in band. ``S`` ≈ 0 is the empirical witness of the
    protocol invariant."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    # Every case's shifted AC@1 (when defined) must equal the true
    # AC@1 — that's the inject_time-independence guarantee.
    for row in per_case:
        for shifted in (row["AC@1_shift_minus"], row["AC@1_shift_plus"]):
            if math.isnan(shifted):
                continue
            assert shifted == row["AC@1"], (
                f"case {row['case_id']}: shifted AC@1 ({shifted}) "
                f"differs from true AC@1 ({row['AC@1']}); MonitorRank "
                f"is leaking inject_time"
            )
    # Overall S must reflect that — strict zero, since the underlying
    # method is invariant by construction.
    overall = summary["overall"]
    if not math.isnan(overall["S"]):
        assert overall["S"] == 0.0
        assert overall["S_flag"] == 0.0
