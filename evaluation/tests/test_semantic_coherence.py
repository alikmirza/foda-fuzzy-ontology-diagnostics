"""Tests for ``evaluation.metrics.semantic_coherence.SemanticCoherence``
under the variant-4 scoring rule (typicality credit, mitigation
exclusion). See module docstring of :mod:`semantic_coherence` for the
design."""

from __future__ import annotations

import pytest

from evaluation.extraction.canonical_explanation import (
    CanonicalExplanation,
    CausalLink,
    ExplanationAtom,
)
from evaluation.metrics.ontology_adapter import OntologyAdapter
from evaluation.metrics.semantic_coherence import (
    PROPAGATION_RELATIONS,
    SemanticCoherence,
    _BACK_FLOW_RELATIONS,
    _MITIGATION_TOKENS,
    _counts_toward_denominator,
    _fault_prototype_uris,
    _is_back_flow,
    _is_mitigation,
    _is_propagation,
    _score_link,
)


_NS = "http://foda.com/ontology/diagnostic#"


@pytest.fixture(scope="module")
def ontology() -> OntologyAdapter:
    return OntologyAdapter()


def _explain_with(
    atoms: list[ExplanationAtom],
    links: list[tuple[int, int, float | None, str | None]] | None = None,
) -> CanonicalExplanation:
    """Build a CanonicalExplanation from a list of atoms and a list of
    ``(src_idx, tgt_idx, weight, relation_type)`` link descriptors."""
    e = CanonicalExplanation()
    for a in atoms:
        e.add_atom(a)
    for src_idx, tgt_idx, weight, rel in links or []:
        e.add_link(CausalLink(
            source_atom_id=atoms[src_idx].id,
            target_atom_id=atoms[tgt_idx].id,
            weight=weight,
            relation_type=rel,
        ))
    return e


# ---- 1. contract ----------------------------------------------------------


