"""Smoke tests for the Phase 2 Week 2 SemanticCoherence harness."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from evaluation.experiments.run_phase2_sc import (
    _summarize,
    spearman,
    write_csv,
)


FIXTURE = Path(__file__).parent / "fixtures" / "rcaeval_fake"


def _fake_rows() -> list[dict[str, object]]:
    return [
        {"method": "FODA-FCP", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg": 1.0, "sc_overall": 1.0,
         "coherent_links": 5, "incoherent_links": 0,
         "unmapped_links": 0, "excluded_mitigation_links": 0,
         "scored_link_count": 5, "link_count": 5},
        {"method": "FODA-FCP", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg": 1.0, "sc_overall": 0.8,
         "coherent_links": 4, "incoherent_links": 1,
         "unmapped_links": 0, "excluded_mitigation_links": 0,
         "scored_link_count": 5, "link_count": 5},
        {"method": "MR", "case_id": "a", "fault": "cpu",
         "ac1": 1.0, "sg": 0.0, "sc_overall": 0.0,
         "coherent_links": 0, "incoherent_links": 0,
         "unmapped_links": 0, "excluded_mitigation_links": 0,
         "scored_link_count": 0, "link_count": 0},
        {"method": "MR", "case_id": "b", "fault": "mem",
         "ac1": 0.0, "sg": 0.0, "sc_overall": 0.0,
         "coherent_links": 0, "incoherent_links": 0,
         "unmapped_links": 0, "excluded_mitigation_links": 0,
         "scored_link_count": 0, "link_count": 0},
    ]


def test_summarize_per_method_aggregates():
    summary = _summarize(_fake_rows())
    assert "FODA-FCP" in summary and "MR" in summary
    assert summary["FODA-FCP"]["sc_mean"] == 0.9
    assert summary["MR"]["sc_mean"] == 0.0
    assert summary["FODA-FCP"]["sg_mean"] == 1.0


def test_summarize_per_fault_breakdown():
    summary = _summarize(_fake_rows())
    assert summary["FODA-FCP"]["sc_cpu"] == 1.0
    assert summary["FODA-FCP"]["sc_mem"] == 0.8


def test_spearman_perfect_positive():
    rows = [
        {"ac1": 0.0, "sc_overall": 0.1},
        {"ac1": 0.0, "sc_overall": 0.3},
        {"ac1": 1.0, "sc_overall": 0.5},
        {"ac1": 1.0, "sc_overall": 0.9},
    ]
    rho = spearman(rows, "ac1", "sc_overall")
    assert rho > 0.7


def test_spearman_constant_input_is_nan():
    rows = [
        {"ac1": 1.0, "sc_overall": 0.5},
        {"ac1": 1.0, "sc_overall": 0.7},
        {"ac1": 1.0, "sc_overall": 0.9},
    ]
    assert math.isnan(spearman(rows, "ac1", "sc_overall"))


def test_write_csv_round_trip(tmp_path):
    rows = _fake_rows()
    path = tmp_path / "sc.csv"
    write_csv(rows, path)
    with path.open() as fh:
        loaded = list(csv.DictReader(fh))
    assert len(loaded) == len(rows)
    assert set(loaded[0].keys()) == {
        "method", "case_id", "fault", "ac1", "sg", "sc_overall",
        "coherent_links", "incoherent_links", "unmapped_links",
        "excluded_mitigation_links", "scored_link_count", "link_count",
    }


def test_end_to_end_on_fake_fixture():
    """Tiny end-to-end run against the fake fixture (2 cases)."""
    from evaluation.experiments.run_phase2_sc import evaluate
    rows, summary = evaluate(FIXTURE)
    assert len(rows) == 14  # 7 methods × 2 cases
    for r in rows:
        assert 0.0 <= r["sc_overall"] <= 1.0
        assert (
            r["coherent_links"] + r["incoherent_links"]
            + r["unmapped_links"] + r["excluded_mitigation_links"]
            == r["link_count"]
        )
        assert (
            r["coherent_links"] + r["incoherent_links"] + r["unmapped_links"]
            == r["scored_link_count"]
        )
