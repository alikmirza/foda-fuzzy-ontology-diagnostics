"""Tests for ``evaluation.methods.yrca`` on :class:`NormalizedCase`.

Eight groups of tests:

1. **Contract** on the small RCAEval fake fixture.
2. **Synthetic-event generation** — anomaly events are emitted for
   service-feature pairs whose post-onset z exceeds the threshold;
   normal events appear only when ``emit_normal_events=True``.
3. **Topology inference** — directed edges along correlation lines,
   no self-loops, threshold is honoured.
4. **Forward-chaining inference** — R1/R2/R3 fire and termination is
   reached within ``max_iterations``; R4/R5 add multi-rule
   derivations.
5. **Ranking** — final_root_cause services rank above non-roots; ties
   broken by severity.
6. **Explanation shape** — role-tagged atoms, ``rule_derived_explanation``
   links, ``yrca:Role/*`` ontology classes.
7. **Protocol validator** + **shift invariance** under ±300 s shift.
8. **Input validation** + **RE1-OB sanity check** (skipped if data
   isn't local).
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
from evaluation.methods.yrca import (
    SyntheticEvent,
    YRCAMethod,
    _forward_chain,
    _infer_topology,
    _synthesize_events,
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
    / "week2_yrca_validation.csv"
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
    """3-service chain: ``db`` is the root cause; its CPU and latency
    step up, propagating downstream to ``cart``'s latency.
    """
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
    cart_latency[inject_idx + 1:] += 0.06

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


# ---- 1. contract tests ----


class TestContractOnFakeFixture:
    def test_returns_diagnostic_output(self):
        out = YRCAMethod().diagnose(_ob_case())
        assert isinstance(out, DiagnosticOutput)
        assert out.method_name == "yrca"
        assert out.wall_time_ms >= 0.0

    def test_ranked_list_non_empty_and_sorted(self):
        out = YRCAMethod().diagnose(_ob_case())
        assert len(out.ranked_list) >= 1
        scores = [s for _, s in out.ranked_list]
        assert scores == sorted(scores, reverse=True)

    def test_explanation_is_canonical(self):
        out = YRCAMethod().diagnose(_ob_case())
        assert isinstance(out.explanation_chain, CanonicalExplanation)
        atoms = list(out.explanation_chain.atoms())
        assert len(atoms) >= 1
        for atom in atoms:
            assert atom.ontology_class is not None
            assert atom.ontology_class.startswith("yrca:Role/")

    def test_confidence_in_unit_interval(self):
        out = YRCAMethod().diagnose(_ob_case())
        assert out.confidence is not None
        assert 0.0 <= out.confidence <= 1.0

    def test_cartservice_outranks_frontend_on_cpu_anomaly(self):
        out = YRCAMethod().diagnose(_ob_case())
        top, _ = out.ranked_list[0]
        assert top == "cartservice"

    def test_deterministic_across_runs(self):
        case = _ob_case()
        a = YRCAMethod().diagnose(case)
        b = YRCAMethod().diagnose(case)
        assert a.ranked_list == b.ranked_list
        assert a.confidence == b.confidence

    def test_raw_output_carries_diagnostic_summary(self):
        out = YRCAMethod().diagnose(_ob_case())
        for key in (
            "onset_time", "n_events", "n_anomaly_events", "topology_edges",
            "iterations", "n_facts", "facts_by_relation",
            "final_root_causes", "severity_by_service",
        ):
            assert key in out.raw_output


# ---- 2. synthetic-event generation ----


class TestSyntheticEventGeneration:
    def test_three_service_chain_emits_anomaly_high_for_db(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        from evaluation.methods._onset import detect_onset
        onset = detect_onset(norm.case_window, norm.services)
        events = _synthesize_events(
            case_window=norm.case_window,
            services=norm.services,
            onset_time=onset,
            severity_threshold=3.0,
            emit_normal=False,
        )
        assert events, "expected at least one anomaly event"
        db_events = [e for e in events if e.service == "db"]
        assert db_events, "db should emit at least one anomaly_high event"
        assert any(e.kind == "anomaly_high" for e in db_events)
        assert all(e.severity >= 3.0 for e in db_events)
        # No normal events when emit_normal=False
        assert not any(e.kind == "normal" for e in events)

    def test_emit_normal_adds_baseline_events(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        from evaluation.methods._onset import detect_onset
        onset = detect_onset(norm.case_window, norm.services)
        events_off = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=3.0, emit_normal=False,
        )
        events_on = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=3.0, emit_normal=True,
        )
        # Same anomaly count; baselines are additive only.
        anom_off = [e for e in events_off if e.kind != "normal"]
        anom_on = [e for e in events_on if e.kind != "normal"]
        assert len(anom_off) == len(anom_on)
        assert len(events_on) > len(events_off)
        assert any(e.kind == "normal" for e in events_on)

    def test_low_threshold_emits_more_events(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        from evaluation.methods._onset import detect_onset
        onset = detect_onset(norm.case_window, norm.services)
        few = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=5.0, emit_normal=False,
        )
        many = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=2.0, emit_normal=False,
        )
        assert len(many) >= len(few)

    def test_anomaly_low_emitted_for_traffic_drop(self):
        """A service whose traffic drops at injection should emit an
        ``anomaly_low`` event on the traffic feature."""
        n = 800
        inject_idx = 400
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "a_traffic": 100.0 + rng.normal(0.0, 0.5, n),
            "a_cpu":     0.20 + rng.normal(0.0, 0.01, n),
            "b_traffic": 100.0 + rng.normal(0.0, 0.5, n),
            "b_cpu":     0.20 + rng.normal(0.0, 0.01, n),
        })
        df.loc[inject_idx:, "a_traffic"] -= 50.0  # large drop
        case = _make_case(df, inject_time=float(inject_idx),
                          root_cause="a", case_id="synth_low",
                          fault_type="loss")
        norm = normalize_case(case, window_seconds=1200.0)
        from evaluation.methods._onset import detect_onset
        onset = detect_onset(norm.case_window, norm.services)
        events = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=3.0, emit_normal=False,
        )
        a_traffic_low = [
            e for e in events
            if e.service == "a" and e.feature == "traffic"
            and e.kind == "anomaly_low"
        ]
        assert a_traffic_low, (
            f"expected a anomaly_low traffic event; got events: {events}"
        )

    def test_all_events_timestamped_at_onset(self):
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        from evaluation.methods._onset import detect_onset
        onset = detect_onset(norm.case_window, norm.services)
        events = _synthesize_events(
            case_window=norm.case_window, services=norm.services,
            onset_time=onset, severity_threshold=3.0, emit_normal=False,
        )
        assert events
        assert all(e.timestamp == onset for e in events)


# ---- 3. topology inference ----


class TestTopologyInference:
    def test_no_self_loops(self):
        out = YRCAMethod().diagnose(_three_service_case())
        for (u, v) in out.raw_output["topology_edges"]:
            assert u != v

    def test_high_threshold_removes_all_edges(self):
        case = _three_service_case()
        out = YRCAMethod(topology_threshold=0.999).diagnose(case)
        assert out.raw_output["topology_edges"] == []

    def test_db_to_cart_edge_present(self):
        """db's cpu jumps up, cart's latency follows; the directed
        edge db→cart should appear (db's signal leads cart's)."""
        case = _three_service_case()
        out = YRCAMethod(topology_threshold=0.3, lag=1).diagnose(case)
        edges = set(out.raw_output["topology_edges"])
        # At least one of db→cart, db→frontend should be present.
        assert any(u == "db" for (u, _) in edges), (
            f"expected at least one db→* edge; got {edges}"
        )


# ---- 4. forward-chaining inference ----


class TestForwardChaining:
    def test_r1_emits_potential_root_cause_for_each_anomaly_service(self):
        events = [
            SyntheticEvent(
                service="a", feature="cpu", kind="anomaly_high",
                timestamp=100.0, severity=5.0, z_signed=5.0,
            ),
            SyntheticEvent(
                service="b", feature="latency", kind="anomaly_high",
                timestamp=100.0, severity=4.0, z_signed=4.0,
            ),
        ]
        facts, iters = _forward_chain(
            services=["a", "b"], events=events, topology={},
            max_iterations=8,
        )
        prc = [f for f in facts if f.relation == "potential_root_cause"]
        assert {f.args[0] for f in prc} == {"a", "b"}
        assert iters >= 1

    def test_r3_marks_unexplained_services_as_final_root_cause(self):
        events = [
            SyntheticEvent(
                service="a", feature="cpu", kind="anomaly_high",
                timestamp=100.0, severity=5.0, z_signed=5.0,
            ),
        ]
        facts, _ = _forward_chain(
            services=["a", "b"], events=events, topology={},
            max_iterations=8,
        )
        frc = [f for f in facts if f.relation == "final_root_cause"]
        assert [f.args[0] for f in frc] == ["a"]

    def test_r2_propagates_explained_by_along_topology(self):
        """``cause`` → ``dep`` topology + both anomalous + dep's anomaly
        is not strictly before cause's ⇒ ``dep explained_by cause`` and
        only ``cause`` remains a final root cause."""
        events = [
            SyntheticEvent(
                service="cause", feature="cpu", kind="anomaly_high",
                timestamp=100.0, severity=5.0, z_signed=5.0,
            ),
            SyntheticEvent(
                service="dep", feature="latency", kind="anomaly_high",
                timestamp=100.0, severity=4.0, z_signed=4.0,
            ),
        ]
        topology = {("cause", "dep"): 0.9}
        facts, _ = _forward_chain(
            services=["cause", "dep"], events=events, topology=topology,
            max_iterations=8,
        )
        explained_by = [
            f for f in facts if f.relation == "explained_by"
        ]
        assert any(f.args == ("dep", "cause") for f in explained_by)
        frc = {f.args[0] for f in facts if f.relation == "final_root_cause"}
        assert frc == {"cause"}

    def test_forward_chain_terminates_within_budget(self):
        case = _three_service_case()
        out = YRCAMethod(max_iterations=8).diagnose(case)
        assert out.raw_output["iterations"] <= 8

    def test_r4_retry_cascade_creates_explained_by_with_distinct_rule_id(self):
        """Upstream latency anomaly + downstream traffic anomaly ⇒
        explained_by under R4 (retry pattern), independent of R2's
        firing condition."""
        events = [
            SyntheticEvent(
                service="api", feature="latency", kind="anomaly_high",
                timestamp=100.0, severity=4.0, z_signed=4.0,
            ),
            SyntheticEvent(
                service="caller", feature="traffic", kind="anomaly_high",
                timestamp=100.0, severity=3.5, z_signed=3.5,
            ),
        ]
        topology = {("api", "caller"): 0.8}
        facts, _ = _forward_chain(
            services=["api", "caller"], events=events, topology=topology,
            max_iterations=8,
        )
        rule_ids = {
            f.rule_id for f in facts
            if f.relation == "explained_by" and f.args == ("caller", "api")
        }
        assert "R4_retry" in rule_ids

    def test_r5_timeout_propagation_creates_explained_by(self):
        events = [
            SyntheticEvent(
                service="up", feature="latency", kind="anomaly_high",
                timestamp=100.0, severity=4.0, z_signed=4.0,
            ),
            SyntheticEvent(
                service="down", feature="latency", kind="anomaly_high",
                timestamp=100.0, severity=3.5, z_signed=3.5,
            ),
        ]
        topology = {("up", "down"): 0.8}
        facts, _ = _forward_chain(
            services=["up", "down"], events=events, topology=topology,
            max_iterations=8,
        )
        rule_ids = {
            f.rule_id for f in facts
            if f.relation == "explained_by" and f.args == ("down", "up")
        }
        assert "R5_timeout" in rule_ids


# ---- 5. ranking ----


class TestRanking:
    def test_three_service_chain_ranks_db_top_1(self):
        out = YRCAMethod().diagnose(_three_service_case())
        top, _ = out.ranked_list[0]
        assert top == "db"

    def test_explained_services_rank_below_final_root_cause(self):
        out = YRCAMethod().diagnose(_three_service_case())
        ranked = [s for s, _ in out.ranked_list]
        assert ranked[0] == "db"
        # Final root causes must appear before non-roots.
        frc = set(out.raw_output["final_root_causes"])
        first_non_root = next(
            (i for i, s in enumerate(ranked) if s not in frc), None
        )
        last_root = max(
            (i for i, s in enumerate(ranked) if s in frc), default=-1
        )
        if first_non_root is not None:
            assert last_root < first_non_root

    def test_constant_case_returns_no_anomaly_events(self):
        """When every metric column is literally constant (zero std),
        no synthetic events are emitted — the rule engine has no
        antecedents, so it derives nothing and returns an empty
        ranked list of final root causes. The method does not
        crash."""
        n = 500
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "a_latency": np.full(n, 0.10),
            "a_cpu":     np.full(n, 0.20),
            "b_latency": np.full(n, 0.10),
            "b_cpu":     np.full(n, 0.20),
        })
        case = _make_case(df, inject_time=250.0, root_cause="a",
                          case_id="constant")
        out = YRCAMethod(severity_threshold=3.0).diagnose(case)
        assert out.raw_output["n_anomaly_events"] == 0
        assert out.raw_output["final_root_causes"] == []
        # Ranked list still covers every service.
        assert {s for s, _ in out.ranked_list} == set(["a", "b"])
        for _, score in out.ranked_list:
            assert np.isfinite(score)

    def test_flat_noise_does_not_crash(self):
        """yRCA inherits ``_onset.detect_onset``'s edge-fragility
        (DEVIATIONS.md): on pure-noise data the detector finds a
        spurious central-band pivot. The method still terminates
        cleanly and returns a finite ranking; whether any
        final_root_cause facts emerge depends on whether the
        spurious-pivot z-score exceeds the severity threshold."""
        n = 500
        rng = np.random.default_rng(0)
        df = pd.DataFrame({
            "time": np.arange(n, dtype=float),
            "a_latency": 0.10 + rng.normal(0.0, 0.05, n),
            "a_cpu": 0.20 + rng.normal(0.0, 0.05, n),
            "b_latency": 0.10 + rng.normal(0.0, 0.05, n),
            "b_cpu": 0.20 + rng.normal(0.0, 0.05, n),
        })
        case = _make_case(df, inject_time=250.0, root_cause="a",
                          case_id="flat_noise")
        out = YRCAMethod(severity_threshold=3.0).diagnose(case)
        # Ranking is defined; confidence in [0, 1]; iteration count finite.
        assert {s for s, _ in out.ranked_list} == set(["a", "b"])
        assert 0.0 <= out.confidence <= 1.0
        assert out.raw_output["iterations"] >= 1


# ---- 6. explanation shape ----


class TestExplanationShape:
    def test_atoms_carry_role_ontology_class(self):
        out = YRCAMethod().diagnose(_three_service_case())
        roles = {
            atom.ontology_class for atom in out.explanation_chain.atoms()
        }
        assert any("final_root_cause" in (r or "") for r in roles)

    def test_links_relation_type_rule_derived_explanation(self):
        """Each CausalLink has ``relation_type`` starting with
        ``rule_derived_explanation``, with a suffix listing the
        ``rule_id``s that derived the edge (e.g.
        ``rule_derived_explanation:R2+R4_retry``)."""
        out = YRCAMethod().diagnose(_three_service_case())
        links = list(out.explanation_chain.links())
        for link in links:
            assert link.relation_type is not None
            assert link.relation_type.startswith("rule_derived_explanation")
            # Suffix is non-empty when the edge was derived (every
            # link in this graph is derived).
            assert ":" in link.relation_type
            suffix = link.relation_type.split(":", 1)[1]
            assert suffix, "expected non-empty rule list in relation_type"
            for rule_id in suffix.split("+"):
                assert rule_id.startswith("R"), (
                    f"unexpected rule_id {rule_id!r} in {link.relation_type!r}"
                )
            assert link.weight is not None
            assert 0.0 <= link.weight <= 1.0

    def test_raw_output_explanation_edges_carry_rule_ids(self):
        """``raw_output['explanation_edges']`` lists every
        ``explained_by`` edge with its full ``rule_ids`` list. This
        is the structured representation the case-study figure
        consumes when CanonicalExplanation's flat link iterator
        won't suffice."""
        out = YRCAMethod().diagnose(_three_service_case())
        edges = out.raw_output["explanation_edges"]
        assert isinstance(edges, list)
        # At least one edge should be present on the 3-service chain.
        assert edges
        for record in edges:
            assert set(record.keys()) == {"dep", "cause", "rule_ids"}
            assert record["rule_ids"], (
                f"every recorded edge must list ≥ 1 rule_id; "
                f"got {record!r}"
            )
            for rid in record["rule_ids"]:
                assert rid.startswith("R")

    def test_atom_text_records_derivation_rules(self):
        out = YRCAMethod().diagnose(_three_service_case())
        # db's atom should mention at least R1 in its derivation list.
        db_atoms = [
            atom for atom in out.explanation_chain.atoms()
            if atom.text.startswith("db ")
        ]
        assert db_atoms
        assert any("R1" in atom.text for atom in db_atoms)


