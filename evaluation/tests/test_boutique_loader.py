"""Tests for evaluation.benchmarks.boutique_loader."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.boutique_loader import BoutiqueLoader
from evaluation.extraction.canonical_explanation import BenchmarkCase

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "boutique_fake"
RCAEVAL_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rcaeval_fake"


# ---- against the committed boutique fixture ----


def test_len_counts_two_cases():
    loader = BoutiqueLoader(FIXTURE_ROOT)
    assert len(loader) == 2


def test_iter_cases_sorted():
    loader = BoutiqueLoader(FIXTURE_ROOT)
    ids = [c.id for c in loader.iter_cases()]
    assert ids == ["OB_frontend_LATENCY_2", "cart_cpu_chaos_001"]
    assert all(isinstance(c, BenchmarkCase) for c in loader)


def test_manifest_overrides_directory_name():
    """The manifest case has a non-RCAEval-style folder name; ground truth
    must come from manifest.json, not from parsing the directory."""
    loader = BoutiqueLoader(FIXTURE_ROOT)
    case = loader.get_case("cart_cpu_chaos_001")
    assert case.ground_truth_root_cause == "cartservice"
    assert case.ground_truth_fault_type == "cpu_throttle"
    assert case.system_topology["frontend"] == [
        "cartservice",
        "productcatalogservice",
    ]
    assert case.telemetry["inject_time"] == 1700000020.0
    df = case.telemetry["metrics"]
    assert "cartservice_cpu" in df.columns
    assert len(df) == 4


def test_directory_name_fallback_with_per_service_csvs():
    """When no manifest is present, parse the dir name like RCAEval; and
    when there's no combined CSV, merge per-service CSVs on `time`."""
    loader = BoutiqueLoader(FIXTURE_ROOT)
    case = loader.get_case("OB_frontend_LATENCY_2")
    assert case.ground_truth_root_cause == "frontend"
    assert case.ground_truth_fault_type == "LATENCY"
    assert case.system_topology is None
    df = case.telemetry["metrics"]
    # Merge of frontend_metrics.csv (latency, qps) and cartservice_metrics.csv
    # (latency, qps) on `time`.
    assert set(df.columns) == {
        "time",
        "frontend_latency_ms",
        "frontend_qps",
        "cartservice_latency_ms",
        "cartservice_qps",
    }
    assert len(df) == 3
    # `time` should be sorted ascending after merge.
    assert list(df["time"]) == sorted(df["time"])


def test_get_case_unknown_id_raises():
    loader = BoutiqueLoader(FIXTURE_ROOT)
    with pytest.raises(KeyError):
        loader.get_case("nope_FAULT_99")


def test_missing_data_path_raises():
    with pytest.raises(FileNotFoundError):
        BoutiqueLoader(FIXTURE_ROOT / "no_such_dir")


# ---- reusing RCAEval fixtures (the user explicitly wants this) ----


def test_rcaeval_fixture_loads_through_boutique_loader():
    loader = BoutiqueLoader(RCAEVAL_FIXTURE_ROOT)
    assert len(loader) == 2
    case = loader.get_case("OB_cartservice_CPU_1")
    assert case.ground_truth_root_cause == "cartservice"
    assert case.ground_truth_fault_type == "CPU"


# ---- runtime fixtures (manifest validation, edge cases) ----


def test_manifest_missing_keys_raises(tmp_path: Path):
    case_dir = tmp_path / "case-A"
    case_dir.mkdir()
    (case_dir / "manifest.json").write_text(json.dumps({"root_cause": "x"}))
    pd.DataFrame({"time": [0], "x_cpu": [0.1]}).to_csv(
        case_dir / "data.csv", index=False
    )
    loader = BoutiqueLoader(tmp_path)
    with pytest.raises(ValueError, match="fault_type"):
        loader.get_case("case-A")


def test_manifest_must_be_object(tmp_path: Path):
    case_dir = tmp_path / "case-B"
    case_dir.mkdir()
    (case_dir / "manifest.json").write_text(json.dumps(["not", "an", "object"]))
    pd.DataFrame({"time": [0], "x_cpu": [0.1]}).to_csv(
        case_dir / "data.csv", index=False
    )
    loader = BoutiqueLoader(tmp_path)
    with pytest.raises(ValueError, match="JSON object"):
        loader.get_case("case-B")


def test_combined_csv_takes_priority_over_per_service(tmp_path: Path):
    case_dir = tmp_path / "OB_x_CPU_1"
    case_dir.mkdir()
    pd.DataFrame({"time": [0, 1], "combined_metric": [1.0, 2.0]}).to_csv(
        case_dir / "simple_metrics.csv", index=False
    )
    pd.DataFrame({"time": [0, 1], "x_metric": [9.0, 9.0]}).to_csv(
        case_dir / "x_metrics.csv", index=False
    )
    loader = BoutiqueLoader(tmp_path)
    df = loader.get_case("OB_x_CPU_1").telemetry["metrics"]
    assert "combined_metric" in df.columns
    assert "x_metric" not in df.columns


def test_per_service_csv_must_have_time_column(tmp_path: Path):
    case_dir = tmp_path / "OB_x_CPU_1"
    case_dir.mkdir()
    # No `time` column on at least one of the per-service CSVs.
    pd.DataFrame({"value": [1.0, 2.0]}).to_csv(
        case_dir / "x_metrics.csv", index=False
    )
    loader = BoutiqueLoader(tmp_path)
    with pytest.raises(ValueError, match="time"):
        loader.get_case("OB_x_CPU_1")


def test_directory_without_metrics_or_manifest_is_ignored(tmp_path: Path):
    (tmp_path / "empty_case").mkdir()
    good = tmp_path / "OB_x_CPU_1"
    good.mkdir()
    pd.DataFrame({"time": [0]}).to_csv(good / "data.csv", index=False)
    loader = BoutiqueLoader(tmp_path)
    assert [c.id for c in loader.iter_cases()] == ["OB_x_CPU_1"]


def test_dir_name_fallback_rejects_malformed(tmp_path: Path):
    case_dir = tmp_path / "two_segments"
    case_dir.mkdir()
    pd.DataFrame({"time": [0]}).to_csv(case_dir / "data.csv", index=False)
    loader = BoutiqueLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.get_case("two_segments")
