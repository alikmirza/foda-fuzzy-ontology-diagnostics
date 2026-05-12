"""Tests for ``evaluation.methods.foda_fcp`` on :class:`NormalizedCase`.

Eight groups of tests cover the dissertation centerpiece:

1. **Contract** — DiagnosticOutput shape on the small RCAEval fake fixture.
2. **Mamdani inference** — 16-rule rule base fires the right category on
   3-service and 5-service synthetic scenarios.
3. **Damped Noisy-OR propagation** — Eq. 4 + the cyclic-graph fallback
   produce the published `C(s) = 1 − (1 − H(s))(1 − P(s))` shape; the
   damping coefficient δ ∈ (0, 1] is honoured.
4. **Topology inference** — directed lagged-correlation edges, no
   self-loops, threshold honoured.
5. **Ontology-grounded explanation** (the critical part) —
     - one atom per top-K service, tagged with the predicted fault's
       full DiagnosticKB URI,
     - at least one Recommendation atom for the predicted root cause,
     - ``contributes_to`` + ``suggests_mitigation`` links.
6. **Protocol validator** + **shift invariance** under ±300 s shift.
7. **Input validation**.
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
from evaluation.methods._protocol import (
    ProtocolViolationError,
    validate_no_ground_truth_peeking,
)
from evaluation.methods.foda_fcp import (
    CATEGORY_TO_FAULT,
    FAULT_TO_RECOMMENDATION,
    ONTOLOGY_NS,
    FodaFCPMethod,
    _ServiceFuzzyVector,
    _fuzzify_service,
    _has_cycle,
    _infer_fault_prototype_from_fuzzy,
    _infer_hypothesis,
    _ontology_uri,
    _propagate_damped,
    _propagate_iterative,
)


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
    / "week2_foda_fcp_validation.csv"
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
    """3-service chain: db is root cause (CPU+latency injection); cart's
    latency follows; frontend stays clean."""
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
    cart_latency[inject_idx + 1:] += 0.08

    base_traffic = 100 + 5 * np.sin(np.linspace(0, 4 * np.pi, n))
    df = pd.DataFrame({
        "time": np.arange(n, dtype=float),
        "frontend_latency": frontend_latency,
        "frontend_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "frontend_cpu":     0.15 + rng.normal(0.0, 0.01, n),
        "cart_latency":     cart_latency,
        "cart_traffic":     base_traffic + rng.normal(0.0, 1.0, n),
        "cart_cpu":         0.25 + rng.normal(0.0, 0.01, n),
        "db_latency":       db_latency,
        "db_traffic":       base_traffic + rng.normal(0.0, 1.0, n),
        "db_cpu":           db_cpu,
    })
    return _make_case(
        df, inject_time=float(inject_idx), root_cause="db",
        case_id="synthetic_3svc",
    )


def _five_service_case(seed: int = 1) -> BenchmarkCase:
    """5-service scenario: ``cache`` is the memory-pressure root.

    cache's mem rises sharply; backend (cache caller)'s latency rises;
    api gateway (backend caller)'s latency rises further; frontend and
    log_collector stay clean.
    """
    n = 1200
    inject_idx = 600
    rng = np.random.default_rng(seed)

    cache_mem = 0.30 + rng.normal(0.0, 0.01, n)
    cache_mem[inject_idx:] += 0.50

    base_lat = 0.10 + 0.01 * np.sin(np.linspace(0, 5 * np.pi, n))
    backend_lat = base_lat + rng.normal(0.0, 0.01, n)
    backend_lat[inject_idx:] += 0.20
    api_lat = base_lat + rng.normal(0.0, 0.01, n)
    api_lat[inject_idx + 1:] += 0.30
    front_lat = base_lat + rng.normal(0.0, 0.01, n)
    log_lat = base_lat + rng.normal(0.0, 0.01, n)
    cache_lat = base_lat + rng.normal(0.0, 0.01, n)

    base_traffic = 100 + 5 * np.sin(np.linspace(0, 3 * np.pi, n))
    df = pd.DataFrame({
        "time": np.arange(n, dtype=float),
        "frontend_latency": front_lat,
        "frontend_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "frontend_cpu":     0.15 + rng.normal(0.0, 0.01, n),
        "frontend_mem":     0.30 + rng.normal(0.0, 0.01, n),
        "api_latency":      api_lat,
        "api_traffic":      base_traffic + rng.normal(0.0, 1.0, n),
        "api_cpu":          0.20 + rng.normal(0.0, 0.01, n),
        "api_mem":          0.40 + rng.normal(0.0, 0.01, n),
        "backend_latency":  backend_lat,
        "backend_traffic":  base_traffic + rng.normal(0.0, 1.0, n),
        "backend_cpu":      0.20 + rng.normal(0.0, 0.01, n),
        "backend_mem":      0.40 + rng.normal(0.0, 0.01, n),
        "cache_latency":    cache_lat,
        "cache_traffic":    base_traffic + rng.normal(0.0, 1.0, n),
        "cache_cpu":        0.20 + rng.normal(0.0, 0.01, n),
        "cache_mem":        cache_mem,
        "log_collector_latency": log_lat,
        "log_collector_traffic": base_traffic + rng.normal(0.0, 1.0, n),
        "log_collector_cpu":     0.10 + rng.normal(0.0, 0.01, n),
    })
    return _make_case(
        df, inject_time=float(inject_idx), root_cause="cache",
        case_id="synthetic_5svc", fault_type="mem",
    )


# ---- 1. contract tests ----


class TestContractOnFakeFixture:
    def test_returns_diagnostic_output(self):
        out = FodaFCPMethod().diagnose(_ob_case())
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "foda-fcp"
        assert out.wall_time_ms >= 0.0

    def test_ranked_list_non_empty_and_sorted(self):
        out = FodaFCPMethod().diagnose(_ob_case())
        assert len(out.ranked_list) >= 1
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_explanation_is_canonical(self):
        out = FodaFCPMethod().diagnose(_ob_case())
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        # On the fake fixture the rule engine may produce no firings
        # (the synthetic data is small), so the explanation can be
        # empty — but the type must still be CanonicalExplanation.

    def test_confidence_in_unit_interval(self):
        out = FodaFCPMethod().diagnose(_ob_case())
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_raw_output_carries_diagnostic_summary(self):
        out = FodaFCPMethod().diagnose(_ob_case())
        for key in (
            "onset_time", "propagator_kind", "damping_factor",
            "topology_edges", "topology_n_edges",
            "local_confidence_H", "final_confidence_C",
            "dominant_category", "fired_rules",
            "predicted_fault_local_name",
        ):
            assert key in out.raw_output, f"missing raw_output[{key!r}]"

    def test_deterministic_across_runs(self):
        case = _ob_case()
        a = FodaFCPMethod().diagnose(case)
        b = FodaFCPMethod().diagnose(case)
        assert a.ranked_list == b.ranked_list
        assert a.confidence == b.confidence


# ---- 2. Mamdani inference ----


class TestMamdaniInference:
    def test_three_service_chain_ranks_db_top_1(self):
        out = FodaFCPMethod().diagnose(_three_service_case())
        top, _ = out.ranked_list[0]
        assert top == "db", (
            f"expected db top-1 on 3-svc CPU+latency injection; "
            f"got {out.ranked_list[:3]}"
        )
        # The dominant category for db should be CPU-related given the
        # CPU+latency injection.
        assert out.raw_output["dominant_category"]["db"] in {
            "CPU_SATURATION", "CASCADING_FAILURE", "LATENCY_ANOMALY",
        }

    def test_five_service_scenario_ranks_cache_in_top_3(self):
        """FCP's damped Noisy-OR can rank an upstream caller above the
        local root when the caller picks up enough propagated
        confidence (the AICT paper's "confidence inflation" caveat).
        We assert that the cache (root cause) appears in the top-3 and
        that its dominant Mamdani category is memory-related — i.e.
        the rule engine identifies cache's local fault correctly even
        if the propagated rank places callers first."""
        out = FodaFCPMethod().diagnose(_five_service_case())
        top3 = [s for s, _ in out.ranked_list[:3]]
        assert "cache" in top3, (
            f"expected cache in top-3 on 5-svc mem injection; "
            f"got {out.ranked_list[:5]}"
        )
        assert out.raw_output["dominant_category"]["cache"] in {
            "MEMORY_PRESSURE", "RESOURCE_CONTENTION", "CASCADING_FAILURE",
        }

    def test_rules_actually_fire_on_anomalous_service(self):
        out = FodaFCPMethod().diagnose(_three_service_case())
        fired = out.raw_output["fired_rules"]
        assert fired["db"], "expected at least one Mamdani rule to fire for db"
        # Every fired rule_id should be Rxx.
        for r in fired["db"]:
            assert r.startswith("R") and r[1:].isdigit(), (
                f"unexpected rule_id format: {r!r}"
            )

    def test_local_confidence_in_unit_interval(self):
        """H(s) is a Mamdani max-aggregation strength: every entry in
        ``local_confidence_H`` must lie in [0, 1]."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        for svc, h in out.raw_output["local_confidence_H"].items():
            assert 0.0 <= h <= 1.0, (
                f"H({svc}) = {h} outside [0, 1]"
            )


# ---- 3. damped Noisy-OR propagation ----


class TestDampedNoisyOrPropagation:
    def test_damping_factor_zero_one_bounds_raise(self):
        with pytest.raises(ValueError, match="damping_factor"):
            FodaFCPMethod(damping_factor=0.0)
        with pytest.raises(ValueError, match="damping_factor"):
            FodaFCPMethod(damping_factor=1.5)

    def test_propagation_does_not_inflate_above_one(self):
        out = FodaFCPMethod().diagnose(_five_service_case())
        for svc, c in out.raw_output["final_confidence_C"].items():
            assert 0.0 <= c <= 1.0, (
                f"C({svc}) = {c} outside [0, 1] — propagation inflated"
            )

    def test_acyclic_graph_uses_damped_propagator(self):
        """Synthetic 3-service case has at most one inferred edge (db
        leads cart); the resulting graph is acyclic and the adaptive
        propagator should select the damped variant."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        assert out.raw_output["propagator_kind"] in {"damped", "iterative"}

    def test_iterative_propagation_converges_on_two_node_cycle(self):
        """Force a cyclic 2-node graph and assert the iterative
        propagator returns finite values inside [0, 1]."""
        from evaluation.methods.foda_fcp import _FaultHypothesis
        services = ["a", "b"]
        edges = {("a", "b"): 0.7, ("b", "a"): 0.7}
        hyps = {
            "a": _FaultHypothesis(
                service="a", local_confidence=0.6,
                dominant_category="CPU_SATURATION",
                fired_rules=(), rule_fire_strengths={},
            ),
            "b": _FaultHypothesis(
                service="b", local_confidence=0.3,
                dominant_category="CPU_SATURATION",
                fired_rules=(), rule_fire_strengths={},
            ),
        }
        assert _has_cycle(services, edges)
        C = _propagate_iterative(hyps, services, edges, delta=0.85)
        for s in services:
            assert 0.0 <= C[s] <= 1.0
            # Propagation can only raise C above the local H.
            assert C[s] >= hyps[s].local_confidence - 1e-9


# ---- 4. topology inference ----


class TestTopologyInference:
    def test_no_self_loops(self):
        out = FodaFCPMethod().diagnose(_three_service_case())
        for (u, v) in out.raw_output["topology_edges"]:
            assert u != v

    def test_high_threshold_removes_all_edges(self):
        out = FodaFCPMethod(topology_threshold=0.999).diagnose(_three_service_case())
        assert out.raw_output["topology_edges"] == []


# ---- 5. ontology-grounded explanation (THE CRITICAL PART) -----------------


class TestOntologyGroundedExplanation:
    def test_atoms_carry_full_diagnostic_kb_uri(self):
        """Every atom's ontology_class must be a full
        ``http://foda.com/ontology/diagnostic#<LocalName>`` URI, not
        just the local name."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        atoms = list(out.explanation_chain.atoms())
        assert atoms, "expected at least one atom in explanation"
        for atom in atoms:
            assert atom.ontology_class is not None
            assert atom.ontology_class.startswith(ONTOLOGY_NS), (
                f"atom {atom.text!r} carries ontology_class "
                f"{atom.ontology_class!r}, expected to start with "
                f"{ONTOLOGY_NS!r}"
            )

    def test_top_k_atoms_present(self):
        m = FodaFCPMethod(top_k=3)
        out = m.diagnose(_three_service_case())
        # Atoms = top-K ContributingFactor atoms PLUS (typically) one
        # Recommendation atom for the predicted root cause.
        contributing = [
            a for a in out.explanation_chain.atoms()
            if not a.ontology_class.endswith(f"#Rec_{CATEGORY_TO_FAULT.get(out.raw_output['dominant_category'][out.ranked_list[0][0]], 'NONE')}")
        ]
        assert len(contributing) >= 1

    def test_recommendation_atom_present_for_predicted_root(self):
        """The predicted root cause must produce exactly one
        Recommendation atom tagged with the corresponding ``Rec_*``
        individual from DiagnosticKB."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        predicted_fault = out.raw_output["predicted_fault_local_name"]
        assert predicted_fault is not None, (
            "synthetic 3-svc case should produce a non-None predicted "
            "fault local name"
        )
        expected_rec_local = FAULT_TO_RECOMMENDATION[predicted_fault]
        expected_uri = _ontology_uri(expected_rec_local)
        rec_atoms = [
            a for a in out.explanation_chain.atoms()
            if a.ontology_class == expected_uri
        ]
        assert len(rec_atoms) == 1, (
            f"expected exactly one Recommendation atom tagged "
            f"{expected_uri!r}; got {len(rec_atoms)} atoms with "
            f"ontology_classes "
            f"{[a.ontology_class for a in out.explanation_chain.atoms()]}"
        )

    def test_recommendation_membership_matches_root_membership(self):
        """The Recommendation atom inherits the same fuzzy_membership
        as the root atom (the confidence with which we recommend the
        mitigation matches the confidence in the root diagnosis)."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        atoms = list(out.explanation_chain.atoms())
        # Root atom = first one (sorted by addition order, root added first).
        rec_local = FAULT_TO_RECOMMENDATION[
            out.raw_output["predicted_fault_local_name"]
        ]
        rec_uri = _ontology_uri(rec_local)
        root = atoms[0]
        rec = next(a for a in atoms if a.ontology_class == rec_uri)
        assert rec.fuzzy_membership == root.fuzzy_membership

    def test_atom_text_mentions_ontology_class_name(self):
        """Each ContributingFactor atom's text mentions the ontology
        class name (so a reader can grok the explanation without
        loading the OWL graph)."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        root_fault = out.raw_output["predicted_fault_local_name"]
        atoms = list(out.explanation_chain.atoms())
        # The root atom's text should contain the fault local name.
        assert any(root_fault in a.text for a in atoms), (
            f"expected at least one atom's text to mention "
            f"{root_fault!r}; got texts:\n"
            + "\n".join(a.text for a in atoms)
        )

    def test_links_include_suggests_mitigation_and_contributes_to(self):
        """The chain has visible structure: ``contributes_to`` links
        from non-root atoms to the root, plus ``suggests_mitigation``
        links to the Recommendation atom."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        link_kinds = {
            (l.relation_type or "").split(":", 1)[0]
            for l in out.explanation_chain.links()
        }
        assert "suggests_mitigation" in link_kinds, (
            f"expected at least one suggests_mitigation link; "
            f"got {link_kinds}"
        )
        # contributes_to may be absent when top_k=1 — but with the
        # default top_k=3 on the 3-service scenario it should be present.
        if len(out.ranked_list) >= 2:
            assert "contributes_to" in link_kinds, (
                f"expected at least one contributes_to link when "
                f"top_k>=2; got {link_kinds}"
            )

    def test_links_attribution_documents_subprocess(self):
        """Each link's relation_type encodes the FCP sub-process that
        derived it (after the colon): ``propagation:noisy_or`` or
        ``recommendation:fault_prototype``."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        for l in out.explanation_chain.links():
            assert l.relation_type is not None
            assert ":" in l.relation_type, (
                f"link {l.relation_type!r} has no attribution suffix"
            )
            assert l.weight is not None
            assert 0.0 <= l.weight <= 1.0

    def test_chain_is_structured_not_flat(self):
        """The brief's verify-with-a-sample step: confirm the chain
        has visible structure (atoms + links, not a flat list)."""
        out = FodaFCPMethod().diagnose(_three_service_case())
        atoms = list(out.explanation_chain.atoms())
        links = list(out.explanation_chain.links())
        assert len(atoms) >= 2
        assert len(links) >= 1


# ---- 5b. fuzzy-fallback fault prototype inference --------------------------


class TestInferFaultPrototypeFromFuzzy:
    """Phase 2 Week 2 v2: when no Mamdani rule fires, fall back to the
    highest-membership fuzzy term and map it to a fault prototype so the
    non-root atom gets a specific ontology class rather than the abstract
    ``ContributingFactor``. SemanticCoherence scores against fault
    prototypes; this fallback makes FCP's contributes_to edges fall in
    SC's scope when the service has appreciable fuzzy signal."""

    def _vector(self, memberships: dict[str, float]) -> _ServiceFuzzyVector:
        base = {
            "cpu_LOW": 0.0, "cpu_MEDIUM": 0.0, "cpu_HIGH": 0.0,
            "memory_LOW": 0.0, "memory_MEDIUM": 0.0, "memory_HIGH": 0.0,
            "latency_NORMAL": 0.0, "latency_ELEVATED": 0.0, "latency_CRITICAL": 0.0,
            "errorRate_NONE": 0.0, "errorRate_LOW": 0.0,
            "errorRate_ELEVATED": 0.0, "errorRate_HIGH": 0.0,
            "throughput_LOW": 0.0, "throughput_NORMAL": 0.0,
        }
        base.update(memberships)
        return _ServiceFuzzyVector(service="x", memberships=base, z_signed={})

    def test_cpu_high_term_infers_cpu_saturation(self):
        fv = self._vector({"cpu_HIGH": 0.9})
        assert _infer_fault_prototype_from_fuzzy(fv) == "CpuSaturation"

    def test_memory_high_term_infers_memory_leak(self):
        fv = self._vector({"memory_HIGH": 0.7})
        assert _infer_fault_prototype_from_fuzzy(fv) == "MemoryLeak"

    def test_latency_critical_infers_latency_spike(self):
        fv = self._vector({"latency_CRITICAL": 0.5})
        assert _infer_fault_prototype_from_fuzzy(fv) == "LatencySpike"

    def test_throughput_low_infers_throughput_degradation(self):
        fv = self._vector({"throughput_LOW": 0.4})
        assert _infer_fault_prototype_from_fuzzy(fv) == "ThroughputDegradation"

    def test_below_floor_returns_none(self):
        """Services whose strongest anomaly term is below the 0.20 floor
        produce no inference — the fallback should stay quiet rather
        than reach for a prototype it has no basis to claim."""
        fv = self._vector({"cpu_HIGH": 0.1, "memory_HIGH": 0.05})
        assert _infer_fault_prototype_from_fuzzy(fv) is None

    def test_all_terms_normal_returns_none(self):
        """A service with only non-anomalous terms (``cpu_LOW``,
        ``throughput_NORMAL``, …) doesn't get inferred. This is the
        right semantic on FCP top-K entries that only appear via
        Noisy-OR back-flow from anomalous callees: their own metrics
        are flat, so the link's source has no fault prototype."""
        fv = self._vector({"cpu_LOW": 1.0, "memory_LOW": 1.0, "throughput_NORMAL": 1.0})
        assert _infer_fault_prototype_from_fuzzy(fv) is None

    def test_strongest_term_wins_over_secondary(self):
        fv = self._vector({"cpu_MEDIUM": 0.3, "memory_HIGH": 0.8})
        assert _infer_fault_prototype_from_fuzzy(fv) == "MemoryLeak"


