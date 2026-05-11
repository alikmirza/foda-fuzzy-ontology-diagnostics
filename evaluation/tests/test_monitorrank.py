"""Tests for ``evaluation.methods.monitorrank`` on :class:`NormalizedCase`.

Three groups of tests live here:

1. **Contract** on the small RCAEval fake fixture — confirms the
   method returns a well-shaped :class:`DiagnosticOutput`.
2. **Synthetic 3-service and 5-service scenarios** where a single
   service is obviously anomalous; MonitorRank should rank it top-1.
3. **RE1-OB sanity check** on all 125 real cases (skipped if the
   dataset isn't local). Writes per-fault-type AC@1/3/5 and MRR to
   ``results/week2_monitorrank_validation.csv`` and prints a comparison
   table against the MicroCause / MicroRank baselines published in
   RCAEval (Pham et al., WWW 2025, Table 5).
"""

from __future__ import annotations

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
from evaluation.methods.monitorrank import MonitorRankMethod


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
    / "week2_monitorrank_validation.csv"
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


def _flat_signal(value: float, n: int, noise: float = 0.005,
                 seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return value + rng.normal(0.0, noise, size=n)


def _step_signal(
    baseline: float,
    spike: float,
    n: int,
    inject_idx: int,
    noise: float = 0.005,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = baseline + rng.normal(0.0, noise, size=n)
    out[inject_idx:] += spike
    return out


# ---- contract tests on the fake fixture ----


class TestContractOnFakeFixture:
    """All contract invariants on the small RCAEval fake fixture."""

    def test_returns_diagnostic_output(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "monitorrank"
        assert out.wall_time_ms >= 0.0

    def test_ranked_list_non_empty_and_sorted(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        assert len(out.ranked_list) >= 1
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_explanation_chain_has_atoms_and_no_links(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        atoms = list(out.explanation_chain.atoms())
        assert 1 <= len(atoms) <= 3
        # MonitorRank emits a flat list, not a causal narrative.
        assert list(out.explanation_chain.links()) == []

    def test_confidence_in_unit_interval(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_raw_output_covers_all_services_including_frontend(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        # raw_output is keyed by service, even the (excluded) frontend.
        assert set(out.raw_output) == {"cartservice", "frontend"}

    def test_cartservice_outranks_frontend_on_cpu_anomaly(self):
        out = MonitorRankMethod().diagnose(_ob_case())
        top_service, _ = out.ranked_list[0]
        assert top_service == "cartservice"

    def test_deterministic_across_runs(self):
        case = _ob_case()
        a = MonitorRankMethod().diagnose(case)
        b = MonitorRankMethod().diagnose(case)
        assert a.ranked_list == b.ranked_list
        assert a.confidence == b.confidence


# ---- frontend selection ----


class TestFrontendSelection:
    def test_explicit_frontend_excluded_from_rank(self):
        out = MonitorRankMethod(frontend_service="cartservice").diagnose(_ob_case())
        services_in_rank = {s for s, _ in out.ranked_list}
        assert "cartservice" not in services_in_rank
        assert "frontend" in services_in_rank

    def test_unknown_frontend_param_raises(self):
        with pytest.raises(ValueError, match="frontend_service"):
            MonitorRankMethod(frontend_service="nope").diagnose(_ob_case())

    def test_no_frontend_match_excludes_no_service(self):
        """A case whose services don't match any name hint should rank
        every service (no automatic seed exclusion)."""
        n = 500
        inject_idx = 250
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "alpha-service_latency": _flat_signal(0.1, n, seed=1),
            "alpha-service_traffic": _flat_signal(100.0, n, noise=1.0, seed=2),
            "alpha-service_cpu": _flat_signal(0.3, n, seed=3),
            "beta-service_latency": _step_signal(0.1, 0.5, n, inject_idx, seed=4),
            "beta-service_traffic": _flat_signal(100.0, n, noise=1.0, seed=5),
            "beta-service_cpu": _step_signal(0.3, 0.4, n, inject_idx, seed=6),
        })
        case = _make_case(df, inject_time=float(inject_idx), root_cause="beta-service")
        out = MonitorRankMethod().diagnose(case)
        ranked_services = [s for s, _ in out.ranked_list]
        # Both services rank; the anomalous one wins.
        assert set(ranked_services) == {"alpha-service", "beta-service"}
        assert ranked_services[0] == "beta-service"


# ---- input validation ----


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
            MonitorRankMethod().diagnose(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            MonitorRankMethod().diagnose(case)

    def test_metrics_with_no_services_raises(self):
        case = _make_case(
            pd.DataFrame({"time": [0.0, 1.0, 2.0], "scalar": [1.0, 2.0, 3.0]}),
            inject_time=1.0,
            root_cause="?",
        )
        with pytest.raises(ValueError, match="services"):
            MonitorRankMethod().diagnose(case)

    @pytest.mark.parametrize("alpha", [-0.1, 0.0, 1.0, 1.5])
    def test_alpha_must_be_in_open_unit_interval(self, alpha):
        with pytest.raises(ValueError, match="alpha"):
            MonitorRankMethod(alpha=alpha)

    def test_top_k_must_be_positive(self):
        with pytest.raises(ValueError, match="top_k"):
            MonitorRankMethod(top_k=0)

    def test_n_iters_must_be_positive(self):
        with pytest.raises(ValueError, match="n_iters"):
            MonitorRankMethod(n_iters=0)

    @pytest.mark.parametrize("threshold", [-0.1, 1.1])
    def test_corr_threshold_must_be_in_unit_interval(self, threshold):
        with pytest.raises(ValueError, match="corr_threshold"):
            MonitorRankMethod(corr_threshold=threshold)


# ---- synthetic scenarios with an obvious anomaly ----


def _three_service_case(seed: int = 0) -> BenchmarkCase:
    """3-service call chain ``frontend → cart → db`` where ``db_cpu``
    steps up at injection. Latency and traffic of the upstream services
    track each other so the correlation-derived graph is connected."""
    n = 1000
    inject_idx = 500
    rng = np.random.default_rng(seed)

    db_cpu_baseline = 0.20
    db_cpu = db_cpu_baseline + rng.normal(0.0, 0.02, n)
    db_cpu[inject_idx:] += 0.60  # huge step

    # Latency: shared traffic shape across the chain, plus per-service noise
    base_latency = 0.10 + 0.02 * np.sin(np.linspace(0, 6 * np.pi, n))
    frontend_latency = base_latency + rng.normal(0.0, 0.01, n)
    cart_latency = base_latency + rng.normal(0.0, 0.01, n)
    db_latency = base_latency + rng.normal(0.0, 0.01, n)
    db_latency[inject_idx:] += 0.20  # latency follows the resource spike

    base_traffic = 100 + 5 * np.sin(np.linspace(0, 4 * np.pi, n))
    frontend_traffic = base_traffic + rng.normal(0.0, 1.0, n)
    cart_traffic = base_traffic + rng.normal(0.0, 1.0, n)
    db_traffic = base_traffic + rng.normal(0.0, 1.0, n)

    df = pd.DataFrame({
        "time": np.arange(n, dtype=float),
        "frontend_latency": frontend_latency,
        "frontend_traffic": frontend_traffic,
        "frontend_cpu": 0.15 + rng.normal(0.0, 0.01, n),
        "cart_latency": cart_latency,
        "cart_traffic": cart_traffic,
        "cart_cpu": 0.25 + rng.normal(0.0, 0.01, n),
        "db_latency": db_latency,
        "db_traffic": db_traffic,
        "db_cpu": db_cpu,
    })
    return _make_case(df, inject_time=float(inject_idx),
                      root_cause="db", case_id="synthetic_3svc")


def _five_service_case(seed: int = 0) -> BenchmarkCase:
    """5-service fan-out where ``inventory`` is the root cause.

    Topology: ``frontend → {cart, search}``; ``cart → {payment,
    inventory}``. The injected fault spikes ``inventory_cpu`` and
    ``inventory_latency`` post-injection."""
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

    return _make_case(
        pd.DataFrame(df),
        inject_time=float(inject_idx),
        root_cause="inventory",
        case_id="synthetic_5svc",
    )


class TestSyntheticScenarios:
    def test_three_service_chain_ranks_anomaly_top_1(self):
        out = MonitorRankMethod().diagnose(_three_service_case())
        top_service, _ = out.ranked_list[0]
        assert top_service == "db"

    def test_five_service_fanout_ranks_anomaly_top_1(self):
        out = MonitorRankMethod().diagnose(_five_service_case())
        top_service, _ = out.ranked_list[0]
        assert top_service == "inventory"

    def test_three_service_flat_no_anomaly_does_not_crash(self):
        """Sanity: when no signal exists anywhere, the method must
        still return a well-formed output with all services ranked."""
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
        out = MonitorRankMethod().diagnose(case)
        assert {s for s, _ in out.ranked_list} == {"cart", "db"}

    def test_five_service_explanation_atom_tags_dominant_feature(self):
        """The top-3 explanation atoms must name the dominant feature
        (latency / cpu / etc.) that earned the service its z-score."""
        out = MonitorRankMethod().diagnose(_five_service_case())
        atoms = list(out.explanation_chain.atoms())
        # inventory is top → its atom must mention cpu or latency.
        top_atom = atoms[0]
        assert "inventory" in top_atom.text
        assert "cpu" in top_atom.text or "latency" in top_atom.text

    def test_three_service_explicit_frontend_excludes_seed(self):
        out = MonitorRankMethod(frontend_service="frontend").diagnose(
            _three_service_case()
        )
        ranked = {s for s, _ in out.ranked_list}
        assert "frontend" not in ranked
        assert "db" in ranked


# ---- RE1-OB sanity check (skipped if data is not local) ----


# Published AC@1 baselines from RCAEval (Pham et al., WWW 2025), Table 5,
# averaged across the OB results for the comparable random-walk family.
# Used only for sanity-checking — we flag >20 percentage-point deviations.
_RCAEVAL_TABLE5_BASELINES = {
    "MicroCause": {"cpu": 0.19, "mem": 0.32, "disk": 0.13, "delay": 0.10, "loss": 0.18},
    "MicroRank":  {"cpu": 0.21, "mem": 0.25, "disk": 0.20, "delay": 0.15, "loss": 0.15},
}


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_ac_at_k_sanity_check():
    """Run MonitorRank on every RE1-OB case via the shared
    :mod:`evaluation.experiments.evaluate_monitorrank` harness, persist
    per-case results, and assert:

    1. ``S(M) ≈ 0`` overall and per-fault — MonitorRank does NOT read
       ``ground_truth.inject_time``, so shifting it by ±300 s must not
       move AC@1. This is the empirical proof of the inject_time-
       removal contract; any non-zero ``S`` is a leak.

    2. AC@1 is within 20 pp of MicroCause or MicroRank on at least one
       fault type. The published baselines come from RCAEval (Pham et
       al., WWW 2025) Table 5; the test exists to catch a wholly broken
       implementation, not to demand parity.

    CHANGED (was passing on leakage): the prior version inlined its own
    evaluation loop and reported AC@1 numbers that were inflated by
    fenceposting on ``inject_time``. Numbers now come from the shared
    harness which runs MonitorRank against the new inject-time-clean
    contract, so the AC@1 column reflects the algorithm's true ability
    to find the root cause without that hint.
    """
    from evaluation.experiments.evaluate_monitorrank import (
        evaluate,
        print_summary,
        write_per_case_csv,
    )

    summary, per_case = evaluate(RE1_OB, top_ks=(1, 3, 5))
    write_per_case_csv(per_case, RESULTS_PATH, top_ks=(1, 3, 5))
    print(f"\nWrote per-case results to {RESULTS_PATH}")
    print()
    print_summary(summary, top_ks=(1, 3, 5))

    # ---- baseline-comparison table ----
    print()
    print("Per-fault comparison vs. RCAEval Table 5 baselines:")
    bh = (
        f"{'fault':<8} {'AC@1':>7} {'MicroCause@1':>14} "
        f"{'MicroRank@1':>13} {'baseline_flag':>15}"
    )
    print(bh)
    print("-" * len(bh))
    baseline_flags: list[str] = []
    for fault in ("cpu", "mem", "disk", "delay", "loss"):
        if fault not in summary:
            continue
        ac1 = summary[fault]["AC@1"]
        mc1 = _RCAEVAL_TABLE5_BASELINES["MicroCause"].get(fault, float("nan"))
        mr1 = _RCAEVAL_TABLE5_BASELINES["MicroRank"].get(fault, float("nan"))
        gap_mc = abs(ac1 - mc1)
        gap_mr = abs(ac1 - mr1)
        flag = "OK" if (gap_mc <= 0.20 or gap_mr <= 0.20) else "FLAG"
        baseline_flags.append(flag)
        print(
            f"{fault:<8} {ac1:>7.3f} {mc1:>14.3f} {mr1:>13.3f} {flag:>15}"
        )

    # ---- assertions ----
    # 1. Inject-time invariance: S(M) per fault must be ~0.
    for fault, row in summary.items():
        if fault == "overall":
            continue
        s = row.get("S", float("nan"))
        # Methods that don't read ground_truth must score S == 0 (every
        # shifted run returns the identical AC@1). Tolerance is
        # nominally 0 — anything else indicates the shift somehow
        # bled into the method's behavior.
        assert s == 0.0 or (isinstance(s, float) and (s != s)), (  # NaN OK
            f"S(MonitorRank) for fault {fault!r} = {s}; non-zero means "
            f"the method is leaking inject_time"
        )

    # 2. At least one fault type within 20 pp of *either* published
    # baseline — guards against the algorithm being trivially broken
    # without the inject_time crutch.
    assert any(f == "OK" for f in baseline_flags), (
        "MonitorRank AC@1 is >20 pp away from BOTH MicroCause and "
        "MicroRank on every fault type. Either the published baselines "
        "in _RCAEVAL_TABLE5_BASELINES are wrong, or the implementation "
        "regressed badly after the inject_time-removal refactor."
    )
