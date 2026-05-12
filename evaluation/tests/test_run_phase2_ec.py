"""Smoke tests for the Phase 2 Week 3 ExplanationCompleteness harness."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from evaluation.experiments.run_phase2_ec import (
    _bucket_ec,
    _summarize,
    spearman,
    write_csv,
)


FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def _fake_rows() -> list[dict[str, object]]:
    return [
        {"method": "FODA-FCP", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg": 1.0, "sc": 0.5, "ec_overall": 1.0,
         "has_cause": 1, "has_component": 1, "has_mitigation": 1},
        {"method": "FODA-FCP", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg": 1.0, "sc": 0.3, "ec_overall": 1.0,
         "has_cause": 1, "has_component": 1, "has_mitigation": 1},
        {"method": "MR", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg": 0.0, "sc": 0.0, "ec_overall": 1.0 / 3.0,
         "has_cause": 0, "has_component": 1, "has_mitigation": 0},
        {"method": "MR", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg": 0.0, "sc": 0.0, "ec_overall": 1.0 / 3.0,
         "has_cause": 0, "has_component": 1, "has_mitigation": 0},
    ]


def test_summarize_per_method_aggregates():
    summary = _summarize(_fake_rows())
    assert "FODA-FCP" in summary and "MR" in summary
    assert summary["FODA-FCP"]["ec_mean"] == 1.0
    assert summary["MR"]["ec_mean"] == 1.0 / 3.0
    assert summary["FODA-FCP"]["frac_mitigation"] == 1.0
    assert summary["MR"]["frac_mitigation"] == 0.0


def test_summarize_per_category_fractions():
    summary = _summarize(_fake_rows())
    assert summary["FODA-FCP"]["frac_cause"] == 1.0
    assert summary["FODA-FCP"]["frac_component"] == 1.0
    assert summary["FODA-FCP"]["frac_mitigation"] == 1.0
    assert summary["MR"]["frac_cause"] == 0.0
    assert summary["MR"]["frac_component"] == 1.0


def test_summarize_ec_bucket_counts():
    summary = _summarize(_fake_rows())
    assert int(summary["FODA-FCP"]["n_at_1"]) == 2
    assert int(summary["FODA-FCP"]["n_at_0"]) == 0
    assert int(summary["MR"]["n_at_one_third"]) == 2
    assert int(summary["MR"]["n_at_1"]) == 0


def test_bucket_ec_snaps_to_canonical_values():
    assert _bucket_ec(0.0) == 0.0
    assert _bucket_ec(1.0 / 3.0) == 1.0 / 3.0
    assert _bucket_ec(2.0 / 3.0) == 2.0 / 3.0
    assert _bucket_ec(1.0) == 1.0
    # Floating-point drift snaps to the nearest bucket.
    assert _bucket_ec(0.33333333333333331) == 1.0 / 3.0
    assert _bucket_ec(0.66666666666666663) == 2.0 / 3.0


def test_spearman_perfect_positive():
    rows = [
        {"ac1": 0.0, "ec_overall": 0.1},
        {"ac1": 0.0, "ec_overall": 0.3},
        {"ac1": 1.0, "ec_overall": 0.5},
        {"ac1": 1.0, "ec_overall": 0.9},
    ]
    rho = spearman(rows, "ac1", "ec_overall")
    assert rho > 0.7


def test_spearman_constant_input_is_nan():
    rows = [
        {"ac1": 1.0, "ec_overall": 0.5},
        {"ac1": 1.0, "ec_overall": 0.7},
        {"ac1": 1.0, "ec_overall": 0.9},
    ]
    assert math.isnan(spearman(rows, "ac1", "ec_overall"))


def test_write_csv_round_trip(tmp_path):
    rows = _fake_rows()
    path = tmp_path / "ec.csv"
    write_csv(rows, path)
    with path.open() as fh:
        loaded = list(csv.DictReader(fh))
    assert len(loaded) == len(rows)
    assert set(loaded[0].keys()) == {
        "method", "case_id", "fault", "ac1", "sg", "sc",
        "ec_overall", "has_cause", "has_component", "has_mitigation",
    }


def test_end_to_end_on_fake_fixture():
    """Tiny end-to-end run against the fake fixture (2 cases × 7 methods)."""
    from evaluation.experiments.run_phase2_ec import evaluate
    rows, summary = evaluate(FIXTURE)
    assert len(rows) == 14
    for r in rows:
        assert 0.0 <= r["ec_overall"] <= 1.0
        assert r["has_cause"] + r["has_component"] + r["has_mitigation"] in (0, 1, 2, 3)