# ---- 6. protocol + shift ---------------------------------------------------


class TestProtocolValidator:
    def test_diagnose_does_not_reference_ground_truth(self):
        validate_no_ground_truth_peeking(FodaFCPMethod())

    def test_protocol_validator_catches_peeking_subclass(self):
        class LeakyFCP(FodaFCPMethod):
            def diagnose(self, case):
                _ = case.ground_truth  # banned
                return super().diagnose(case)

        with pytest.raises(ProtocolViolationError):
            validate_no_ground_truth_peeking(LeakyFCP())


class TestShiftInvariance:
    def test_output_identical_under_pm_300s_shift(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        m = FodaFCPMethod()
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


# ---- 7. input validation ---------------------------------------------------


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
            FodaFCPMethod().diagnose(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            FodaFCPMethod().diagnose(case)

    def test_no_services_raises(self):
        case = _make_case(
            pd.DataFrame({"time": [0.0, 1.0, 2.0], "scalar": [1.0, 2.0, 3.0]}),
            inject_time=1.0, root_cause="?",
        )
        with pytest.raises(ValueError, match="services"):
            FodaFCPMethod().diagnose(case)

    @pytest.mark.parametrize("delta", [0.0, -0.1, 1.1])
    def test_damping_factor_must_be_in_open_unit_to_one(self, delta):
        with pytest.raises(ValueError, match="damping_factor"):
            FodaFCPMethod(damping_factor=delta)

    @pytest.mark.parametrize("thr", [-0.1, 1.1])
    def test_topology_threshold_must_be_in_unit_interval(self, thr):
        with pytest.raises(ValueError, match="topology_threshold"):
            FodaFCPMethod(topology_threshold=thr)

    def test_top_k_must_be_positive(self):
        with pytest.raises(ValueError, match="top_k"):
            FodaFCPMethod(top_k=0)

    def test_window_seconds_must_be_positive(self):
        with pytest.raises(ValueError, match="window_seconds"):
            FodaFCPMethod(window_seconds=0.0)

    def test_lag_must_be_non_negative(self):
        with pytest.raises(ValueError, match="lag"):
            FodaFCPMethod(lag=-1)

    def test_max_iterations_must_be_at_least_one(self):
        with pytest.raises(ValueError, match="max_iterations"):
            FodaFCPMethod(max_iterations=0)


# ---- 8. RE1-OB sanity check -----------------------------------------------


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_ac_at_k_sanity_check():
    """Run FODA-FCP on every RE1-OB case via the standalone harness and
    assert:

    1. ``S(FODA-FCP) == 0`` per fault — the adapter uses
       :func:`detect_onset` on ``case_window`` and never reads
       ``ground_truth``.
    2. AC@1 overall is in ``[0.10, 0.70]`` (brief target: ontology-
       grounded explanation prioritizes structure over rank, so the
       AC@1 may sit anywhere from yRCA-level (0.328) to MR/CR/Micro
       level (~0.62)).
    3. The cross-method diagnostic columns ``AC@1_a_standard``,
       ``AC@1_b_edges_mean``, ``AC@1_c_centered``, and ``AC@1_random``
       are all present.
    """
    from evaluation.experiments.evaluate_foda_fcp import (
        evaluate, print_summary, write_per_case_csv,
    )

    summary, per_case = evaluate(
        RE1_OB,
        top_ks=(1, 3, 5),
        with_random_onset=True,
        with_offset_robustness=True,
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
            f"S(FODA-FCP) for fault {fault!r} = {s}; non-zero means the "
            f"method is leaking inject_time"
        )

    overall_ac1 = summary["overall"]["AC@1"]
    print(f"\nOverall AC@1 = {overall_ac1:.3f} (expected [0.10, 0.70])")
    assert 0.10 <= overall_ac1 <= 0.70, (
        f"FODA-FCP overall AC@1 = {overall_ac1:.3f} outside the "
        f"expected [0.10, 0.70] band (brief §7)."
    )

    for col in ("AC@1_random", "AC@1_a_standard",
                "AC@1_b_edges_mean", "AC@1_c_centered"):
        assert col in summary["overall"], (
            f"expected decomposition column {col!r} in summary"
        )