class TestContract:
    def test_name(self):
        assert SemanticCoherence().name == "semantic_coherence"

    def test_score_returns_float_in_unit_interval(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="y", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        s = m.score(e, ontology)
        assert isinstance(s, float)
        assert 0.0 <= s <= 1.0

    def test_breakdown_overall_matches_score(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="y", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        assert m.score(e, ontology) == m.score_with_breakdown(e, ontology)["overall"]


# ---- 2. coherent links ----------------------------------------------------


class TestCoherentLinks:
    """Under variant 4 the subscore equals the ontology's typicality
    (1.0 for typical patterns, 0.5 for conditional ones). The link's
    own ``weight`` does not penalise the score — see the diagnostic in
    findings.md §"Phase 2 Week 2 v3" for why the v2 weight-consistency
    formula failed FCP."""

    def test_typical_propagation_scores_one(self, ontology):
        """``CpuSaturation → LatencySpike`` has ontology strength 1.0
        and is a forward propagation; ``"causes"`` is forward."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        assert m.score(e, ontology) == 1.0

    def test_conditional_propagation_scores_half(self, ontology):
        """``MemoryLeak → CpuSaturation`` has ontology strength 0.5
        (conditional propagation). Variant 4 gives partial credit
        equal to the typicality."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="mem", ontology_class=f"{_NS}MemoryLeak")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 0.9, "causes")])
        assert m.score(e, ontology) == 0.5

    def test_link_weight_does_not_change_subscore(self, ontology):
        """The link's ``weight`` is informational — variant 4 ignores
        it. Two links with identical (src, tgt) and different weights
        score the same."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e1 = _explain_with([a, b], [(0, 1, 0.001, "causes")])
        e2 = _explain_with([a, b], [(0, 1, 0.999, "causes")])
        assert m.score(e1, ontology) == m.score(e2, ontology) == 1.0

    def test_missing_weight_does_not_change_subscore(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="err", ontology_class=f"{_NS}HighErrorRate")
        e = _explain_with([a, b], [(0, 1, None, "causes")])
        # CpuSaturation → HighErrorRate is a 0.5-strength propagation.
        assert m.score(e, ontology) == 0.5

    def test_breakdown_match_type_coherent(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        br = m.score_with_breakdown(e, ontology)
        row = br["per_link"][0]
        assert row["match_type"] == "coherent"
        assert row["ontology_strength"] == 1.0
        assert row["link_weight"] == 1.0
        assert br["coherent_links"] == 1
        assert br["incoherent_links"] == 0
        assert br["unmapped_links"] == 0
        assert br["excluded_mitigation_links"] == 0
        assert br["scored_link_count"] == 1


# ---- 3. incoherent links --------------------------------------------------


class TestIncoherentLinks:
    def test_reverse_direction_is_incoherent(self, ontology):
        """``LatencySpike → CpuSaturation`` is not a declared
        propagation (the reverse is typical). With a forward relation
        type, SC has no swap to perform and the lookup misses."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        assert m.score(e, ontology) == 0.0
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "incoherent"
        assert br["incoherent_links"] == 1

    def test_self_loop_is_incoherent(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu1", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="cpu2", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        assert m.score(e, ontology) == 0.0
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "incoherent"

    def test_undeclared_pair_is_incoherent(self, ontology):
        """``HighErrorRate → MemoryLeak`` — both fault prototypes but
        no propagation declared."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="err", ontology_class=f"{_NS}HighErrorRate")
        b = ExplanationAtom(text="mem", ontology_class=f"{_NS}MemoryLeak")
        e = _explain_with([a, b], [(0, 1, 0.8, "causes")])
        assert m.score(e, ontology) == 0.0


# ---- 4. unmapped links ----------------------------------------------------


class TestUnmappedLinks:
    def test_link_with_no_source_class_is_unmapped(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="anon")  # no ontology_class
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        assert m.score(e, ontology) == 0.0
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"
        assert br["unmapped_links"] == 1

    def test_link_with_no_target_class_is_unmapped(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="anon")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"

    def test_link_with_foreign_namespace_is_unmapped(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="src", ontology_class="yrca:Role/final_root_cause")
        b = ExplanationAtom(text="tgt", ontology_class="yrca:Role/intermediate_propagator")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"

    def test_non_propagation_relation_is_unmapped(self, ontology):
        """A link with ``relation_type=None`` is not a propagation
        claim and is unmapped under variant 4, even if both endpoints
        are fault prototypes."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, None)])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"

    def test_anomaly_correlates_with_is_unmapped(self, ontology):
        """MicroRCA's ``"anomaly-correlates-with"`` shape isn't a
        propagation claim — it's a correlation observation. SC
        classifies it as unmapped."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        e = _explain_with([a, b], [(0, 1, 1.0, "anomaly-correlates-with")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"


# ---- 5. overall scoring ---------------------------------------------------


class TestOverallScoring:
    def test_mean_of_per_link_subscores(self, ontology):
        m = SemanticCoherence()
        cpu = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        lat = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        err = ExplanationAtom(text="err", ontology_class=f"{_NS}HighErrorRate")
        mem = ExplanationAtom(text="mem", ontology_class=f"{_NS}MemoryLeak")
        e = _explain_with(
            [cpu, lat, err, mem],
            links=[
                (0, 1, 1.0, "causes"),  # CpuSat→LatSpike, strength 1.0 → 1.0
                (1, 2, 0.5, "causes"),  # LatSpike→HighErr, strength 0.5 → 0.5
                (2, 3, 0.5, "causes"),  # HighErr→MemLeak, undeclared → 0.0
            ],
        )
        # Mean = (1.0 + 0.5 + 0.0) / 3 = 0.5
        assert m.score(e, ontology) == pytest.approx(0.5, abs=1e-6)

    def test_empty_explanation_returns_zero(self, ontology):
        m = SemanticCoherence()
        assert m.score(CanonicalExplanation(), ontology) == 0.0

    def test_atom_only_explanation_returns_zero(self, ontology):
        m = SemanticCoherence()
        e = _explain_with([
            ExplanationAtom(text="svc", ontology_class=f"{_NS}CpuSaturation"),
        ])
        assert m.score(e, ontology) == 0.0

    def test_breakdown_for_empty_explanation(self, ontology):
        m = SemanticCoherence()
        br = m.score_with_breakdown(CanonicalExplanation(), ontology)
        assert br == {
            "overall": 0.0,
            "per_link": [],
            "link_count": 0,
            "coherent_links": 0,
            "incoherent_links": 0,
            "unmapped_links": 0,
            "excluded_mitigation_links": 0,
            "scored_link_count": 0,
        }


# ---- 6. breakdown output --------------------------------------------------


class TestBreakdown:
    def test_breakdown_lists_every_link_in_order(self, ontology):
        m = SemanticCoherence()
        cpu = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        lat = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        err = ExplanationAtom(text="err", ontology_class=f"{_NS}HighErrorRate")
        e = _explain_with(
            [cpu, lat, err],
            links=[(0, 1, 1.0, "causes"), (1, 2, 0.5, "causes")],
        )
        br = m.score_with_breakdown(e, ontology)
        assert br["link_count"] == 2
        assert len(br["per_link"]) == 2
        assert br["per_link"][0]["source_atom_id"] == cpu.id
        assert br["per_link"][0]["target_atom_id"] == lat.id
        assert br["per_link"][1]["source_atom_id"] == lat.id
        assert br["per_link"][1]["target_atom_id"] == err.id

    def test_counts_partition_links(self, ontology):
        """``coherent + incoherent + unmapped + excluded_mitigation
        == link_count``; ``scored_link_count`` excludes mitigation."""
        m = SemanticCoherence()
        cpu = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        lat = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        err = ExplanationAtom(text="err", ontology_class=f"{_NS}HighErrorRate")
        mem = ExplanationAtom(text="mem", ontology_class=f"{_NS}MemoryLeak")
        rec = ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation")
        anon = ExplanationAtom(text="anon")
        e = _explain_with(
            [cpu, lat, err, mem, rec, anon],
            links=[
                (0, 1, 1.0, "causes"),                 # coherent
                (2, 3, 1.0, "causes"),                 # incoherent
                (0, 5, 1.0, "causes"),                 # unmapped (anon)
                (0, 4, 1.0, "suggests_mitigation"),    # excluded mitigation
            ],
        )
        br = m.score_with_breakdown(e, ontology)
        assert (
            br["coherent_links"] + br["incoherent_links"]
            + br["unmapped_links"] + br["excluded_mitigation_links"]
            == br["link_count"]
        )
        assert br["coherent_links"] == 1
        assert br["incoherent_links"] == 1
        assert br["unmapped_links"] == 1
        assert br["excluded_mitigation_links"] == 1
        assert br["scored_link_count"] == 3  # mitigation excluded


# ---- 7. _score_link helper ------------------------------------------------


class TestScoreLinkHelper:
    def test_returns_link_score_dataclass_fields(self, ontology):
        from evaluation.metrics.semantic_coherence import _LinkScore
        a = ExplanationAtom(text="a", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="b", ontology_class=f"{_NS}LatencySpike")
        link = CausalLink(
            source_atom_id=a.id, target_atom_id=b.id, weight=0.8,
            relation_type="causes",
        )
        s = _score_link(link, a, b, ontology)
        assert isinstance(s, _LinkScore)
        assert s.match_type == "coherent"
        assert s.ontology_strength == 1.0
        assert s.link_weight == 0.8
        # Variant 4: subscore = ontology_strength, weight ignored.
        assert s.subscore == 1.0


# ---- 8. back-flow relation handling ---------------------------------------


class TestBackFlowRelationHandling:
    """Back-flow propagation shapes flow ``effect → cause`` and need
    the (source, target) pair swapped before the ontology lookup."""

    def test_contributes_to_back_flow_swaps_direction(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [
            (0, 1, 0.001, "contributes_to:propagation:noisy_or"),
        ])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "coherent"
        assert br["per_link"][0]["ontology_strength"] == 1.0
        # Variant 4: low link weight doesn't penalise; subscore = 1.0.
        assert m.score(e, ontology) == 1.0

    def test_explained_by_back_flow_swaps_direction(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 0.5, "explained_by")])
        assert m.score(e, ontology) == 1.0

    def test_caused_by_back_flow_swaps_direction(self, ontology):
        """``caused_by`` is generic back-flow (X is caused by Y)."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 0.7, "caused_by")])
        assert m.score(e, ontology) == 1.0

    def test_forward_relation_does_not_swap(self, ontology):
        """``causes`` is forward; a link from LatencySpike to
        CpuSaturation with ``causes`` is genuinely reversed and
        scores incoherent."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        b = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "incoherent"

    def test_back_flow_constants(self):
        assert "contributes_to" in _BACK_FLOW_RELATIONS
        assert "explained_by" in _BACK_FLOW_RELATIONS
        assert "caused_by" in _BACK_FLOW_RELATIONS
        assert _BACK_FLOW_RELATIONS.issubset(PROPAGATION_RELATIONS)

    def test_propagation_constants(self):
        assert "contributes_to" in PROPAGATION_RELATIONS
        assert "explained_by" in PROPAGATION_RELATIONS
        assert "caused_by" in PROPAGATION_RELATIONS
        assert "causes" in PROPAGATION_RELATIONS
        assert "propagates_to" in PROPAGATION_RELATIONS
        assert "leads_to" in PROPAGATION_RELATIONS

    def test_is_propagation_helper(self):
        assert _is_propagation("causes")
        assert _is_propagation("contributes_to:propagation:noisy_or")
        assert _is_propagation("propagates_to")
        assert not _is_propagation("anomaly-correlates-with")
        assert not _is_propagation("rule_derived_explanation")
        assert not _is_propagation(None)
        assert not _is_propagation("suggests_mitigation")

    def test_is_back_flow_helper(self):
        assert _is_back_flow("contributes_to:propagation:noisy_or")
        assert _is_back_flow("explained_by")
        assert _is_back_flow("caused_by")
        assert not _is_back_flow("causes")
        assert not _is_back_flow("propagates_to")
        assert not _is_back_flow(None)


# ---- 9. fault-prototype filtering -----------------------------------------


class TestFaultPrototypeFiltering:
    def test_link_to_recommendation_via_propagation_relation_is_unmapped(
        self, ontology,
    ):
        """A direct propagation-relation link to a Recommendation
        endpoint is unmapped (Recommendation isn't a fault prototype).
        Real-world recommendation links are typically tagged with
        suggests_mitigation and excluded — this test covers the edge
        case where some adapter mislabels them as propagation."""
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 1.0, "causes")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"

    def test_link_to_abstract_contributing_factor_is_unmapped(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="root", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="leaf", ontology_class=f"{_NS}ContributingFactor")
        e = _explain_with([a, b], [(0, 1, 0.5, "causes")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "unmapped"

    def test_fault_prototype_uris_helper(self, ontology):
        protos = _fault_prototype_uris(ontology)
        for local in (
            "CpuSaturation", "MemoryLeak", "LatencySpike",
            "HighErrorRate", "ResourceContention",
        ):
            assert f"{_NS}{local}" in protos
        assert f"{_NS}ContributingFactor" not in protos
        assert f"{_NS}Rec_CpuSaturation" not in protos


# ---- 10. mitigation exclusion ---------------------------------------------


class TestMitigationExclusion:
    """Mitigation links are excluded from SC's denominator entirely.
    The exclusion is what makes FCP's suggests_mitigation links —
    structurally never propagation claims — stop dragging the metric
    down."""

    def test_suggests_mitigation_excluded(self, ontology):
        m = SemanticCoherence()
        cpu = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        rec = ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation")
        e = _explain_with(
            [cpu, rec],
            [(0, 1, 1.0, "suggests_mitigation:recommendation:fault_prototype")],
        )
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "excluded_mitigation"
        assert br["excluded_mitigation_links"] == 1
        assert br["scored_link_count"] == 0
        # No scored links → overall 0.0 (vacuous denominator).
        assert m.score(e, ontology) == 0.0

    def test_mitigation_does_not_dilute_coherent_score(self, ontology):
        """One coherent propagation + one mitigation link → SC = 1.0
        (mitigation is dropped from denominator), NOT 0.5."""
        m = SemanticCoherence()
        cpu = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        lat = ExplanationAtom(text="lat", ontology_class=f"{_NS}LatencySpike")
        rec = ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation")
        e = _explain_with(
            [cpu, lat, rec],
            [
                (0, 1, 1.0, "causes"),                    # coherent → 1.0
                (0, 2, 1.0, "suggests_mitigation"),       # excluded
            ],
        )
        assert m.score(e, ontology) == 1.0
        br = m.score_with_breakdown(e, ontology)
        assert br["coherent_links"] == 1
        assert br["excluded_mitigation_links"] == 1
        assert br["scored_link_count"] == 1

    def test_recommend_token_in_relation_type_is_mitigation(self, ontology):
        m = SemanticCoherence()
        a = ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation")
        e = _explain_with([a, b], [(0, 1, 1.0, "recommend_action")])
        br = m.score_with_breakdown(e, ontology)
        assert br["per_link"][0]["match_type"] == "excluded_mitigation"

    def test_mitigation_token_constants(self):
        assert "mitigation" in _MITIGATION_TOKENS
        assert "recommend" in _MITIGATION_TOKENS
        assert "suggests" in _MITIGATION_TOKENS

    def test_is_mitigation_helper(self):
        assert _is_mitigation("suggests_mitigation:recommendation:fault_prototype")
        assert _is_mitigation("recommend_action")
        assert _is_mitigation("suggests_recovery")
        assert not _is_mitigation("causes")
        assert not _is_mitigation("contributes_to:propagation:noisy_or")
        assert not _is_mitigation(None)

    def test_counts_toward_denominator_helper(self):
        assert _counts_toward_denominator("coherent")
        assert _counts_toward_denominator("incoherent")
        assert _counts_toward_denominator("unmapped")
        assert not _counts_toward_denominator("excluded_mitigation")
