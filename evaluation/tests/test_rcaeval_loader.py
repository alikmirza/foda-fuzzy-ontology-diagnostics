"""Tests for evaluation.benchmarks.rcaeval_loader."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import BenchmarkCase

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "rcaeval_fake"

# Real RE1 dataset on this machine — tests that depend on it are skipped
# automatically when the data is not present.
RE1_DEFAULT = Path(
    os.environ.get(
        "RCAEVAL_DATA_PATH", "~/research/rcaeval-tools/RCAEval/data/RE1/"
    )
).expanduser()
RE1_OB = RE1_DEFAULT / "RE1-OB"


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


# ---- nested RE1 layout (synthetic + real) ----


def _make_re1_ob_tree(root: Path, services=("adservice",), faults=("cpu",),
                     instances=(1, 2)) -> Path:
    """Build a minimal RE1-style tree at ``root/RE1-OB/...`` for unit
    tests that don't need the full RCAEval download."""
    ob = root / "RE1-OB"
    for svc in services:
        for fault in faults:
            for inst in instances:
                inst_dir = ob / f"{svc}_{fault}" / str(inst)
                _write_csv(
                    inst_dir / "data.csv",
                    [
                        {"time": 0, f"{svc}_cpu": 0.1},
                        {"time": 1, f"{svc}_cpu": 0.9},
                    ],
                )
                (inst_dir / "inject_time.txt").write_text("1700000000\n")
    return ob


def test_nested_layout_pointed_at_system_root(tmp_path: Path):
    ob = _make_re1_ob_tree(
        tmp_path,
        services=("adservice", "cartservice"),
        faults=("cpu", "mem"),
        instances=(1, 2, 3),
    )
    loader = RCAEvalLoader(ob)
    cases = list(loader.iter_cases())
    assert len(cases) == 2 * 2 * 3  # services × faults × instances
    ids = {c.id for c in cases}
    assert "re1-ob_adservice_cpu_1" in ids
    assert "re1-ob_cartservice_mem_3" in ids


def test_nested_layout_pointed_at_re1_root(tmp_path: Path):
    _make_re1_ob_tree(tmp_path)
    # Add a sibling system dir so we exercise the multi-system branch.
    ss_inst = tmp_path / "RE1-SS" / "carts_cpu" / "1"
    _write_csv(ss_inst / "data.csv", [{"time": 0, "carts_cpu": 0.1}])
    (ss_inst / "inject_time.txt").write_text("1700000050\n")

    loader = RCAEvalLoader(tmp_path)
    cases = {c.id: c for c in loader.iter_cases()}
    assert "re1-ob_adservice_cpu_1" in cases
    assert "re1-ss_carts_cpu_1" in cases
    assert cases["re1-ob_adservice_cpu_1"].telemetry["system"] == "online-boutique"
    assert cases["re1-ss_carts_cpu_1"].telemetry["system"] == "sock-shop"


def test_nested_case_fields_and_inject_time(tmp_path: Path):
    ob = _make_re1_ob_tree(tmp_path)
    loader = RCAEvalLoader(ob)
    case = loader.get_case("re1-ob_adservice_cpu_1")
    assert case.ground_truth_root_cause == "adservice"
    assert case.ground_truth_fault_type == "cpu"
    assert case.telemetry["system"] == "online-boutique"
    assert case.telemetry["inject_time"] == 1700000000.0
    df = case.telemetry["metrics"]
    assert "time" in df.columns
    assert len(df) == 2


def test_hyphenated_service_name_parses(tmp_path: Path):
    # RE1-TT uses names like ``ts-auth-service`` — the loader must keep
    # the hyphens in the service name and split only on the final ``_``.
    tt = tmp_path / "RE1-TT"
    inst = tt / "ts-auth-service_delay" / "1"
    _write_csv(inst / "data.csv", [{"time": 0, "x": 0.0}])
    (inst / "inject_time.txt").write_text("1700000123\n")

    loader = RCAEvalLoader(tt)
    case = loader.get_case("re1-tt_ts-auth-service_delay_1")
    assert case.ground_truth_root_cause == "ts-auth-service"
    assert case.ground_truth_fault_type == "delay"
    assert case.telemetry["system"] == "train-ticket"


def test_default_data_path_from_env(tmp_path: Path, monkeypatch):
    _make_re1_ob_tree(tmp_path)
    monkeypatch.setenv("RCAEVAL_DATA_PATH", str(tmp_path))
    loader = RCAEvalLoader()  # no explicit path
    assert loader.data_path == tmp_path
    assert any(c.id.startswith("re1-ob_") for c in loader.iter_cases())


# ---- real RE1-OB dataset (skipped if not present locally) ----


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_has_125_cases_with_valid_data_and_inject_time():
    """Loads the real RE1-OB dataset, asserts 125 cases, every case
    has a non-empty ``data.csv`` and a numeric ``inject_time``, and
    prints 3 samples with their metrics shapes."""
    loader = RCAEvalLoader(RE1_OB)
    cases = list(loader.iter_cases())
    assert len(cases) == 125, (
        f"expected 25 service-faults × 5 instances = 125 cases, got {len(cases)}"
    )

    fault_counts: dict[str, int] = {}
    for case in cases:
        df = case.telemetry["metrics"]
        assert isinstance(df, pd.DataFrame), f"{case.id}: metrics not a DataFrame"
        assert not df.empty, f"{case.id}: empty data.csv"
        assert "time" in df.columns, f"{case.id}: no 'time' column"
        assert "inject_time" in case.telemetry, f"{case.id}: missing inject_time"
        assert isinstance(case.telemetry["inject_time"], float)
        assert case.telemetry["system"] == "online-boutique"
        assert case.ground_truth_fault_type in {"cpu", "mem", "disk", "delay", "loss"}
        fault_counts[case.ground_truth_fault_type] = (
            fault_counts.get(case.ground_truth_fault_type, 0) + 1
        )

    # 5 services × 5 instances = 25 cases per fault type.
    assert fault_counts == {f: 25 for f in ("cpu", "mem", "disk", "delay", "loss")}

    # Surface 3 samples — visible with ``pytest -s``.
    samples = [cases[0], cases[len(cases) // 2], cases[-1]]
    print("\n--- RE1-OB sample cases ---")
    for c in samples:
        df = c.telemetry["metrics"]
        print(
            f"id={c.id:<40} service={c.ground_truth_root_cause:<25} "
            f"fault={c.ground_truth_fault_type:<6} "
            f"metrics_shape={df.shape} inject_time={c.telemetry['inject_time']}"
        )
