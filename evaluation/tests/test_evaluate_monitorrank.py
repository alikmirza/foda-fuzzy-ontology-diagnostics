"""Smoke test for the evaluate_monitorrank harness.

The real validation run happens against the multi-GB RCAEval archive
(see the script's docstring); this just makes sure the harness can be
imported and runs end-to-end against the fake fixture.
"""

from __future__ import annotations

from pathlib import Path

from evaluation.experiments.evaluate_monitorrank import evaluate

FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def test_evaluate_runs_against_fake_fixture():
    summary = evaluate(FIXTURE, top_ks=(1, 3))
    # Two cases in the fixture (CPU and MEM) → two fault buckets plus overall.
    assert "CPU" in summary
    assert "MEM" in summary
    assert "overall" in summary
    for row in summary.values():
        assert "AC@1" in row
        assert "AC@3" in row
        assert "MRR" in row
        assert 0.0 <= row["AC@1"] <= 1.0
        assert row["n"] >= 1


def test_overall_aggregates_all_cases():
    summary = evaluate(FIXTURE, top_ks=(1,))
    n_overall = summary["overall"]["n"]
    n_per_fault = sum(
        v["n"] for k, v in summary.items() if k != "overall"
    )
    assert n_overall == n_per_fault
