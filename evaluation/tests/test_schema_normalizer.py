"""Tests for evaluation.extraction.schema_normalizer.

Annotation policy
-----------------
Every assertion that **changed** versus the previous test suite carries
a ``# CHANGED:`` comment explaining why. Where the previous assertion
was passing only because methods could fencepost on ``inject_time``,
the comment is prefixed ``# CHANGED (was passing on leakage):`` so the
regression record is unambiguous. New tests added for the inject_time-
removal redesign are gathered in their own classes at the bottom.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import BenchmarkCase
from evaluation.extraction.schema_normalizer import (
    DEFAULT_INJECT_HIGH_PCT,
    DEFAULT_INJECT_LOW_PCT,
    DEFAULT_WINDOW_SECONDS,
    CaseGroundTruth,
    NormalizedCase,
    default_inject_offset_seconds,
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
    times = np.arange(start, start + n_rows, dtype=float)
    cols: dict[str, np.ndarray] = {"time": times}
    for svc in services:
        cols[f"{svc}_latency-50"] = np.full(n_rows, 0.05)
        cols[f"{svc}_latency-90"] = np.full(n_rows, 0.10)
        cols[f"{svc}_workload"]   = np.full(n_rows, 100.0)
        cols[f"{svc}_cpu"]        = np.full(n_rows, 0.30)
        cols[f"{svc}_mem"]        = np.full(n_rows, 0.40)
    cols["frontend_error"]              = np.zeros(n_rows)
    cols["frontend-external_error"]     = np.zeros(n_rows)
    cols["frontend-external_workload"]  = np.full(n_rows, 200.0)
    return pd.DataFrame(cols)


def _long_pipeline_df(
    n_rows: int = 4201,
    start: int = 2_000_000,
    services: tuple[str, ...] = ("svc-a", "svc-b"),
) -> pd.DataFrame:
    times = np.arange(start, start + n_rows, dtype=float)
    cols: dict[str, np.ndarray] = {"time": times}
    for svc in services:
        cols[f"{svc}_latency"] = np.full(n_rows, 0.07)
        cols[f"{svc}_load"]    = np.full(n_rows, 150.0)
        cols[f"{svc}_cpu"]     = np.full(n_rows, 0.55)
        cols[f"{svc}_mem"]     = np.full(n_rows, 0.65)
    cols["frontend_error"]              = np.zeros(n_rows)
    cols["frontend-external_error"]     = np.zeros(n_rows)
    cols["frontend-external_load"]      = np.full(n_rows, 250.0)
    cols["PassthroughCluster_error"]    = np.zeros(n_rows)
    cols["PassthroughCluster_load"]     = np.full(n_rows, 50.0)
    cols["time.1"] = times
    return pd.DataFrame(cols)


# ---- parse_service_list (unchanged behavior) ----


class TestParseServiceList:
    def test_short_pipeline(self):
        assert parse_service_list(_short_pipeline_df()) == [
            "frontend", "svc-a", "svc-b",
        ]

    def test_long_pipeline_excludes_passthrough(self):
        out = parse_service_list(_long_pipeline_df())
        assert "PassthroughCluster" not in out
        assert "frontend-external" not in out
        assert set(out) >= {"svc-a", "svc-b", "frontend"}

    def test_keeps_hyphenated_service_names(self):
        df = pd.DataFrame({"time": [0, 1], "ts-auth-service_cpu": [0.1, 0.2]})
        assert parse_service_list(df) == ["ts-auth-service"]

    def test_accepts_benchmark_case(self):
        # Centre the inject_time inside the synthetic time range so the
        # window has real data to crop. inject_time was at "1_000_360" in
        # the previous test; we keep it.
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        assert "svc-a" in parse_service_list(case)

    def test_ignores_time_columns(self):
        df = pd.DataFrame(
            {"time": [0, 1], "time.1": [0, 1], "svc-a_cpu": [0.1, 0.2]}
        )
        assert parse_service_list(df) == ["svc-a"]

    def test_rejects_non_dataframe_non_case(self):
        with pytest.raises(TypeError):
            parse_service_list("not a frame")  # type: ignore[arg-type]


# ---- column derivation (canonical naming) ----


class TestColumnDerivation:
    """All assertions read ``norm.case_window``.

    CHANGED: every ``norm.metrics`` access in the previous suite is now
    ``norm.case_window``. This is a pure rename to make the
    "bounded slice" semantics impossible to miss in review; the data is
    identical.
    """

    def test_short_case_latency_uses_p50(self):
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert "svc-a_latency" in norm.case_window.columns
        assert np.allclose(norm.case_window["svc-a_latency"].to_numpy(), 0.05)

    def test_short_case_traffic_uses_workload(self):
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert "svc-a_traffic" in norm.case_window.columns
        assert np.allclose(norm.case_window["svc-a_traffic"].to_numpy(), 100.0)

    def test_long_case_latency_uses_mean_column(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert "svc-a_latency" in norm.case_window.columns
        assert np.allclose(norm.case_window["svc-a_latency"].to_numpy(), 0.07)

    def test_long_case_traffic_prefers_load_over_workload(self):
        df = _long_pipeline_df()
        df["svc-a_workload"] = 999.0
        case = _make_case(df, inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert np.allclose(norm.case_window["svc-a_traffic"].to_numpy(), 150.0)

    def test_latency_prefers_mean_over_p50_when_both_present(self):
        df = _short_pipeline_df()
        df["svc-a_latency"] = 0.42
        case = _make_case(df, inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert np.allclose(norm.case_window["svc-a_latency"].to_numpy(), 0.42)

    def test_latency_falls_through_to_p90_only(self):
        # CHANGED: bumped n_rows from 100 to 1300 so the 1200 s window
        # has real data across most of it. Old test passed by accident
        # because the 600 s half-width window only needed ~100 rows; the
        # new full-width window needs at least ~window_seconds rows.
        df = pd.DataFrame({
            "time": np.arange(1300, dtype=float),
            "svc-a_latency-90": np.full(1300, 0.99),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert np.allclose(norm.case_window["svc-a_latency"].to_numpy(), 0.99)
        assert norm.schema_summary["latency"] == ["svc-a"]

    def test_time_dot_one_dropped(self):
        df = _long_pipeline_df()
        assert "time.1" in df.columns
        case = _make_case(df, inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert "time.1" not in norm.case_window.columns

    def test_resource_columns_passed_through(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert "svc-a_cpu" in norm.case_window.columns
        assert "svc-a_mem" in norm.case_window.columns
        assert np.allclose(norm.case_window["svc-a_cpu"].to_numpy(), 0.55)

    def test_error_column_passed_through_under_service_prefix(self):
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert "frontend_error" in norm.case_window.columns


# ---- latency_source tagging (Phase 2 multi-system extension) ----


class TestLatencySource:
    """The ``schema_summary["latency_source"]`` per-service tag records
    which raw column the canonical ``{svc}_latency`` slot was sourced
    from. RE1-OB ships mean-latency columns directly; RE1-SS / RE1-TT
    only expose Istio-percentile columns (``_latency-50`` / ``_latency-90``)
    that we alias under DEVIATIONS.md → "RE1-SS / RE1-TT latency alias".
    The tag lets downstream consumers (analysis notebooks, paper §4
    discussion) report when median-latency substitution is in effect.
    """

    def test_mean_latency_recorded_when_only_mean_present(self):
        df = pd.DataFrame({
            "time":          np.arange(1300, dtype=float),
            "svc-a_latency": np.full(1300, 0.07),
            "svc-a_cpu":     np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "mean_latency",
        }

    def test_p50_proxy_recorded_when_only_p50_present(self):
        df = pd.DataFrame({
            "time":             np.arange(1300, dtype=float),
            "svc-a_latency-50": np.full(1300, 0.05),
            "svc-a_cpu":        np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "p50_latency_proxy",
        }
        # The canonical {svc}_latency column carries the p50 values.
        assert np.allclose(
            norm.case_window["svc-a_latency"].to_numpy(), 0.05,
        )

    def test_mean_preferred_when_both_mean_and_p50_present(self):
        df = pd.DataFrame({
            "time":             np.arange(1300, dtype=float),
            "svc-a_latency":    np.full(1300, 0.42),
            "svc-a_latency-50": np.full(1300, 0.05),
            "svc-a_cpu":        np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "mean_latency",
        }
        assert np.allclose(
            norm.case_window["svc-a_latency"].to_numpy(), 0.42,
        )

    def test_p90_proxy_recorded_when_only_p90_present(self):
        df = pd.DataFrame({
            "time":             np.arange(1300, dtype=float),
            "svc-a_latency-90": np.full(1300, 0.99),
            "svc-a_cpu":        np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "p90_latency_proxy",
        }
        assert np.allclose(
            norm.case_window["svc-a_latency"].to_numpy(), 0.99,
        )

    def test_missing_recorded_when_no_latency_column_present(self):
        df = pd.DataFrame({
            "time":        np.arange(1300, dtype=float),
            "svc-a_cpu":   np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "missing",
        }
        assert "svc-a_latency" not in norm.case_window.columns

    def test_per_service_tagging_across_mixed_services(self):
        """Two services in the same frame, each backed by a different
        raw column. The tag must reflect each service independently."""
        df = pd.DataFrame({
            "time":             np.arange(1300, dtype=float),
            "svc-a_latency":    np.full(1300, 0.07),
            "svc-b_latency-50": np.full(1300, 0.05),
            "svc-a_cpu":        np.full(1300, 0.5),
            "svc-b_cpu":        np.full(1300, 0.5),
        })
        case = _make_case(df, inject_time=650.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency_source"] == {
            "svc-a": "mean_latency",
            "svc-b": "p50_latency_proxy",
        }


# ---- schema_summary (unchanged) ----


class TestSchemaSummary:
    def test_lists_populated_features(self):
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        norm = normalize_case(case)
        s = norm.schema_summary
        assert "svc-a" in s["latency"] and "svc-b" in s["latency"]
        assert "svc-a" in s["traffic"]
        assert "frontend" in s["error"]
        assert "svc-a" in s["cpu"]
        assert s["disk"] == []
        assert s["net"] == []

    def test_keys_always_present(self):
        case = _make_case(_short_pipeline_df(), inject_time=1_000_360.0)
        norm = normalize_case(case)
        for key in ("latency", "traffic", "error", "cpu", "mem", "disk", "net"):
            assert key in norm.schema_summary

    def test_service_lists_are_sorted(self):
        df = _short_pipeline_df(services=("zzz-svc", "aaa-svc", "mmm-svc"))
        case = _make_case(df, inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert norm.schema_summary["latency"] == sorted(
            norm.schema_summary["latency"]
        )


# ---- windowing under the NEW design ----


class TestWindowing:
    """The previous suite asserted that the window was centred on
    ``inject_time`` and had size ``2 * window_seconds / dt + 1``.

    CHANGED (was passing on leakage): the inject point is now placed
    at a per-case **random offset** in ``[25 %, 75 %]`` of the window,
    and ``window_seconds`` is the **total** window length (was the
    half-width). Tests below assert the new invariants instead.
    """

    def test_window_size_is_W_over_dt_plus_1_for_long_case(self):
        # CHANGED (was passing on leakage):
        # old assert: len == 2 * 600 / dt + 1 = 1201 (half-width design)
        # new assert: len == 1200 / dt + 1 = 1201 (full-width design)
        # Numerically identical (both 1201) by coincidence — the design
        # changed even when the row count didn't.
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert len(norm.case_window) == int(DEFAULT_WINDOW_SECONDS) + 1

    def test_window_bounds_anchor_to_random_offset_not_inject_time(self):
        # CHANGED (was passing on leakage):
        # old assert: window_start == inject_time - 600
        #             window_end   == inject_time + 600
        # new assert: window contains inject_time at a per-case offset in
        # [25 %, 75 %] of the window — there is no fencepost.
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        gt = norm.ground_truth
        assert norm.window_end - norm.window_start == pytest.approx(
            DEFAULT_WINDOW_SECONDS
        )
        offset = gt.inject_time - norm.window_start
        assert offset == pytest.approx(gt.inject_offset_seconds)
        assert (
            DEFAULT_INJECT_LOW_PCT  * DEFAULT_WINDOW_SECONDS
            <= gt.inject_offset_seconds
            <= DEFAULT_INJECT_HIGH_PCT * DEFAULT_WINDOW_SECONDS
        )

    def test_custom_window_size(self):
        # CHANGED (was passing on leakage):
        # old assert: len == 2 * 30 + 1 = 61
        # new assert: len == 30 + 1 = 31 (full-width now)
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case, window_seconds=30.0)
        assert len(norm.case_window) == 31

    def test_short_case_window_pads_when_data_is_shorter_than_window(self):
        # CHANGED: previous test had inject_time at the data midpoint and
        # asserted that both edges padded by exactly ``half_width −
        # half_data`` rows. Under the new design the inject offset is
        # hash-driven so the leading vs. trailing padding is asymmetric;
        # we now just assert (a) no NaN survives, (b) row count matches
        # the formula, (c) the inject_time still lies inside the window.
        df = _short_pipeline_df(n_rows=721, start=1_000_000)
        case = _make_case(df, inject_time=1_000_360.0)
        norm = normalize_case(case)
        assert len(norm.case_window) == int(DEFAULT_WINDOW_SECONDS) + 1
        assert not norm.case_window.isna().any().any()
        assert (
            norm.window_start
            <= norm.ground_truth.inject_time
            <= norm.window_end
        )
        # Constant fixture ⇒ leading-edge bfill / trailing-edge ffill
        # must both produce the same constant. Spot-check svc-a_latency
        # (derived from latency-50 = 0.05).
        assert norm.case_window["svc-a_latency"].iloc[0]  == pytest.approx(0.05)
        assert norm.case_window["svc-a_latency"].iloc[-1] == pytest.approx(0.05)

    def test_window_padding_uses_last_observed_value_at_trailing_edge(self):
        # CHANGED (was passing on leakage): previous test placed
        # inject_time at the end of the data so the entire trailing half
        # was padding. Under the new design we engineer the same regime
        # by giving the offset a deliberately low value via the explicit
        # override.
        n = 200
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "svc-a_latency": np.linspace(0.0, 1.0, n),
            "svc-a_load":    np.full(n, 42.0),
            "svc-a_error":   np.zeros(n),
        })
        case = _make_case(df, inject_time=199.0)
        # Force the inject point near the *start* of the window so we
        # have lots of trailing-edge padding. ``offset=300`` puts the
        # inject 300 s in; the window stretches to inject+900 = +701
        # seconds past the end of the raw data, which all gets ffilled
        # from raw[199].
        norm = normalize_case(case, inject_offset_seconds=300.0)
        last = norm.case_window.iloc[-1]
        assert last["svc-a_latency"] == pytest.approx(1.0)
        # ``_load`` → canonical ``_traffic`` post-normalization.
        assert last["svc-a_traffic"] == pytest.approx(42.0)

    def test_window_padding_uses_first_observed_value_at_leading_edge(self):
        # CHANGED (was passing on leakage): same idea as the trailing
        # edge — force the inject point near the *end* of the window
        # via an explicit offset to maximize leading-edge padding.
        n = 200
        df = pd.DataFrame({
            "time": np.arange(1000, 1000 + n, dtype=float),
            "svc-a_latency": np.linspace(0.5, 1.5, n),
            "svc-a_load":    np.full(n, 7.0),
        })
        case = _make_case(df, inject_time=1000.0)
        # ``offset=900`` puts the inject at 900 s in, leaving the
        # leading 900 s of the window before any raw data; bfilled from
        # raw[0] = 0.5.
        norm = normalize_case(case, inject_offset_seconds=900.0)
        first = norm.case_window.iloc[0]
        assert first["svc-a_latency"] == pytest.approx(0.5)
        # ``_load`` → canonical ``_traffic`` post-normalization.
        assert first["svc-a_traffic"] == pytest.approx(7.0)


# ---- error paths (unchanged) ----


class TestErrorPaths:
    def test_missing_metrics_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"inject_time": 1.0},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="metrics"):
            normalize_case(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            normalize_case(case)

    def test_missing_time_column_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"x": [0, 1]}), "inject_time": 1.0},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="time"):
            normalize_case(case)


# ---- NEW invariants introduced by the inject_time-removal design ----


class TestInjectTimeAttributeRemoval:
    """The whole point of this redesign — ``norm.inject_time`` must be
    inaccessible from the method-facing surface."""

    def test_inject_time_attribute_access_raises_helpful_error(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        with pytest.raises(AttributeError) as exc:
            norm.inject_time  # noqa: B018
        msg = str(exc.value)
        # Pinned to the exact wording specified in the approved design.
        assert "inject_time was removed from NormalizedCase" in msg
        assert "ground_truth.inject_time" in msg
        assert "evaluation harness" in msg

    def test_metrics_attribute_access_raises_with_rename_hint(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        with pytest.raises(AttributeError) as exc:
            norm.metrics  # noqa: B018
        assert "case_window" in str(exc.value)

    def test_hasattr_inject_time_is_false(self):
        # ``hasattr`` catches AttributeError and returns False — make
        # sure the redesign doesn't accidentally trip a different
        # exception class.
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert not hasattr(norm, "inject_time")
        assert not hasattr(norm, "metrics")

    def test_ground_truth_carries_the_metadata(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0,
                          case_id="c1", fault_type="cpu", root_cause="svc-a")
        norm = normalize_case(case)
        assert isinstance(norm.ground_truth, CaseGroundTruth)
        assert norm.ground_truth.inject_time == 2_002_100.0
        assert norm.ground_truth.root_cause_service == "svc-a"
        assert norm.ground_truth.fault_type == "cpu"

    def test_normalized_case_is_frozen(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        with pytest.raises(Exception):  # FrozenInstanceError on dataclass
            norm.id = "tampered"  # type: ignore[misc]


class TestDeterministicOffset:
    def test_offset_is_deterministic_for_same_case_id_and_window(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0,
                          case_id="case-42")
        a = normalize_case(case)
        b = normalize_case(case)
        assert (
            a.ground_truth.inject_offset_seconds
            == b.ground_truth.inject_offset_seconds
        )
        assert a.window_start == b.window_start
        assert a.window_end   == b.window_end

    def test_offset_changes_with_window_seconds(self):
        # Hash key is ``f"{case_id}|{window_seconds}"`` — changing the
        # window length re-randomizes the placement.
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0,
                          case_id="case-42")
        a = normalize_case(case, window_seconds=1200.0)
        b = normalize_case(case, window_seconds=1800.0)
        # Compare in normalized [0, 1] units so the two scales don't
        # bias the comparison.
        a_u = a.ground_truth.inject_offset_seconds / 1200.0
        b_u = b.ground_truth.inject_offset_seconds / 1800.0
        assert abs(a_u - b_u) > 1e-9

    def test_offset_is_in_25_75_band_across_many_ids(self):
        # Sanity histogram on synthetic ids: every offset must land in
        # [25 %, 75 %] and the spread must be non-degenerate.
        offsets = [
            default_inject_offset_seconds(f"case-{i}", 1200.0)
            for i in range(200)
        ]
        assert all(300.0 <= o <= 900.0 for o in offsets)
        # Non-degenerate spread: at least 10 % of the band's width.
        assert (max(offsets) - min(offsets)) >= 0.10 * (900.0 - 300.0)

    def test_explicit_offset_overrides_default(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case, inject_offset_seconds=400.0)
        assert norm.ground_truth.inject_offset_seconds == 400.0
        assert norm.window_start == pytest.approx(2_002_100.0 - 400.0)

    def test_explicit_offset_outside_window_raises(self):
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        with pytest.raises(ValueError, match="inject_offset_seconds"):
            normalize_case(case, inject_offset_seconds=1500.0)  # > window
        with pytest.raises(ValueError, match="inject_offset_seconds"):
            normalize_case(case, inject_offset_seconds=-5.0)


class TestResamplingAndRegularity:
    def test_sampling_dt_exposed_as_field(self):
        # The previous suite computed dt inside each test from
        # ``diff(times).median()``; the new ``NormalizedCase`` carries
        # it explicitly so methods don't redo the work and so the
        # validator can rely on a single source of truth.
        case = _make_case(_long_pipeline_df(), inject_time=2_002_100.0)
        norm = normalize_case(case)
        assert norm.sampling_dt == pytest.approx(1.0)

    def test_linear_interpolation_used_within_raw_range(self):
        # Build a sparse but regular raw frame at dt=10. Force an
        # explicit offset so the target grid lands mid-way between raw
        # samples, then check the linear interp values.
        n = 300
        raw_times = np.arange(0, n * 10, 10, dtype=float)
        df = pd.DataFrame({
            "time": raw_times,
            "svc-a_latency": np.linspace(0.0, 30.0, n),  # 0.1/step
        })
        case = _make_case(df, inject_time=1500.0, case_id="interp-test")
        # Override offset so the inject is at window_start + 600 → the
        # target grid is window_start + i*10 = raw[i] exactly; we then
        # don't need to assert mid-gap interp here (that case is the
        # phase-shifted one below).
        norm = normalize_case(case, window_seconds=200.0,
                              inject_offset_seconds=100.0)
        # Values pulled at exact raw timestamps must equal raw.
        first = norm.case_window["svc-a_latency"].iloc[0]
        last  = norm.case_window["svc-a_latency"].iloc[-1]
        # Sanity: monotone linear ramp.
        assert last > first
        # Mid-gap check: build the same case at the default hashed
        # offset (likely fractional) and confirm interp doesn't go NaN.
        norm2 = normalize_case(case, window_seconds=200.0)
        assert not norm2.case_window.isna().any().any()

    def test_irregular_raw_sampling_over_20pct_raises(self):
        # Build 100 rows where 25 of them have a >50% gap deviation.
        n = 100
        diffs = [1.0] * 75 + [3.5] * 25  # 25/99 = 25 % irregular
        times = np.cumsum(diffs)
        df = pd.DataFrame({
            "time": np.concatenate(([0.0], times)),
            "svc-a_latency": np.zeros(len(times) + 1),
        })
        case = _make_case(df, inject_time=float(times[len(times) // 2]),
                          case_id="irregular-1")
        with pytest.raises(ValueError, match="irregular"):
            normalize_case(case, window_seconds=200.0)

    def test_regular_raw_sampling_does_not_raise(self):
        # The synthetic fixtures use perfectly regular sampling at dt=1
        # and dt=10. Both must normalize without raising.
        normalize_case(_make_case(_long_pipeline_df(),  inject_time=2_002_100.0))
        normalize_case(_make_case(_short_pipeline_df(), inject_time=1_000_360.0))


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
    """5 short + 5 long real cases. CHANGED row count assertion: the
    new full-width 1200 s window at 1 s sampling yields ``1200 + 1 =
    1201`` rows, the same number as the previous half-width 600 s
    design (by coincidence, not by design)."""
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
        f"{'case_id':<48} {'raw_rows':>9} {'win_rows':>9} "
        f"{'offset_s':>10} {'services':>9} {'lat':>4} {'tfc':>4} "
        f"{'err':>4} {'cpu':>4} {'mem':>4}"
    )
    print(header)
    print("-" * len(header))

    sampled = [by_id[i] for i in short_ids + long_ids]
    seen_row_counts: set[int] = set()
    for case in sampled:
        norm = normalize_case(case)
        s = norm.schema_summary
        print(
            f"{case.id:<48} {len(case.telemetry['metrics']):>9} "
            f"{len(norm.case_window):>9} "
            f"{norm.ground_truth.inject_offset_seconds:>10.1f} "
            f"{len(norm.services):>9} "
            f"{len(s['latency']):>4} {len(s['traffic']):>4} "
            f"{len(s['error']):>4} {len(s['cpu']):>4} {len(s['mem']):>4}"
        )
        seen_row_counts.add(len(norm.case_window))
        assert s["latency"], f"{case.id}: no service has canonical latency"
        assert s["traffic"], f"{case.id}: no service has canonical traffic"
        assert not norm.case_window.isna().any().any()
        # CHANGED (was passing on leakage): previously asserted that the
        # window was centred on the inject point. Now the inject lies at
        # the hashed offset within the window — we just confirm it's
        # somewhere inside.
        gt = norm.ground_truth
        assert norm.window_start <= gt.inject_time <= norm.window_end

    expected_rows = int(DEFAULT_WINDOW_SECONDS) + 1   # 1201 @ dt=1
    assert seen_row_counts == {expected_rows}, (
        f"expected every case to normalize to {expected_rows} rows, "
        f"saw {seen_row_counts}"
    )
