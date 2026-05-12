"""Smoke tests for the Phase 2 Week 1 SemanticGroundedness harness.

These tests exercise the aggregation, CSV writing, and Spearman code
path against the small fake RCAEval fixture so the harness shape is
verified without depending on the 125-case RE1-OB run. The end-to-end
RE1-OB run lives outside the test suite (it takes minutes; see
``run_phase2_sg.py`` CLI usage).
"""

from __future__ import annotations

import csv
from pathlib import Path

from evaluation.experiments.run_phase2_sg import (
    _summarize,
    spearman_ac1_vs_sg,
    write_csv,
)


FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def _fake_rows() -> list[dict[str, object]]:
    """Hand-written rows that exercise summarize + spearman without
    actually running every method."""
    return [
        {"method": "FODA-FCP", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg_overall": 1.0, "direct_matches": 4,
         "fuzzy_matches": 0, "unmatched": 0, "atom_count": 4},
        {"method": "FODA-FCP", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg_overall": 1.0, "direct_matches": 4,
         "fuzzy_matches": 0, "unmatched": 0, "atom_count": 4},
        {"method": "MR", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg_overall": 0.0, "direct_matches": 0,
         "fuzzy_matches": 0, "unmatched": 3, "atom_count": 3},
        {"method": "MR", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg_overall": 0.0, "direct_matches": 0,
         "fuzzy_matches": 0, "unmatched": 3, "atom_count": 3},
    ]


def test_summarize_per_method_aggregates():
    rows = _fake_rows()
    summary = _summarize(rows)
    assert "FODA-FCP" in summary
    assert "MR" in summary
    assert summary["FODA-FCP"]["sg_mean"] == 1.0
    assert summary["MR"]["sg_mean"] == 0.0
    assert summary["FODA-FCP"]["ac1_mean"] == 0.5
    assert summary["MR"]["ac1_mean"] == 0.5


def test_summarize_per_fault_breakdown():
    summary = _summarize(_fake_rows())
    assert summary["FODA-FCP"]["sg_cpu"] == 1.0
    assert summary["FODA-FCP"]["sg_mem"] == 1.0
    assert summary["MR"]["sg_cpu"] == 0.0


def test_spearman_constant_input_is_nan():
    """When one of the two ranked series is constant the rank
    correlation is undefined."""
    rows = [
        {"ac1": 1.0, "sg_overall": 0.5},
        {"ac1": 1.0, "sg_overall": 0.7},
        {"ac1": 1.0, "sg_overall": 0.9},
    ]
    import math
    assert math.isnan(spearman_ac1_vs_sg(rows))


def test_spearman_perfect_positive():
    rows = [
        {"ac1": 0.0, "sg_overall": 0.1},
        {"ac1": 0.0, "sg_overall": 0.3},
        {"ac1": 1.0, "sg_overall": 0.5},
        {"ac1": 1.0, "sg_overall": 0.9},
    ]
    rho = spearman_ac1_vs_sg(rows)
    # Two AC@1 groups; SG strictly increasing within and between.
    # Spearman should be strongly positive.
    assert rho > 0.7


def test_write_csv_round_trip(tmp_path):
    rows = _fake_rows()
    path = tmp_path / "sg.csv"
    write_csv(rows, path)
    with path.open() as fh:
        loaded = list(csv.DictReader(fh))
    assert len(loaded) == len(rows)
    assert set(loaded[0].keys()) == {
        "method", "case_id", "fault", "ac1", "sg_overall",
        "direct_matches", "fuzzy_matches", "unmatched", "atom_count",
    }


def test_end_to_end_on_fake_fixture():
    """Tiny end-to-end run against the fake fixture (2 cases) — verifies
    the integration between every method's diagnose() and the metric
    without depending on RE1-OB."""
    from evaluation.experiments.run_phase2_sg import evaluate
    rows, summary = evaluate(FIXTURE)
    # 7 methods × 2 fixture cases = 14 rows.
    assert len(rows) == 14
    methods = {r["method"] for r in rows}
    assert methods == {"MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP"}
    # SG in [0, 1] for every row.
    for r in rows:
        assert 0.0 <= r["sg_overall"] <= 1.0
    # FODA-FCP should hit 1.0 on every case where it produces atoms;
    # on the tiny fixture some methods produce no atoms and score 0.
    assert summary["FODA-FCP"]["sg_mean"] >= 0.5
