"""Tests for evaluation.benchmarks.foda12_loader."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.foda12_loader import Foda12Loader
from evaluation.extraction.canonical_explanation import BenchmarkCase

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "foda12_fake"

# Namespace declared in ontology/DiagnosticKB.owl.
NS = "http://foda.com/ontology/diagnostic#"


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
    # Ontology annotations use the real DiagnosticKB.owl namespace and
    # class names; healthy services are tagged with the base MicroService
    # class (there is no NormalOperation class).
    assert case.ontology_mapping == {
        "service-A": f"{NS}LatencySpike",
        "service-B": f"{NS}MicroService",
        "service-C": f"{NS}MicroService",
    }
    assert case.system_topology == {
        "service-A": ["service-B", "service-C"],
        "service-B": [],
        "service-C": [],
    }
    # Per-service time-series arrive as a {service: DataFrame} dict.
    metrics = case.telemetry["metrics"]
    assert isinstance(metrics, dict)
    assert set(metrics) == {"service-A", "service-B", "service-C"}
    df_a = metrics["service-A"]
    assert isinstance(df_a, pd.DataFrame)
    assert "latency_ms" in df_a.columns
    assert len(df_a) == 4


def test_get_case_s09_root_cause_class_is_cpu_saturation():
    loader = Foda12Loader(FIXTURE_ROOT)
    case = loader.get_case("S09")
    assert case.ground_truth_root_cause == "service-B"
    assert case.ground_truth_fault_type == "CPU_SATURATION"
    # Root-cause service must be annotated with the matching ontology class
    # — using the real OWL fragment CpuSaturation.
    assert (
        case.ontology_mapping[case.ground_truth_root_cause]
        == f"{NS}CpuSaturation"
    )
    # inject_time is now required on every case.
    assert case.telemetry["inject_time"] == 20.0


def test_get_case_unknown_id_raises():
    loader = Foda12Loader(FIXTURE_ROOT)
    with pytest.raises(KeyError):
        loader.get_case("S99")


def test_missing_data_path_raises():
    with pytest.raises(FileNotFoundError):
        Foda12Loader(FIXTURE_ROOT / "no_such_dir")


# ---- runtime fixtures: schema validation ----


def _write_case(
    case_dir: Path,
    case_json: dict,
    per_service_metrics: dict[str, list[dict]] | None = None,
) -> None:
    """Write a case directory with the per-service metrics layout.

    `per_service_metrics` maps service name → rows; defaults to one CSV
    per service in `case_json["ontology_mapping"]`.
    """
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "case.json").write_text(json.dumps(case_json))
    metrics_dir = case_dir / "metrics"
    metrics_dir.mkdir(exist_ok=True)
    if per_service_metrics is None:
        services = list(case_json.get("ontology_mapping", {}).keys())
        per_service_metrics = {s: [{"time": 0, "x": 0.0}] for s in services}
    for service, rows in per_service_metrics.items():
        pd.DataFrame(rows).to_csv(metrics_dir / f"{service}.csv", index=False)


def _valid_case_json(**overrides) -> dict:
    base = {
        "fault_type": "X",
        "ground_truth_root_cause": "svc",
        "ontology_mapping": {"svc": f"{NS}LatencySpike"},
        "inject_time": 100,
    }
    base.update(overrides)
    return base


def test_missing_required_key_raises(tmp_path: Path):
    bad = _valid_case_json()
    del bad["fault_type"]
    _write_case(tmp_path / "S01", bad)
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="fault_type"):
        loader.get_case("S01")


def test_missing_inject_time_raises(tmp_path: Path):
    bad = _valid_case_json()
    del bad["inject_time"]
    _write_case(tmp_path / "S01", bad)
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="inject_time"):
        loader.get_case("S01")


def test_missing_ontology_mapping_raises(tmp_path: Path):
    bad = _valid_case_json()
    del bad["ontology_mapping"]
    # Provide an empty metrics layout since ontology_mapping is gone.
    _write_case(tmp_path / "S01", bad, per_service_metrics={})
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="ontology_mapping"):
        loader.get_case("S01")


def test_empty_ontology_mapping_raises(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        _valid_case_json(ontology_mapping={}),
        per_service_metrics={},
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="non-empty"):
        loader.get_case("S01")


def test_root_cause_must_be_in_ontology_mapping(tmp_path: Path):
    _write_case(
        tmp_path / "S01",
        _valid_case_json(
            ground_truth_root_cause="svc-A",
            ontology_mapping={"svc-B": f"{NS}LatencySpike"},
        ),
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="root cause"):
        loader.get_case("S01")


def test_case_json_must_be_object(tmp_path: Path):
    case_dir = tmp_path / "S01"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(json.dumps([1, 2, 3]))
    (case_dir / "metrics").mkdir()
    pd.DataFrame({"time": [0]}).to_csv(
        case_dir / "metrics" / "svc.csv", index=False
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="JSON object"):
        loader.get_case("S01")


def test_metrics_dir_required(tmp_path: Path):
    case_dir = tmp_path / "S01"
    case_dir.mkdir()
    (case_dir / "case.json").write_text(json.dumps(_valid_case_json()))
    # No metrics/ directory on disk.
    loader = Foda12Loader(tmp_path)
    # Discovery skips this folder, so it's not an iter_cases result …
    assert list(loader) == []
    # … and get_case raises with a clear message.
    with pytest.raises(KeyError, match="metrics"):
        loader.get_case("S01")


def test_case_json_required(tmp_path: Path):
    case_dir = tmp_path / "S01"
    (case_dir / "metrics").mkdir(parents=True)
    pd.DataFrame({"time": [0]}).to_csv(
        case_dir / "metrics" / "svc.csv", index=False
    )
    loader = Foda12Loader(tmp_path)
    assert list(loader) == []
    with pytest.raises(KeyError, match="case.json"):
        loader.get_case("S01")


def test_optional_topology_can_be_omitted(tmp_path: Path):
    _write_case(tmp_path / "S01", _valid_case_json())
    loader = Foda12Loader(tmp_path)
    case = loader.get_case("S01")
    assert case.system_topology is None
    assert case.ontology_mapping == {"svc": f"{NS}LatencySpike"}


def test_metrics_must_match_ontology_mapping_services(tmp_path: Path):
    # ontology_mapping declares svc-A and svc-B but only svc-A has a CSV.
    case_json = _valid_case_json(
        ground_truth_root_cause="svc-A",
        ontology_mapping={
            "svc-A": f"{NS}LatencySpike",
            "svc-B": f"{NS}MicroService",
        },
    )
    _write_case(
        tmp_path / "S01",
        case_json,
        per_service_metrics={"svc-A": [{"time": 0, "x": 0.0}]},
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="svc-B"):
        loader.get_case("S01")


def test_metrics_extra_csv_rejected(tmp_path: Path):
    # An extra CSV not in ontology_mapping is also a malformed scenario.
    case_json = _valid_case_json()
    _write_case(
        tmp_path / "S01",
        case_json,
        per_service_metrics={
            "svc": [{"time": 0, "x": 0.0}],
            "ghost": [{"time": 0, "x": 0.0}],
        },
    )
    loader = Foda12Loader(tmp_path)
    with pytest.raises(ValueError, match="ghost"):
        loader.get_case("S01")