# ---- 7. protocol + shift ----


class TestProtocolValidator:
    def test_diagnose_does_not_reference_ground_truth(self):
        validate_no_ground_truth_peeking(YRCAMethod())

    def test_protocol_validator_catches_peeking_subclass(self):
        class LeakyYRCA(YRCAMethod):
            def diagnose(self, case):
                _ = case.ground_truth  # banned
                return super().diagnose(case)

        with pytest.raises(ProtocolViolationError):
            validate_no_ground_truth_peeking(LeakyYRCA())


class TestShiftInvariance:
    def test_output_identical_under_pm_300s_shift(self):
        """yRCA does its own onset detection from ``case_window`` and
        never reads ``ground_truth``. The ground-truth-side-channel
        shift must leave the diagnosis bit-identical."""
        case = _three_service_case()
        norm = normalize_case(case, window_seconds=1200.0)
        m = YRCAMethod()
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


# ---- 8. input validation + RE1-OB sanity ----


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
            YRCAMethod().diagnose(case)

    def test_missing_inject_time_raises(self):
        case = BenchmarkCase(
            id="bad",
            telemetry={"metrics": pd.DataFrame({"time": [0, 1]})},
            ground_truth_root_cause="x",
            ground_truth_fault_type="y",
            system_topology=None,
        )
        with pytest.raises(KeyError, match="inject_time"):
            YRCAMethod().diagnose(case)

    def test_no_services_raises(self):
        case = _make_case(
            pd.DataFrame({"time": [0.0, 1.0, 2.0], "scalar": [1.0, 2.0, 3.0]}),
            inject_time=1.0, root_cause="?",
        )
        with pytest.raises(ValueError, match="services"):
            YRCAMethod().diagnose(case)

    @pytest.mark.parametrize("threshold", [0.0, -1.0])
    def test_severity_threshold_must_be_positive(self, threshold):
        with pytest.raises(ValueError, match="severity_threshold"):
            YRCAMethod(severity_threshold=threshold)

    @pytest.mark.parametrize("threshold", [-0.1, 1.1])
    def test_topology_threshold_must_be_in_unit_interval(self, threshold):
        with pytest.raises(ValueError, match="topology_threshold"):
            YRCAMethod(topology_threshold=threshold)

    def test_max_iterations_must_be_at_least_one(self):
        with pytest.raises(ValueError, match="max_iterations"):
            YRCAMethod(max_iterations=0)

    def test_top_k_must_be_positive(self):
        with pytest.raises(ValueError, match="top_k"):
            YRCAMethod(top_k=0)

    def test_window_seconds_must_be_positive(self):
        with pytest.raises(ValueError, match="window_seconds"):
            YRCAMethod(window_seconds=0.0)

    def test_lag_must_be_non_negative(self):
        with pytest.raises(ValueError, match="lag"):
            YRCAMethod(lag=-1)


