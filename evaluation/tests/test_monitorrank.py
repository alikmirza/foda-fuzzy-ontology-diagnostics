"""Tests for ``evaluation.methods.monitorrank``.

These tests cover the contract MonitorRank exposes to the evaluation
harness: that it produces a non-empty ranking on real-shaped inputs,
emits a top-K explanation chain, and behaves deterministically. They
do not assert anything about RCA *correctness* — that comparison
against published numbers happens against the real RCAEval data, not
the fake fixture.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from evaluation.benchmarks.foda12_loader import Foda12Loader
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader
from evaluation.extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
)
from evaluation.methods.monitorrank import MonitorRankMethod

FIXTURES = Path(__file__).parent / "fixtures"
RCAEVAL_FIXTURE = FIXTURES / "rcaeval_fake"
FODA12_FIXTURE = FIXTURES / "foda12_fake"


# ---- contract on the fake RCAEval fixture ----


def _ob_case() -> BenchmarkCase:
    return RCAEvalLoader(RCAEVAL_FIXTURE).get_case("OB_cartservice_CPU_1")


def test_returns_diagnostic_output_on_rcaeval_fixture():
    out = MonitorRankMethod().diagnose(_ob_case())
    assert isinstance(out, DiagnosticOutput)
    assert out.method_name == "monitorrank"
    assert out.wall_time_ms >= 0.0


def test_ranked_list_non_empty_and_sorted():
    out = MonitorRankMethod().diagnose(_ob_case())
    assert len(out.ranked_list) >= 1
    scores = [score for _, score in out.ranked_list]
    assert scores == sorted(scores, reverse=True)


def test_explanation_chain_has_at_least_one_atom():
    out = MonitorRankMethod().diagnose(_ob_case())
    assert isinstance(out.explanation_chain, CanonicalExplanation)
    atoms = list(out.explanation_chain.atoms())
    assert len(atoms) >= 1
    # MonitorRank is a flat ranker — no causal narrative.
    assert list(out.explanation_chain.links()) == []


def test_confidence_is_in_unit_interval():
    out = MonitorRankMethod().diagnose(_ob_case())
    assert out.confidence is not None
    assert 0.0 <= out.confidence <= 1.0


def test_raw_output_covers_all_services():
    case = _ob_case()
    out = MonitorRankMethod().diagnose(case)
    # OB_cartservice_CPU_1 has columns frontend_* and cartservice_*.
    assert set(out.raw_output) == {"cartservice", "frontend"}


def test_cartservice_outranks_frontend_on_cpu_anomaly():
    """Sanity check on a case the algorithm should obviously get right.

    The fixture spikes ``cartservice_cpu`` while ``frontend_*`` stays
    flat; with frontend auto-detected as the seed, MonitorRank should
    place ``cartservice`` at the top of the candidate list.
    """
    out = MonitorRankMethod().diagnose(_ob_case())
    top_service, _ = out.ranked_list[0]
    assert top_service == "cartservice"


def test_deterministic_across_runs():
    case = _ob_case()
    a = MonitorRankMethod().diagnose(case)
    b = MonitorRankMethod().diagnose(case)
    assert a.ranked_list == b.ranked_list
    assert a.confidence == b.confidence


# ---- topology handling ----


def test_runs_with_topology_omitted():
    """No topology + no name match → fully-connected fallback still ranks."""
    case = _ob_case()
    assert case.system_topology is None
    out = MonitorRankMethod().diagnose(case)
    assert len(out.ranked_list) >= 1


def test_explicit_topology_propagates_via_foda12():
    """FODA-12 cases supply an explicit ``system_topology`` mapping."""
    case = Foda12Loader(FODA12_FIXTURE).get_case("S01")
    out = MonitorRankMethod().diagnose(case)
    services_in_rank = {s for s, _ in out.ranked_list}
    # Frontend is excluded by paper convention; the other two services
    # must show up.
    assert "service-B" in services_in_rank
    assert "service-C" in services_in_rank


# ---- frontend selection ----


def test_explicit_frontend_param_overrides_autodetect():
    case = _ob_case()
    out = MonitorRankMethod(frontend_service="cartservice").diagnose(case)
    # cartservice is now the seed → it must NOT appear in the rank.
    assert "cartservice" not in {s for s, _ in out.ranked_list}
    assert "frontend" in {s for s, _ in out.ranked_list}


def test_unknown_frontend_param_raises():
    case = _ob_case()
    with pytest.raises(ValueError, match="frontend_service"):
        MonitorRankMethod(frontend_service="nope").diagnose(case)


# ---- input validation ----


def test_rejects_case_without_metrics():
    case = BenchmarkCase(
        id="bad",
        telemetry={},  # no 'metrics' key
        ground_truth_root_cause="x",
        ground_truth_fault_type="y",
        system_topology=None,
    )
    with pytest.raises(ValueError, match="metrics"):
        MonitorRankMethod().diagnose(case)


def test_rejects_unparseable_metrics_dataframe():
    """A DataFrame whose columns can't be split into <service>_<metric>."""
    case = BenchmarkCase(
        id="bad",
        telemetry={"metrics": pd.DataFrame({"time": [0, 1], "x": [0.0, 1.0]})},
        ground_truth_root_cause="x",
        ground_truth_fault_type="y",
        system_topology=None,
    )
    with pytest.raises(ValueError, match="per-service metrics"):
        MonitorRankMethod().diagnose(case)


# ---- hyperparameter validation ----


@pytest.mark.parametrize("alpha", [-0.1, 0.0, 1.0, 1.5])
def test_alpha_must_be_strictly_in_unit_interval(alpha):
    with pytest.raises(ValueError, match="alpha"):
        MonitorRankMethod(alpha=alpha)


@pytest.mark.parametrize("rho", [-0.1, 1.0, 1.5])
def test_rho_must_be_in_half_open_unit_interval(rho):
    with pytest.raises(ValueError, match="rho"):
        MonitorRankMethod(rho=rho)


def test_top_k_must_be_positive():
    with pytest.raises(ValueError, match="top_k"):
        MonitorRankMethod(top_k=0)
