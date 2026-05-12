"""Smoke tests for the evaluate_foda_fcp harness.

Mirrors ``test_evaluate_yrca.py`` with FODA-FCP-specific assertions:

* ``--with-random-onset`` emits ``AC@1_random``.
* ``--with-offset-robustness`` emits the five offset-robustness
  columns.
* ``append_offset_diagnostic_csv`` appends method-labeled rows to the
  shared cross-method diagnostic CSV in the expected column order.

FODA-FCP does not read ``ground_truth``, so ``S(FODA-FCP) = 0`` is
structural and is asserted here on the fake fixture as well.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from evaluation.experiments.evaluate_foda_fcp import (
    append_offset_diagnostic_csv,
    evaluate,
    write_per_case_csv,
)


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
    """``S(FODA-FCP) = 0`` by construction (the adapter detects its own
    onset from ``case_window``) — assert it empirically on every
    case."""
    summary, per_case = evaluate(FIXTURE, top_ks=(1,))
    for row in per_case:
        for shifted in (row["AC@1_shift_minus"], row["AC@1_shift_plus"]):
            if math.isnan(shifted):
                continue
            assert shifted == row["AC@1"], (
                f"case {row['case_id']}: shifted AC@1 ({shifted}) "
                f"differs from true AC@1 ({row['AC@1']}); FODA-FCP "
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


def test_append_offset_diagnostic_csv(tmp_path: Path):
    """``append_offset_diagnostic_csv`` writes a row per case in the
    shared cross-method-diagnostic schema."""
    _, per_case = evaluate(FIXTURE, top_ks=(1,), with_offset_robustness=True)
    csv_path = tmp_path / "cross_method_offset_diagnostic.csv"
    append_offset_diagnostic_csv(per_case, csv_path, method_label="FODA-FCP")

    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == len(per_case)
    assert all(r["method"] == "FODA-FCP" for r in rows)
    for r in rows:
        for col in ("AC@1_a_standard", "AC@1_b_edge_left",
                    "AC@1_b_edge_right", "AC@1_b_edges_mean",
                    "AC@1_c_centered"):
            assert col in r


def test_append_offset_diagnostic_preserves_existing_rows(tmp_path: Path):
    """Appending to a non-empty CSV keeps previous rows intact and does
    NOT re-emit the header. This is the key contract for joining
    FODA-FCP rows to the existing six-method cross-method CSV."""
    csv_path = tmp_path / "cross.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "method", "case_id", "fault", "ground_truth",
            "AC@1_a_standard", "AC@1_b_edge_left", "AC@1_b_edge_right",
            "AC@1_b_edges_mean", "AC@1_c_centered",
        ])
        w.writeheader()
        w.writerow({
            "method": "MR", "case_id": "x", "fault": "cpu",
            "ground_truth": "svc", "AC@1_a_standard": 1.0,
            "AC@1_b_edge_left": 0.0, "AC@1_b_edge_right": 1.0,
            "AC@1_b_edges_mean": 0.5, "AC@1_c_centered": 1.0,
        })

    _, per_case = evaluate(FIXTURE, top_ks=(1,), with_offset_robustness=True)
    append_offset_diagnostic_csv(per_case, csv_path)

    with csv_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["method"] == "MR"
    assert any(r["method"] == "FODA-FCP" for r in rows)
    assert len(rows) == 1 + len(per_case)
