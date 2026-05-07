"""Tests for evaluation.benchmarks.foda12_loader."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.foda12_loader import Foda12Loader
from evaluation.extraction.canonical_explanation import BenchmarkCase

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "foda12_fake"


# ---- against the committed fixture ----


def test_len_counts_two_cases():
    loader = Foda12Loader(FIXTURE_ROOT)
    assert len(loader) == 2


def test_iter_cases_sorted():
    loader = Foda12Loader(FIXTURE_ROOT)
    ids = [c.id for c in loader.iter_cases()]
    assert ids == ["S01", "S09"]
    assert all(isinstance(c, BenchmarkCase) for c in loader)


def test_get_case_s01_propagates_ontology_mapping():
    loader = Foda12Loader(FIXTURE_ROOT)
    case = loader.get_case("S01")
    assert case.ground_truth_root_cause == "service-A"
    assert case.ground_truth_fault_type == "LATENCY_ANOMALY"
    assert case.telemetry["scenario_name"] == "LATENCY_FANOUT"
    assert case.telemetry["inject_time"] == 1700000020.0
    # Critical: the FODA-12 ontology annotation flows through unchanged.
    assert case.ontology_mapping == {
        "service-A": "http://foda.example.org/onto#LatencyFault",
        "service-B": "http://foda.example.org/onto#NormalOperation",
        "service-C": "http://foda.example.org/onto#NormalOperation",
    }
    assert case.system_topology == {
        "service-A": ["service-B", "service-C"],
        "service-B": [],
        "service-C": [],
    }
    df = case.telemetry["metrics"]
    assert isinstance(df, pd.DataFrame)
    assert "service-A_latency_ms" in df.columns
    assert len(df) == 4


def test_get_case_s09_root_cause_class_is_cpu_saturation():
    loader = Foda12Loader(FIXTURE_ROOT)
    case = loader.get_case("S09")
    assert case.ground_truth_root_cause == "service-B"
    assert case.ground_truth_fault_type == "CPU_SATURATION"
    # Root-cause service must be annotated with the matching ontology class.
    assert (
        case.ontology_mapping[case.ground_truth_root_cause]
        == "http://foda.example.org/onto#CPUSaturation"
    )
    # No inject_time was provided in this case.
    assert "inject_time" not in case.telemetry


def test_get_case_unknown_id_raises():
    loader = Foda12Loader(FIXTURE_ROOT)
    with pytest.raises(KeyError):
        loader.get_case("S99")


def test_missing_data_path_raises():
    with pytest.raises(FileNotFoundError):
        Foda12Loader(FIXTURE_ROOT / "no_such_dir")


# ---- runtime fixtures: schema validation ----


def _write_case(
    case_dir: Path, case_json: dict, metrics_rows: list[dict] | None = None
) -> None:
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps(case_json))
    rows = metrics_rows or [{"time": 0, "x": 0.0}]
    pd.DataFrame(rows).to_csv(case_dir / "metrics.csv", index=False)


def test_missing_required_key_raises(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        {
            # 'fault_type' missing
            "ground_truth_root_cause": "svc",
            "ontology_mapping": {"svc": "http://example/x"},
        },
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="fault_type"):
        loader.get_case("S01")


def test_missing_ontology_mapping_raises(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        {
            "fault_type": "X",
            "ground_truth_root_cause": "svc",
            # 'ontology_mapping' missing
        },
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="ontology_mapping"):
        loader.get_case("S01")


def test_empty_ontology_mapping_raises(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        {
            "fault_type": "X",
            "ground_truth_root_cause": "svc",
            "ontology_mapping": {},
        },
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="non-empty"):
        loader.get_case("S01")


def test_root_cause_must_be_in_ontology_mapping(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        {
            "fault_type": "X",
            "ground_truth_root_cause": "svc-A",
            "ontology_mapping": {"svc-B": "http://example/x"},
        },
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="root cause"):
        loader.get_case("S01")


def test_case_json_must_be_object(tmp_path: Path):
    case_dir = tmp_path / "S01"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(json.dumps([1, 2, 3]))
    pd.DataFrame({"time": [0]}).to_csv(case_dir / "metrics.csv", index=False)
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="JSON object"):
        loader.get_case("S01")


def test_metrics_csv_required(tmp_path: Path):
    case_dir = tmp_path / "S01"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(
        json.dumps(
            {
                "fault_type": "X",
                "ground_truth_root_cause": "svc",
                "ontology_mapping": {"svc": "http://example/x"},
            }
        )
    )
    # No metrics.csv on disk.
    loader = Foda12Loader(tmp_path)
    # Discovery skips this folder, so it's not an iter_cases result …
    assert list(loader) == []
    # … and get_case raises with a clear message.
    with pytest.raises(KeyError, match="metrics.csv"):
        loader.get_case("S01")


def test_case_json_required(tmp_path: Path):
    case_dir = tmp_path / "S01"
    case_dir.mkdir()
    pd.DataFrame({"time": [0]}).to_csv(case_dir / "metrics.csv", index=False)
    loader = Foda12Loader(tmp_path)
    assert list(loader) == []
    with pytest.raises(KeyError, match="case.json"):
        loader.get_case("S01")


def test_optional_topology_can_be_omitted(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        {
            "fault_type": "X",
            "ground_truth_root_cause": "svc",
            "ontology_mapping": {"svc": "http://example/x"},
        },
    )
    loader = Foda12Loader(tmp_path)
    case = loader.get_case("S01")
    assert case.system_topology is None
    assert case.ontology_mapping == {"svc": "http://example/x"}
