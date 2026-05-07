"""Tests for evaluation.benchmarks.rcaeval_loader."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import BenchmarkCase

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rcaeval_fake"


# ---- against the committed fixture ----


def test_len_counts_two_cases():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    assert len(loader) == 2


def test_iter_cases_yields_benchmark_cases_in_sorted_order():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    cases = list(loader.iter_cases())
    assert [c.id for c in cases] == ["OB_cartservice_CPU_1", "SS_carts_MEM_2"]
    assert all(isinstance(c, BenchmarkCase) for c in cases)


def test_load_alias_matches_iter_cases():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    iterated = [c.id for c in loader]  # __iter__ -> load() -> iter_cases()
    assert iterated == [c.id for c in loader.iter_cases()]


def test_get_case_csv_with_inject_time():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    case = loader.get_case("OB_cartservice_CPU_1")
    assert case.id == "OB_cartservice_CPU_1"
    assert case.ground_truth_root_cause == "cartservice"
    assert case.ground_truth_fault_type == "CPU"
    assert case.telemetry["system"] == "online-boutique"
    assert case.telemetry["inject_time"] == 1700000020.0
    df = case.telemetry["metrics"]
    assert isinstance(df, pd.DataFrame)
    assert "time" in df.columns
    assert "cartservice_cpu" in df.columns
    assert len(df) == 5


def test_get_case_csv_without_inject_time():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    case = loader.get_case("SS_carts_MEM_2")
    assert case.ground_truth_root_cause == "carts"
    assert case.ground_truth_fault_type == "MEM"
    assert case.telemetry["system"] == "sock-shop"
    # No inject_time.txt in this fixture — key should be absent.
    assert "inject_time" not in case.telemetry
    df = case.telemetry["metrics"]
    assert len(df) == 4


def test_get_case_unknown_id_raises():
    loader = RCAEvalLoader(FIXTURE_ROOT)
    with pytest.raises(KeyError):
        loader.get_case("does_not_exist_FAULT_99")


def test_missing_data_path_raises():
    with pytest.raises(FileNotFoundError):
        RCAEvalLoader(FIXTURE_ROOT / "no_such_dir")


# ---- runtime-built fixtures (cover JSON + edge cases without committing
# extra files) ----


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def test_metrics_json_records_format(tmp_path: Path):
    case_dir = tmp_path / "TT_tsauthservice_DELAY_1"
    case_dir.mkdir()
    records = [
        {"time": 1, "tsauthservice_latency_ms": 50},
        {"time": 2, "tsauthservice_latency_ms": 120},
        {"time": 3, "tsauthservice_latency_ms": 800},
    ]
    (case_dir / "metrics.json").write_text(json.dumps(records))

    loader = RCAEvalLoader(tmp_path)
    case = loader.get_case("TT_tsauthservice_DELAY_1")
    assert case.ground_truth_root_cause == "tsauthservice"
    assert case.ground_truth_fault_type == "DELAY"
    assert case.telemetry["system"] == "train-ticket"
    df = case.telemetry["metrics"]
    assert list(df["time"]) == [1, 2, 3]
    assert df["tsauthservice_latency_ms"].iloc[-1] == 800


def test_metrics_json_columnar_format(tmp_path: Path):
    case_dir = tmp_path / "OB_frontend_LOSS_3"
    case_dir.mkdir()
    columnar = {"time": [1, 2], "frontend_err": [0.0, 0.5]}
    (case_dir / "metrics.json").write_text(json.dumps(columnar))

    loader = RCAEvalLoader(tmp_path)
    case = loader.get_case("OB_frontend_LOSS_3")
    df = case.telemetry["metrics"]
    assert list(df.columns) == ["time", "frontend_err"]
    assert df["frontend_err"].tolist() == [0.0, 0.5]


def test_directories_without_metrics_file_are_ignored(tmp_path: Path):
    # A real folder with metrics.
    good = tmp_path / "OB_currency_CPU_1"
    _write_csv(good / "simple_metrics.csv", [{"time": 1, "currency_cpu": 0.1}])
    # A sibling that looks like a case but has no metrics file.
    (tmp_path / "OB_payment_CPU_1").mkdir()
    # And a non-case-shaped directory.
    (tmp_path / "logs").mkdir()

    loader = RCAEvalLoader(tmp_path)
    assert len(loader) == 1
    assert [c.id for c in loader.iter_cases()] == ["OB_currency_CPU_1"]


def test_get_case_for_metricsless_dir_raises(tmp_path: Path):
    (tmp_path / "OB_payment_CPU_1").mkdir()
    loader = RCAEvalLoader(tmp_path)
    with pytest.raises(KeyError):
        loader.get_case("OB_payment_CPU_1")


def test_unknown_system_prefix_omits_system_field(tmp_path: Path):
    case_dir = tmp_path / "MYSET_someservice_CPU_1"
    _write_csv(case_dir / "data.csv", [{"time": 0, "x": 0}])
    loader = RCAEvalLoader(tmp_path)
    case = loader.get_case("MYSET_someservice_CPU_1")
    assert "system" not in case.telemetry
    assert case.ground_truth_root_cause == "someservice"


def test_dataset_then_system_prefix_resolves_system(tmp_path: Path):
    # E.g. RE1_SS_carts_cpu_1 — system is the second segment.
    case_dir = tmp_path / "RE1_SS_carts_cpu_1"
    _write_csv(case_dir / "data.csv", [{"time": 0, "carts_cpu": 0.1}])
    loader = RCAEvalLoader(tmp_path)
    case = loader.get_case("RE1_SS_carts_cpu_1")
    assert case.telemetry["system"] == "sock-shop"
    assert case.ground_truth_root_cause == "carts"
    assert case.ground_truth_fault_type == "cpu"


def test_malformed_case_id_raises(tmp_path: Path):
    case_dir = tmp_path / "tooshort"
    _write_csv(case_dir / "data.csv", [{"time": 0, "x": 0}])
    loader = RCAEvalLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.get_case("tooshort")


def test_non_numeric_instance_raises(tmp_path: Path):
    case_dir = tmp_path / "OB_cartservice_CPU_first"
    _write_csv(case_dir / "data.csv", [{"time": 0, "x": 0}])
    loader = RCAEvalLoader(tmp_path)
    with pytest.raises(ValueError):
        loader.get_case("OB_cartservice_CPU_first")
