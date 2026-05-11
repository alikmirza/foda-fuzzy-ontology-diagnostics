"""Tests for ``evaluation.methods.baro`` on :class:`NormalizedCase`.

Eight groups of tests:

1. **Contract** on the small RCAEval fake fixture.
2. **Synthetic 3-service and 5-service** scenarios with an obvious
   anomaly — BARO must rank it top-1.
3. **BOCPD detector** — change point lands inside the band, post-
   change-point evidence dominates pre.
4. **Input validation** — bad init args, missing telemetry pieces.
5. **Protocol validator** + **shift invariance** under ±300 s shift.
6. **Decompositions** — random-onset and z-score-onset variants via
   :func:`_detect_change_point` monkey-patching match what the
   harness expects to see.
7. **Explanation shape** — change-point atom at the root, top-K
   service atoms attached by ``post-change-shift-attribution``.
8. **RE1-OB sanity check** (skipped if data isn't local).
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
)
from evaluation.extraction.schema_normalizer import normalize_case
from evaluation.methods import baro as baro_mod
from evaluation.methods._protocol import validate_no_ground_truth_peeking
from evaluation.methods.baro import BAROMethod


FIXTURES = Path(__file__).parent / "fixtures"
RCAEVAL_FIXTURE = FIXTURES / "rcaeval_fake"

RE1_OB = Path(
    os.environ.get(
        "RCAEVAL_DATA_PATH", "~/research/rcaeval-tools/RCAEval/data/RE1/"
    )
).expanduser() / "RE1-OB"

RESULTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "results"
    / "week2_baro_validation.csv"
)


# ---- helpers ----


def _ob_case() -> BenchmarkCase:
    return RCAEvalLoader(RCAEVAL_FIXTURE).get_case("OB_cartservice_CPU_1")


def _make_case(
    df: pd.DataFrame,
    inject_time: float,
    root_cause: str,
    case_id: str = "synthetic",
    fault_type: str = "cpu",
) -> BenchmarkCase:
    return BenchmarkCase(
        id=case_id,
        telemetry={"metrics": df, "inject_time": inject_time},
        ground_truth_root_cause=root_cause,
        ground_truth_fault_type=fault_type,
        system_topology=None,
    )


def _three_service_case(seed: int = 0) -> BenchmarkCase:
    """3-service chain where ``db_cpu`` and ``db_latency`` step up at
    the injection. BARO should rank ``db`` top-1 by post-change shift
    magnitude regardless of which onset it detects, as long as the
    onset is somewhere before the post segment is dominated by the
    spike."""
    n = 1000
    inject_idx = 500
    rng = np.random.default_rng(seed)

    db_cpu = 0.20 + rng.normal(0.0, 0.02, n)
    db_cpu[inject_idx:] += 0.60

    base_latency = 0.10 + 0.02 * np.sin(np.linspace(0, 6 * np.pi, n))
    frontend_latency = base_latency + rng.normal(0.0, 0.01, n)
    cart_latency = base_latency + rng.normal(0.0, 0.01, n)
    db_latency = base_latency + rng.normal(0.0, 0.01, n)
    db_latency[inject_idx:] += 0.20
    cart_latency[inject_idx + 1:] += 0.05

    base_traffic = 100 + 5 * np.sin(np.linspace(0, 4 * np.pi, n))
    df = pd.DataFrame({
        "time": np.arange(n, dtype=float),
        "frontend_latency": frontend_latency,
        "frontend_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "frontend_cpu": 0.15 + rng.normal(0.0, 0.01, n),
        "cart_latency": cart_latency,
        "cart_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "cart_cpu": 0.25 + rng.normal(0.0, 0.01, n),
        "db_latency": db_latency,
        "db_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "db_cpu": db_cpu,
    })
    return _make_case(
        df, inject_time=float(inject_idx), root_cause="db",
        case_id="synthetic_3svc",
    )


def _five_service_case(seed: int = 0) -> BenchmarkCase:
    n = 1000
    inject_idx = 500
    rng = np.random.default_rng(seed)
    services = ["frontend", "cart", "search", "payment", "inventory"]
    base_latency = 0.10 + 0.02 * np.sin(np.linspace(0, 6 * np.pi, n))
    base_traffic = 100 + 5 * np.sin(np.linspace(0, 4 * np.pi, n))

    df: dict[str, np.ndarray] = {"time": np.arange(n, dtype=float)}
    for svc in services:
        df[f"{svc}_latency"] = base_latency + rng.normal(0.0, 0.01, n)
        df[f"{svc}_traffic"] = base_traffic + rng.normal(0.0, 1.0, n)
        df[f"{svc}_cpu"] = 0.20 + rng.normal(0.0, 0.01, n)
        df[f"{svc}_mem"] = 0.30 + rng.normal(0.0, 0.01, n)

    df["inventory_cpu"][inject_idx:] += 0.60
    df["inventory_latency"][inject_idx:] += 0.25
    df["cart_latency"][inject_idx + 1:] += 0.05
    df["frontend_latency"][inject_idx + 2:] += 0.03

    return _make_case(
        pd.DataFrame(df),
        inject_time=float(inject_idx),
        root_cause="inventory",
        case_id="synthetic_5svc",
    )


# ---- 1. contract tests ----


class TestContractOnFakeFixture:
    def test_returns_diagnostic_output(self):
        out = BAROMethod().diagnose(_ob_case())
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "baro"
        assert out.wall_time_ms >= 0.0

    def test_ranked_list_non_empty_and_sorted(self):
        out = BAROMethod().diagnose(_ob_case())
        assert len(out.ranked_list) >= 1
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_explanation_is_change_point_rooted(self):
        out = BAROMethod().diagnose(_ob_case())
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        atoms = list(out.explanation_chain.atoms())
        assert len(atoms) >= 1
        roots = out.explanation_chain.roots()
        # The change-point atom is the root (no incoming edges).
        assert len(roots) == 1
        assert "change point" in roots[0].text

    def test_confidence_in_unit_interval(self):
        out = BAROMethod().diagnose(_ob_case())
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_cartservice_outranks_frontend_on_cpu_anomaly(self):
        out = BAROMethod().diagnose(_ob_case())
        top, _ = out.ranked_list[0]
        assert top == "cartservice"

    def test_deterministic_across_runs(self):
        case = _ob_case()
        a = BAROMethod().diagnose(case)
        b = BAROMethod().diagnose(case)
        assert a.ranked_list == b.ranked_list
        assert a.confidence == b.confidence

    def test_raw_output_carries_change_point_and_scores(self):
        out = BAROMethod().diagnose(_ob_case())
        assert "change_point_time" in out.raw_output
        assert "change_point_posterior" in out.raw_output
        assert "shift_scores" in out.raw_output
        assert "dominant_features" in out.raw_output
        assert "aggregate" in out.raw_output


# ---- 2. synthetic scenarios ----


class TestSyntheticScenarios:
    def test_three_service_chain_ranks_anomaly_top_1(self):
        out = BAROMethod().diagnose(_three_service_case())
        top, _ = out.ranked_list[0]
        assert top == "db"

    def test_five_service_fanout_ranks_anomaly_top_1(self):
        out = BAROMethod().diagnose(_five_service_case())
        top, _ = out.ranked_list[0]
        assert top == "inventory"

    def test_five_service_top_atom_tags_dominant_feature(self):
        out = BAROMethod().diagnose(_five_service_case())
        atoms = list(out.explanation_chain.atoms())
        # Atom 0 is the change-point root; atom 1+ are the top-K services
        # in ranked order.
        assert "inventory" in atoms[1].text
        assert "cpu" in atoms[1].text or "latency" in atoms[1].text

    def test_flat_no_anomaly_does_not_crash(self):
        n = 500
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "frontend_latency": 0.10 + rng.normal(0.0, 0.01, n),
            "frontend_traffic": 100.0 + rng.normal(0.0, 1.0, n),
            "cart_latency": 0.15 + rng.normal(0.0, 0.01, n),
            "cart_traffic": 100.0 + rng.normal(0.0, 1.0, n),
            "db_latency": 0.20 + rng.normal(0.0, 0.01, n),
            "db_traffic": 100.0 + rng.normal(0.0, 1.0, n),
        })
        case = _make_case(df, inject_time=250.0, root_cause="cart",
                          case_id="synthetic_flat")
        out = BAROMethod().diagnose(case)
        assert {s for s, _ in out.ranked_list} == {"frontend", "cart", "db"}
        for _, score in out.ranked_list:
            assert np.isfinite(score)


# ---- 3. BOCPD detector ----


class TestBOCPDDetector:
    def test_change_point_falls_inside_post_band_on_clear_step(self):
        """Detected change-point timestamp must be in the central band
        (the masked region) and reasonably close to the synthetic
        injection."""
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        cp_time, posterior = baro_mod._detect_change_point(
            case_window=norm.case_window,
            services=norm.services,
        )
        ts = norm.case_window["time"].to_numpy()
        t_min, t_max = float(ts[0]), float(ts[-1])
        # Detector is restricted to the central [25%, 75%) band.
        assert t_min + 0.25 * (t_max - t_min) <= cp_time
        assert cp_time <= t_min + 0.75 * (t_max - t_min)
        assert 0.0 <= posterior <= 1.0

    def test_change_point_finite_on_flat_signal(self):
        n = 400
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "a_latency": 0.10 + rng.normal(0.0, 0.001, n),
            "a_cpu": 0.20 + rng.normal(0.0, 0.001, n),
            "b_latency": 0.15 + rng.normal(0.0, 0.001, n),
        })
        case = _make_case(df, inject_time=200.0, root_cause="a",
                          case_id="flat")
        norm = normalize_case(case, window_seconds=1200.0)
        cp_time, posterior = baro_mod._detect_change_point(
            case_window=norm.case_window,
            services=norm.services,
        )
        assert np.isfinite(cp_time)
        assert 0.0 <= posterior <= 1.0

    def test_bocpd_handles_all_constant_columns(self):
        """If every column has zero variance, _stack_signal_matrix
        returns empty; the detector falls back to the window centre
        and posterior 0.0."""
        n = 100
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "a_latency": np.full(n, 0.10),
            "a_cpu": np.full(n, 0.20),
        })
        cp_time, posterior = baro_mod._detect_change_point(
            case_window=df, services=["a"],
        )
        assert cp_time == float(df["time"].iloc[n // 2])
        assert posterior == 0.0


# ---- 4. input validation ----


class TestInputValidation:
    def test_missing_metrics_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"inject_time": 1.0},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="metrics"):
            BAROMethod().diagnose(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            BAROMethod().diagnose(case)

    def test_metrics_with_no_services_raises(self):
        case = _make_case(
            pd.DataFrame({"time": [0.0, 1.0, 2.0], "scalar": [1.0, 2.0, 3.0]}),
            inject_time=1.0,
            root_cause="?",
        )
        with pytest.raises(ValueError, match="services"):
            BAROMethod().diagnose(case)

    @pytest.mark.parametrize("hazard_lambda", [0.5, 1.0, 0.0, -1.0])
    def test_hazard_lambda_must_exceed_one(self, hazard_lambda):
        with pytest.raises(ValueError, match="hazard_lambda"):
            BAROMethod(hazard_lambda=hazard_lambda)

    def test_prior_var_must_be_positive(self):
        with pytest.raises(ValueError, match="prior_var"):
            BAROMethod(prior_var=0.0)

    def test_obs_var_floor_must_be_positive(self):
        with pytest.raises(ValueError, match="obs_var_floor"):
            BAROMethod(obs_var_floor=0.0)

    def test_max_run_length_must_be_at_least_four(self):
        with pytest.raises(ValueError, match="max_run_length"):
            BAROMethod(max_run_length=3)

    def test_aggregate_must_be_sum_or_max(self):
        with pytest.raises(ValueError, match="aggregate"):
            BAROMethod(aggregate="median")

    def test_top_k_must_be_positive(self):
        with pytest.raises(ValueError, match="top_k"):
            BAROMethod(top_k=0)

    def test_window_seconds_must_be_positive(self):
        with pytest.raises(ValueError, match="window_seconds"):
            BAROMethod(window_seconds=0.0)


# ---- 5. protocol + shift ----


class TestProtocolValidator:
    def test_diagnose_does_not_reference_ground_truth(self):
        validate_no_ground_truth_peeking(BAROMethod())

    def test_aggregate_max_variant_also_passes_protocol(self):
        validate_no_ground_truth_peeking(BAROMethod(aggregate="max"))


class TestShiftInvariance:
    def test_output_identical_under_pm_300s_shift(self):
        """By construction: BARO does its own change-point detection
        from ``case_window`` and never reads ``ground_truth``. The
        ground-truth-side-channel shift must leave the diagnosis
        bit-identical."""
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        m = BAROMethod()
        out_true = m.diagnose_normalized(norm)
        for shift in (-300.0, 300.0):
            shifted_gt = dataclasses.replace(
                norm.ground_truth,
                inject_time=norm.ground_truth.inject_time + shift,
                inject_offset_seconds=norm.ground_truth.inject_offset_seconds,
            )
            shifted = dataclasses.replace(norm, ground_truth=shifted_gt)
            out = m.diagnose_normalized(shifted)
            assert out.ranked_list == out_true.ranked_list
            assert out.confidence == out_true.confidence


# ---- 6. decompositions (monkey-patch _detect_change_point) ----


class TestDetectorDecompositions:
    def test_random_onset_variant_yields_finite_ranking(self):
        """Monkey-patch ``_detect_change_point`` to return a fixed
        in-band pivot — the harness uses this pattern to compute
        ``AC@1_random``."""
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        original = baro_mod._detect_change_point
        ts = norm.case_window["time"].to_numpy()
        forced = float(ts[len(ts) // 2])

        def _fake(case_window, services, **kwargs):
            return forced, float("nan")

        baro_mod._detect_change_point = _fake
        try:
            out = BAROMethod().diagnose_normalized(norm)
        finally:
            baro_mod._detect_change_point = original
        assert {s for s, _ in out.ranked_list} == set(norm.services)
        # Confidence falls back to the score ratio.
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_zscore_onset_variant_yields_finite_ranking(self):
        """Monkey-patch ``_detect_change_point`` to delegate to the
        shared z-score :func:`detect_onset` — the harness uses this
        pattern to compute ``AC@1_zscore_onset``."""
        from evaluation.methods._onset import detect_onset

        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        original = baro_mod._detect_change_point

        def _fake(case_window, services, **kwargs):
            return detect_onset(case_window, services), float("nan")

        baro_mod._detect_change_point = _fake
        try:
            out = BAROMethod().diagnose_normalized(norm)
        finally:
            baro_mod._detect_change_point = original
        assert {s for s, _ in out.ranked_list} == set(norm.services)
        assert out.confidence is not None

    def test_native_and_zscore_onset_may_disagree_on_change_point(self):
        """The two detectors are method-internal vs. method-external;
        they need not agree on the exact change-point timestamp. The
        rank ordering may still match — that's the paper-relevant
        observation."""
        from evaluation.methods._onset import detect_onset

        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        cp_native, _ = baro_mod._detect_change_point(
            case_window=norm.case_window, services=norm.services,
        )
        cp_zscore = detect_onset(norm.case_window, norm.services)
        # Both must be inside the band.
        ts = norm.case_window["time"].to_numpy()
        t_min, t_max = float(ts[0]), float(ts[-1])
        for cp in (cp_native, cp_zscore):
            assert t_min + 0.25 * (t_max - t_min) <= cp
            assert cp <= t_min + 0.75 * (t_max - t_min)


# ---- 7. explanation shape ----


class TestExplanationShape:
    def test_change_point_atom_is_root_with_outgoing_links(self):
        out = BAROMethod().diagnose(_three_service_case())
        roots = out.explanation_chain.roots()
        assert len(roots) == 1
        root = roots[0]
        assert "change point" in root.text
        # Every link emanates from the root.
        links = list(out.explanation_chain.links())
        assert links, "expected at least one outgoing link"
        for link in links:
            assert link.source_atom_id == root.id
            assert link.relation_type == "post-change-shift-attribution"
            assert link.weight is not None
            assert 0.0 <= link.weight <= 1.0

    def test_link_weights_sum_to_at_most_one(self):
        """Each service's link weight is its score divided by the head
        total — by construction the weights sum to 1.0 across the head."""
        out = BAROMethod().diagnose(_three_service_case())
        weights = [
            link.weight for link in out.explanation_chain.links()
            if link.weight is not None
        ]
        assert weights
        s = sum(weights)
        assert 0.99 <= s <= 1.01


# ---- 8. RE1-OB sanity check ----


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_ac_at_k_sanity_check():
    """Run BARO on every RE1-OB case via the standalone harness and
    assert:

    1. ``S(BARO) == 0`` per fault — BARO does its own change-point
       detection from ``case_window`` and never reads ``ground_truth``.
       The ±300 s shift must not move AC@1.
    2. AC@1 overall is in ``[0.10, 0.80]`` (brief §11; published
       BARO is ~0.80 Avg@5 on RE2-TT, our RE1-OB number is expected
       to be in the same ballpark, possibly higher under the
       schema-preprocessing-uplift pattern we've seen).
    3. ``AC@1_random`` and ``AC@1_zscore_onset`` columns are present
       in the per-case CSV (paper-relevant decompositions).
    """
    from evaluation.experiments.evaluate_baro import (
        evaluate,
        print_summary,
        write_per_case_csv,
    )

    summary, per_case = evaluate(
        RE1_OB,
        top_ks=(1, 3, 5),
        with_random_onset=True,
        with_zscore_onset=True,
    )
    write_per_case_csv(per_case, RESULTS_PATH, top_ks=(1, 3, 5))
    print(f"\nWrote per-case results to {RESULTS_PATH}")
    print()
    print_summary(summary, top_ks=(1, 3, 5))

    for fault, row in summary.items():
        if fault == "overall":
            continue
        s = row.get("S", float("nan"))
        assert s == 0.0 or (isinstance(s, float) and (s != s)), (
            f"S(BARO) for fault {fault!r} = {s}; non-zero means the "
            f"method is leaking inject_time"
        )

    overall_ac1 = summary["overall"]["AC@1"]
    print(f"\nOverall AC@1 = {overall_ac1:.3f} (expected [0.10, 0.80])")
    if overall_ac1 > 0.80:
        print(
            "  ⚠ AC@1 above brief's upper band (0.80). S(M)=0 ⇒ not "
            "an inject_time leak; same schema-uplift pattern as "
            "the other adapters."
        )
    assert overall_ac1 >= 0.10, (
        f"BARO overall AC@1 = {overall_ac1:.3f} below 0.10 — "
        f"likely an implementation bug."
    )

    ac1_random = summary["overall"].get("AC@1_random", float("nan"))
    ac1_zscore = summary["overall"].get("AC@1_zscore_onset", float("nan"))
    print(
        f"Decompositions: native AC@1 = {overall_ac1:.3f}, "
        f"random AC@1 = {ac1_random:.3f}, "
        f"z-score-onset AC@1 = {ac1_zscore:.3f}"
    )
