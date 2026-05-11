"""Tests for evaluation.extraction.schema_normalizer."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import BenchmarkCase
from evaluation.extraction.schema_normalizer import (
    DEFAULT_WINDOW_SECONDS,
    NormalizedCase,
    normalize_case,
    parse_service_list,
)


# ---- synthetic fixtures ----


def _make_case(
    df: pd.DataFrame,
    inject_time: float,
    case_id: str = "synthetic_1",
    fault_type: str = "cpu",
    root_cause: str = "svc-a",
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        telemetry={"metrics": df, "inject_time": inject_time},
        ground_truth_root_cause=root_cause,
        ground_truth_fault_type=fault_type,
        system_topology=None,
    )


def _short_pipeline_df(
    n_rows: int = 721,
    start: int = 1_000_000,
    services: tuple[str, ...] = ("svc-a", "svc-b"),
) -> pd.DataFrame:
    """Mimic the disk/delay/loss schema: percentile latencies, workload."""
    times = np.arange(start, start + n_rows, dtype=float)
    cols: dict[str, np.ndarray] = {"time": times}
    for svc in services:
        cols[f"{svc}_latency-50"] = np.full(n_rows, 0.05)
        cols[f"{svc}_latency-90"] = np.full(n_rows, 0.10)
        cols[f"{svc}_workload"] = np.full(n_rows, 100.0)
        cols[f"{svc}_cpu"] = np.full(n_rows, 0.30)
        cols[f"{svc}_mem"] = np.full(n_rows, 0.40)
    cols["frontend_error"] = np.zeros(n_rows)
    cols["frontend-external_error"] = np.zeros(n_rows)
    cols["frontend-external_workload"] = np.full(n_rows, 200.0)
    return pd.DataFrame(cols)


def _long_pipeline_df(
    n_rows: int = 4201,
    start: int = 2_000_000,
    services: tuple[str, ...] = ("svc-a", "svc-b"),
) -> pd.DataFrame:
    """Mimic the cpu/mem schema: mean latency, load, PassthroughCluster,
    and the spurious ``time.1`` duplicate."""
    times = np.arange(start, start + n_rows, dtype=float)
    cols: dict[str, np.ndarray] = {"time": times}
    for svc in services:
        cols[f"{svc}_latency"] = np.full(n_rows, 0.07)
        cols[f"{svc}_load"] = np.full(n_rows, 150.0)
        cols[f"{svc}_cpu"] = np.full(n_rows, 0.55)
        cols[f"{svc}_mem"] = np.full(n_rows, 0.65)
    cols["frontend_error"] = np.zeros(n_rows)
    cols["frontend-external_error"] = np.zeros(n_rows)
    cols["frontend-external_load"] = np.full(n_rows, 250.0)
    cols["PassthroughCluster_error"] = np.zeros(n_rows)
    cols["PassthroughCluster_load"] = np.full(n_rows, 50.0)
    cols["time.1"] = times  # join artifact
    return pd.DataFrame(cols)


# ---- parse_service_list ----


def test_parse_service_list_short_pipeline():
    df = _short_pipeline_df(services=("svc-a", "svc-b"))
    # 'frontend' is a real service (frontend_error); 'frontend-external'
    # is excluded by convention.
    assert parse_service_list(df) == ["frontend", "svc-a", "svc-b"]


def test_parse_service_list_long_pipeline_excludes_passthrough():
    df = _long_pipeline_df(services=("svc-a", "svc-b"))
    assert "PassthroughCluster" not in parse_service_list(df)
    assert "frontend-external" not in parse_service_list(df)
    assert set(parse_service_list(df)) >= {"svc-a", "svc-b", "frontend"}


def test_parse_service_list_keeps_hyphenated_names():
    df = pd.DataFrame(
        {"time": [0, 1], "ts-auth-service_cpu": [0.1, 0.2]}
    )
    assert parse_service_list(df) == ["ts-auth-service"]


def test_parse_service_list_accepts_benchmark_case():
    case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
    assert "svc-a" in parse_service_list(case)


def test_parse_service_list_ignores_time_columns():
    df = pd.DataFrame(
        {"time": [0, 1], "time.1": [0, 1], "svc-a_cpu": [0.1, 0.2]}
    )
    assert parse_service_list(df) == ["svc-a"]


def test_parse_service_list_rejects_non_dataframe_non_case():
    with pytest.raises(TypeError):
        parse_service_list("not a frame")  # type: ignore[arg-type]


# ---- normalize_case: column derivation ----


def test_short_case_latency_uses_p50():
    """When only ``_latency-50`` / ``_latency-90`` exist, the canonical
    ``_latency`` is the p50 proxy."""
    df = _short_pipeline_df()
    case = _make_case(df, inject_time=1_000_360.0)
    norm = normalize_case(case)

    assert "svc-a_latency" in norm.metrics.columns
    # All values come from latency-50 (= 0.05), not latency-90 (= 0.10).
    assert np.allclose(norm.metrics["svc-a_latency"].to_numpy(), 0.05)


def test_short_case_traffic_uses_workload():
    case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
    norm = normalize_case(case)
    assert "svc-a_traffic" in norm.metrics.columns
    assert np.allclose(norm.metrics["svc-a_traffic"].to_numpy(), 100.0)


def test_long_case_latency_uses_mean_column():
    case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
    norm = normalize_case(case)
    assert "svc-a_latency" in norm.metrics.columns
    assert np.allclose(norm.metrics["svc-a_latency"].to_numpy(), 0.07)


def test_long_case_traffic_prefers_load_over_workload():
    """When both ``_load`` and ``_workload`` exist, ``_load`` wins."""
    df = _long_pipeline_df()
    df["svc-a_workload"] = 999.0  # add a spurious workload column
    case = _make_case(df, inject_time=2_002_100.0)
    norm = normalize_case(case)
    # Should still be 150.0 from _load, not 999.0 from _workload.
    assert np.allclose(norm.metrics["svc-a_traffic"].to_numpy(), 150.0)


def test_latency_prefers_mean_over_p50_when_both_present():
    df = _short_pipeline_df()
    df["svc-a_latency"] = 0.42  # add canonical column
    case = _make_case(df, inject_time=1_000_360.0)
    norm = normalize_case(case)
    assert np.allclose(norm.metrics["svc-a_latency"].to_numpy(), 0.42)


def test_latency_falls_through_to_p90_only():
    df = pd.DataFrame(
        {
            "time": np.arange(100, dtype=float),
            "svc-a_latency-90": np.full(100, 0.99),
        }
    )
    case = _make_case(df, inject_time=50.0)
    norm = normalize_case(case)
    assert np.allclose(norm.metrics["svc-a_latency"].to_numpy(), 0.99)
    assert norm.schema_summary["latency"] == ["svc-a"]


def test_time_dot_one_dropped():
    df = _long_pipeline_df()
    assert "time.1" in df.columns  # sanity: it was in the raw input
    case = _make_case(df, inject_time=2_002_100.0)
    norm = normalize_case(case)
    assert "time.1" not in norm.metrics.columns


def test_resource_columns_passed_through():
    case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
    norm = normalize_case(case)
    assert "svc-a_cpu" in norm.metrics.columns
    assert "svc-a_mem" in norm.metrics.columns
    assert np.allclose(norm.metrics["svc-a_cpu"].to_numpy(), 0.55)


def test_error_column_passed_through_under_service_prefix():
    case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
    norm = normalize_case(case)
    # 'frontend' is a service with an error column.
    assert "frontend_error" in norm.metrics.columns


# ---- normalize_case: schema_summary ----


def test_schema_summary_lists_populated_features():
    case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
    norm = normalize_case(case)
    s = norm.schema_summary
    assert "svc-a" in s["latency"] and "svc-b" in s["latency"]
    assert "svc-a" in s["traffic"]
    assert "frontend" in s["error"]
    assert "svc-a" in s["cpu"]
    # No disk / net columns were synthesized in the fixture.
    assert s["disk"] == []
    assert s["net"] == []


def test_schema_summary_keys_always_present():
    """Every canonical feature key must be in the summary, even when no
    service populates it (so callers can iterate without ``KeyError``)."""
    case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
    norm = normalize_case(case)
    for key in ("latency", "traffic", "error", "cpu", "mem", "disk", "net"):
        assert key in norm.schema_summary


def test_schema_summary_service_lists_are_sorted():
    df = _short_pipeline_df(services=("zzz-svc", "aaa-svc", "mmm-svc"))
    case = _make_case(df, inject_time=1_000_360.0)
    norm = normalize_case(case)
    assert norm.schema_summary["latency"] == sorted(norm.schema_summary["latency"])


# ---- normalize_case: windowing ----


def test_window_size_is_2W_plus_1_for_long_case():
    """For a case fully inside the raw data, the window is exactly
    2*window_seconds/dt + 1 rows."""
    df = _long_pipeline_df(n_rows=4201, start=2_000_000)
    case = _make_case(df, inject_time=2_002_100.0)
    norm = normalize_case(case)
    assert len(norm.metrics) == int(2 * DEFAULT_WINDOW_SECONDS) + 1


def test_window_bounds_are_symmetric_around_inject_time():
    case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
    norm = normalize_case(case)
    assert norm.window_start == pytest.approx(2_002_100.0 - 600.0)
    assert norm.window_end == pytest.approx(2_002_100.0 + 600.0)
    assert norm.metrics["time"].iloc[0] == pytest.approx(norm.window_start)
    assert norm.metrics["time"].iloc[-1] == pytest.approx(norm.window_end)


def test_short_case_window_pads_when_data_is_shorter_than_window():
    """A 720-row short case with inject_time near the middle has data
    spanning only ~720s; a 1200s symmetric window must be padded on
    both sides."""
    df = _short_pipeline_df(n_rows=721, start=1_000_000)
    # inject_time at midpoint: row index 360 → time = 1_000_360
    case = _make_case(df, inject_time=1_000_360.0)
    norm = normalize_case(case)
    assert len(norm.metrics) == 1201

    first_row = norm.metrics.iloc[0]
    last_row = norm.metrics.iloc[-1]
    # Leading-edge bfill: first padded row equals the first raw row's
    # values (latency-50 → canonical latency = 0.05).
    assert first_row["svc-a_latency"] == pytest.approx(0.05)
    # Trailing-edge ffill: same value (constant fixture), but the
    # important invariant is "no NaN anywhere".
    assert not norm.metrics.isna().any().any()
    assert last_row["svc-a_latency"] == pytest.approx(0.05)


def test_window_padding_uses_last_observed_value_at_trailing_edge():
    """When the window extends past the data, the padded rows must hold
    the *final* raw value, not zero or NaN."""
    times = np.arange(0, 200, dtype=float)
    df = pd.DataFrame(
        {
            "time": times,
            "svc-a_latency": np.linspace(0.0, 1.0, 200),  # ends at 1.0
            "svc-a_load": np.full(200, 42.0),
            "svc-a_error": np.zeros(200),
        }
    )
    # inject at t=199 → window = [-401, +799]; trailing 600 rows need ffill.
    case = _make_case(df, inject_time=199.0)
    norm = normalize_case(case)
    # The final row of the windowed frame is at t = 799.
    final = norm.metrics.iloc[-1]
    assert final["time"] == pytest.approx(799.0)
    assert final["svc-a_latency"] == pytest.approx(1.0)


def test_window_padding_uses_first_observed_value_at_leading_edge():
    times = np.arange(1000, 1200, dtype=float)
    df = pd.DataFrame(
        {
            "time": times,
            "svc-a_latency": np.linspace(0.5, 1.5, 200),  # starts at 0.5
            "svc-a_load": np.full(200, 7.0),
        }
    )
    # inject at t=1000 → window = [400, 1600]; leading 600 rows need bfill.
    case = _make_case(df, inject_time=1000.0)
    norm = normalize_case(case)
    first = norm.metrics.iloc[0]
    assert first["time"] == pytest.approx(400.0)
    assert first["svc-a_latency"] == pytest.approx(0.5)


def test_custom_window_size():
    case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
    norm = normalize_case(case, window_seconds=30.0)
    assert len(norm.metrics) == 61  # 2*30 + 1


# ---- normalize_case: error paths ----


def test_missing_metrics_raises():
    case = BenchmarkCase(
        id="bad",
        telemetry={"inject_time": 1.0},
        ground_truth_root_cause="x",
        ground_truth_fault_type="y",
        system_topology=None,
    )
    with pytest.raises(KeyError, match="metrics"):
        normalize_case(case)


def test_missing_inject_time_raises():
    case = BenchmarkCase(
        id="bad",
        telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
        ground_truth_root_cause="x",
        ground_truth_fault_type="y",
        system_topology=None,
    )
    with pytest.raises(KeyError, match="inject_time"):
        normalize_case(case)


def test_missing_time_column_raises():
    case = BenchmarkCase(
        id="bad",
        telemetry={"metrics": pd.DataFrame({"x": [0, 1]}), "inject_time": 1.0},
        ground_truth_root_cause="x",
        ground_truth_fault_type="y",
        system_topology=None,
    )
    with pytest.raises(KeyError, match="time"):
        normalize_case(case)


# ---- live RE1-OB sample (skipped if dataset is not on this machine) ----


RE1_OB = Path(
    os.environ.get(
        "RCAEVAL_DATA_PATH", "~/research/rcaeval-tools/RCAEval/data/RE1/"
    )
).expanduser() / "RE1-OB"


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_real_re1_ob_sample_normalizes_to_uniform_window():
    """Run on 5 short (delay) + 5 long (mem) real cases. Confirm:

    * every normalized case has exactly 1201 rows (the symmetric 600s
      window at 1s sampling), regardless of the asymmetric raw length;
    * service list and populated canonical features print for each.
    """
    loader = RCAEvalLoader(RE1_OB)
    by_id = {c.id: c for c in loader.iter_cases()}

    short_ids = [
        "re1-ob_adservice_delay_1",
        "re1-ob_cartservice_delay_1",
        "re1-ob_checkoutservice_disk_1",
        "re1-ob_currencyservice_loss_1",
        "re1-ob_productcatalogservice_delay_2",
    ]
    long_ids = [
        "re1-ob_adservice_cpu_1",
        "re1-ob_cartservice_mem_1",
        "re1-ob_checkoutservice_cpu_1",
        "re1-ob_currencyservice_mem_1",
        "re1-ob_productcatalogservice_mem_3",
    ]

    print()
    header = (
        f"{'case_id':<48} {'raw_rows':>9} {'win_rows':>9} {'services':>9} "
        f"{'lat':>4} {'tfc':>4} {'err':>4} {'cpu':>4} {'mem':>4}"
    )
    print(header)
    print("-" * len(header))

    sampled = [by_id[i] for i in short_ids + long_ids]
    win_rows_seen: set[int] = set()
    for case in sampled:
        raw_rows = len(case.telemetry["metrics"])
        norm = normalize_case(case)
        s = norm.schema_summary
        print(
            f"{case.id:<48} {raw_rows:>9} {len(norm.metrics):>9} "
            f"{len(norm.services):>9} "
            f"{len(s['latency']):>4} {len(s['traffic']):>4} "
            f"{len(s['error']):>4} {len(s['cpu']):>4} {len(s['mem']):>4}"
        )
        win_rows_seen.add(len(norm.metrics))

        # Every sampled case must have the canonical latency / traffic
        # columns for at least one service after normalization.
        assert s["latency"], f"{case.id}: no service has canonical latency"
        assert s["traffic"], f"{case.id}: no service has canonical traffic"
        assert not norm.metrics.isna().any().any(), (
            f"{case.id}: normalized frame has NaN"
        )

    # The single most important invariant: row count is uniform across
    # both pipelines.
    assert win_rows_seen == {1201}, (
        f"expected every case to normalize to 1201 rows, saw {win_rows_seen}"
    )

    # And print a per-case sample of canonical features for one short
    # and one long case, so the output documents what downstream methods
    # actually see.
    print()
    for case_id in (short_ids[0], long_ids[0]):
        norm = normalize_case(by_id[case_id])
        print(f"{case_id}:")
        print(f"  services    = {norm.services}")
        for feat, svcs in norm.schema_summary.items():
            print(f"  {feat:<8} -> {svcs}")
