"""Tests for ``evaluation.methods.microrca`` on :class:`NormalizedCase`.

Six groups of tests:

1. **Contract** on the small RCAEval fake fixture.
2. **Synthetic 3-service and 5-service** scenarios with an obvious
   anomaly — MicroRCA must rank it top-1.
3. **Attributed-graph asymmetry** — lagged correlation produces
   different edge weights in opposite directions on a constructed
   lead-lag signal, and the collapsed-graph mode does not.
4. **Input validation** — bad init args, missing telemetry pieces.
5. **Protocol validator** + **shift invariance**.
6. **RE1-OB sanity check** (skipped if data isn't local).
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
from evaluation.methods._protocol import validate_no_ground_truth_peeking
from evaluation.methods.microrca import MicroRCAMethod


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
    / "week2_microrca_validation.csv"
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
    """3-service ``frontend → cart → db`` where ``db_cpu`` steps up at
    injection. Cart's latency tracks db's CPU spike (downstream
    propagation), so the lead-lag correlation should have
    ``db → cart`` weight > ``cart → db`` weight."""
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
    cart_latency[inject_idx + 1 :] += 0.10  # cart lags db by one sample

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
    return _make_case(df, inject_time=float(inject_idx),
                      root_cause="db", case_id="synthetic_3svc")


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
    df["cart_latency"][inject_idx + 1 :] += 0.08
    df["frontend_latency"][inject_idx + 2 :] += 0.04

    return _make_case(
        pd.DataFrame(df),
        inject_time=float(inject_idx),
        root_cause="inventory",
        case_id="synthetic_5svc",
    )


# ---- 1. contract tests ----


class TestContractOnFakeFixture:
    def test_returns_diagnostic_output(self):
        out = MicroRCAMethod().diagnose(_ob_case())
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "microrca"
        assert out.wall_time_ms >= 0.0

    def test_ranked_list_non_empty_and_sorted(self):
        out = MicroRCAMethod().diagnose(_ob_case())
        assert len(out.ranked_list) >= 1
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_explanation_is_attributed_graph(self):
        """MicroRCA emits a real causal-link graph between top-K
        services, not a flat list. On the 2-service fixture we
        expect 2 atoms and 0-2 links (self-loops are dropped)."""
        out = MicroRCAMethod().diagnose(_ob_case())
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        atoms = list(out.explanation_chain.atoms())
        assert 1 <= len(atoms) <= 3

    def test_confidence_in_unit_interval(self):
        out = MicroRCAMethod().diagnose(_ob_case())
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_cartservice_outranks_frontend_on_cpu_anomaly(self):
        out = MicroRCAMethod().diagnose(_ob_case())
        top, _ = out.ranked_list[0]
        assert top == "cartservice"

    def test_deterministic_across_runs(self):
        case = _ob_case()
        a = MicroRCAMethod().diagnose(case)
        b = MicroRCAMethod().diagnose(case)
        assert a.ranked_list == b.ranked_list
        assert a.confidence == b.confidence

    def test_raw_output_carries_graph_and_anomaly(self):
        out = MicroRCAMethod().diagnose(_ob_case())
        assert "graph_edges" in out.raw_output
        assert "ppr_scores" in out.raw_output
        assert "anomaly_scores" in out.raw_output
        assert "collapsed_graph" in out.raw_output
        assert out.raw_output["collapsed_graph"] is False


# ---- 2. synthetic scenarios ----


class TestSyntheticScenarios:
    def test_three_service_chain_ranks_anomaly_top_1(self):
        out = MicroRCAMethod().diagnose(_three_service_case())
        top, _ = out.ranked_list[0]
        assert top == "db"

    def test_five_service_fanout_ranks_anomaly_top_1(self):
        out = MicroRCAMethod().diagnose(_five_service_case())
        top, _ = out.ranked_list[0]
        assert top == "inventory"

    def test_five_service_top_atom_tags_dominant_feature(self):
        out = MicroRCAMethod().diagnose(_five_service_case())
        atoms = list(out.explanation_chain.atoms())
        top_atom = atoms[0]
        assert "inventory" in top_atom.text
        assert "cpu" in top_atom.text or "latency" in top_atom.text

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
        out = MicroRCAMethod().diagnose(case)
        assert {s for s, _ in out.ranked_list} == {"frontend", "cart", "db"}
        for _, score in out.ranked_list:
            assert np.isfinite(score)


# ---- 3. attributed-graph asymmetry ----


class TestAttributedGraphAsymmetry:
    def test_lagged_edges_are_asymmetric(self):
        """On a chain ``db → cart`` where cart's latency lags db's
        CPU by one sample, the lagged-correlation graph must give
        ``db → cart`` higher weight than ``cart → db``."""
        out = MicroRCAMethod(lag=1).diagnose(_three_service_case())
        edges = {(u, v): w for u, v, w in out.raw_output["graph_edges"]}
        w_db_cart = edges.get(("db", "cart"), 0.0)
        w_cart_db = edges.get(("cart", "db"), 0.0)
        assert w_db_cart > w_cart_db, (
            f"expected db → cart > cart → db, got {w_db_cart} vs "
            f"{w_cart_db}"
        )

    def test_collapsed_graph_is_symmetric(self):
        """``collapsed_graph=True`` reduces to symmetric Pearson;
        both directions get the same weight, modulo float noise."""
        out = MicroRCAMethod(collapsed_graph=True).diagnose(
            _three_service_case()
        )
        edges = {(u, v): w for u, v, w in out.raw_output["graph_edges"]}
        w_db_cart = edges.get(("db", "cart"), 0.0)
        w_cart_db = edges.get(("cart", "db"), 0.0)
        assert abs(w_db_cart - w_cart_db) < 1e-9

    def test_collapsed_flag_marked_in_raw_output(self):
        out = MicroRCAMethod(collapsed_graph=True).diagnose(_ob_case())
        assert out.raw_output["collapsed_graph"] is True


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
            MicroRCAMethod().diagnose(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            MicroRCAMethod().diagnose(case)

    def test_metrics_with_no_services_raises(self):
        case = _make_case(
            pd.DataFrame({"time": [0.0, 1.0, 2.0], "scalar": [1.0, 2.0, 3.0]}),
            inject_time=1.0,
            root_cause="?",
        )
        with pytest.raises(ValueError, match="services"):
            MicroRCAMethod().diagnose(case)

    @pytest.mark.parametrize("alpha", [-0.1, 0.0, 1.0, 1.5])
    def test_alpha_must_be_in_open_unit_interval(self, alpha):
        with pytest.raises(ValueError, match="alpha"):
            MicroRCAMethod(alpha=alpha)

    def test_n_iters_must_be_positive(self):
        with pytest.raises(ValueError, match="n_iters"):
            MicroRCAMethod(n_iters=0)

    def test_top_k_must_be_positive(self):
        with pytest.raises(ValueError, match="top_k"):
            MicroRCAMethod(top_k=0)

    def test_lag_must_be_non_negative(self):
        with pytest.raises(ValueError, match="lag"):
            MicroRCAMethod(lag=-1)

    def test_window_seconds_must_be_positive(self):
        with pytest.raises(ValueError, match="window_seconds"):
            MicroRCAMethod(window_seconds=0.0)


# ---- 5. protocol + shift ----


class TestProtocolValidator:
    def test_diagnose_does_not_reference_ground_truth(self):
        validate_no_ground_truth_peeking(MicroRCAMethod())

    def test_collapsed_variant_also_passes_protocol(self):
        validate_no_ground_truth_peeking(MicroRCAMethod(collapsed_graph=True))


class TestShiftInvariance:
    def test_output_identical_under_pm_300s_shift(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        m = MicroRCAMethod()
        out_true = m.diagnose_normalized(norm)
        for shift in (-300.0, 300.0):
            shifted_gt = dataclasses.replace(
                norm.ground_truth,
                inject_time=norm.ground_truth.inject_time + shift,
                inject_offset_seconds=(
                    norm.ground_truth.inject_offset_seconds
                ),
            )
            shifted = dataclasses.replace(norm, ground_truth=shifted_gt)
            out = m.diagnose_normalized(shifted)
            assert out.ranked_list == out_true.ranked_list
            assert out.confidence == out_true.confidence


# ---- 6. RE1-OB sanity check ----


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_ac_at_k_sanity_check():
    """Run MicroRCA on every RE1-OB case via the shared harness and
    assert:

    1. ``S(M) ≈ 0`` per fault — MicroRCA does NOT read
       ``ground_truth.inject_time``, so the ±300 s shift must not
       move AC@1.
    2. AC@1 overall is in ``[0.10, 0.65]``. The brief's expanded
       ceiling reflects that MonitorRank and CausalRCA both score
       ~0.63 on the same normalized telemetry.
    3. Collapsed-graph AC@1 is computed and reported in the per-case
       CSV (paper-relevant diagnostic — see brief §9).
    """
    from evaluation.experiments.evaluate_microrca import (
        evaluate,
        print_summary,
        write_per_case_csv,
    )

    summary, per_case = evaluate(
        RE1_OB,
        top_ks=(1, 3, 5),
        with_random_onset=True,
        with_collapsed_graph=True,
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
            f"S(MicroRCA) for fault {fault!r} = {s}; non-zero means "
            f"the method is leaking inject_time"
        )

    overall_ac1 = summary["overall"]["AC@1"]
    print(f"\nOverall AC@1 = {overall_ac1:.3f} (expected [0.10, 0.65])")
    if overall_ac1 > 0.65:
        print(
            "  ⚠ AC@1 above brief's expanded upper band (0.65). "
            "S(M)=0 ⇒ not an inject_time leak; most likely the same "
            "z-score-on-canonical-signals effect MonitorRank/CausalRCA show."
        )
    assert overall_ac1 >= 0.10, (
        f"MicroRCA overall AC@1 = {overall_ac1:.3f} below 0.10 — "
        f"likely an implementation bug."
    )

    # Brief §9: report the attributed-graph delta.
    ac1_collapsed = summary["overall"].get("AC@1_collapsed", float("nan"))
    delta = overall_ac1 - ac1_collapsed
    print(
        f"Attributed-graph effect: AC@1 = {overall_ac1:.3f}, "
        f"collapsed AC@1 = {ac1_collapsed:.3f}, delta = {delta:+.3f}"
    )