@pytest.mark.skipif(
    not RE1_OB.is_dir(),
    reason=f"RE1-OB data not found at {RE1_OB}",
)
def test_re1_ob_ac_at_k_sanity_check():
    """Run yRCA on every RE1-OB case via the standalone harness and
    assert:

    1. ``S(yRCA) == 0`` per fault — yRCA's onset comes from
       :func:`detect_onset` on ``case_window``; ``ground_truth`` is
       not read.
    2. AC@1 overall is in ``[0.05, 0.65]`` (brief target: lower than
       supervised DejaVu, comparable to or below unsupervised graph
       methods because the synthetic-event abstraction loses
       information).
    3. ``AC@1_random``, ``AC@1_a_standard``, ``AC@1_b_edges_mean``,
       ``AC@1_c_centered`` columns present (paper-relevant
       decompositions).
    """
    from evaluation.experiments.evaluate_yrca import (
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
            f"S(yRCA) for fault {fault!r} = {s}; non-zero means the "
            f"method is leaking inject_time"
        )

    overall_ac1 = summary["overall"]["AC@1"]
    print(f"\nOverall AC@1 = {overall_ac1:.3f} (expected [0.05, 0.65])")
    assert 0.05 <= overall_ac1 <= 0.65, (
        f"yRCA overall AC@1 = {overall_ac1:.3f} outside the expected "
        f"[0.05, 0.65] band (brief)."
    )

    for col in ("AC@1_random", "AC@1_a_standard",
                "AC@1_b_edges_mean", "AC@1_c_centered"):
        assert col in summary["overall"], (
            f"expected decomposition column {col!r} in summary"
        )
