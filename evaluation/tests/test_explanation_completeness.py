"""Tests for ``evaluation.metrics.explanation_completeness``.

EC is a binary three-category detector: does the explanation surface a
**fault type**, an **affected service**, and a **mitigation
recommendation**? Aggregate = count / 3, so the scalar takes one of
four values in ``{0.0, 0.333…, 0.667…, 1.0}``.
"""

from __future__ import annotations

import pytest

from evaluation.extraction.canonical_explanation import (
    CanonicalExplanation,
    ExplanationAtom,
)
from evaluation.metrics.explanation_completeness import (
    ExplanationCompleteness,
    _content_tokens,
    _detect_affected_component_category,
    _detect_mitigation_category,
    _detect_root_cause_category,
)
from evaluation.metrics.ontology_adapter import OntologyAdapter


_NS = "http://foda.com/ontology/diagnostic#"


@pytest.fixture(scope="module")
def ontology() -> OntologyAdapter:
    return OntologyAdapter()


def _explain_with(atoms: list[ExplanationAtom]) -> CanonicalExplanation:
    e = CanonicalExplanation()
    for a in atoms:
        e.add_atom(a)
    return e


# ---- 1. contract ----------------------------------------------------------


class TestContract:
    def test_name(self):
        assert ExplanationCompleteness().name == "explanation_completeness"

    def test_score_returns_float_in_unit_interval(self, ontology):
        m = ExplanationCompleteness()
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
        ])
        s = m.score(e, ontology)
        assert isinstance(s, float)
        assert 0.0 <= s <= 1.0

    def test_breakdown_overall_matches_score(self, ontology):
        m = ExplanationCompleteness()
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
        ])
        s = m.score(e, ontology, case_services=["cartservice"])
        br = m.score_with_breakdown(e, ontology, case_services=["cartservice"])
        assert s == br["overall"]


# ---- 2. root-cause detector ----------------------------------------------


class TestRootCauseDetector:
    def test_fault_prototype_uri_matches(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),
        ])
        matched, atoms = _detect_root_cause_category(e, ontology)
        assert matched
        assert len(atoms) == 1

    def test_fault_class_uri_matches(self, ontology):
        """The Fault class URI itself is in
        list_fault_prototypes, so an atom tagged with the class
        rather than an individual also counts."""
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}Fault"),
        ])
        matched, _ = _detect_root_cause_category(e, ontology)
        assert matched

    def test_text_label_match_against_fault_prototype(self, ontology):
        """Atom text 'cpu saturation detected' should token-match
        the CpuSaturation label even without an ontology_class tag."""
        e = _explain_with([
            ExplanationAtom(text="cpu saturation detected on adservice"),
        ])
        matched, _ = _detect_root_cause_category(e, ontology)
        assert matched

    def test_foreign_namespace_uri_does_not_match(self, ontology):
        """yRCA-style atom whose ontology_class is foreign should not
        count via the ontology-side rule."""
        e = _explain_with([
            ExplanationAtom(text="something",
                            ontology_class="yrca:Role/final_root_cause"),
        ])
        matched, _ = _detect_root_cause_category(e, ontology)
        # Token "root cause" might match RootCause label, but RootCause
        # is not a Fault prototype; so this should return False.
        assert not matched

    def test_recommendation_uri_does_not_match_root_cause(self, ontology):
        """An atom tagged with a Rec_* URI is a mitigation, not a
        root cause."""
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}Rec_CpuSaturation"),
        ])
        matched, _ = _detect_root_cause_category(e, ontology)
        assert not matched

    def test_empty_explanation_returns_false(self, ontology):
        matched, atoms = _detect_root_cause_category(
            CanonicalExplanation(), ontology,
        )
        assert not matched
        assert atoms == []


# ---- 3. affected-component detector ---------------------------------------


class TestAffectedComponentDetector:
    def test_atom_text_contains_service_name(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="anomaly on cartservice at t=42"),
        ])
        matched, atoms = _detect_affected_component_category(
            e, ontology, case_services=["cartservice", "frontend"],
        )
        assert matched
        assert len(atoms) == 1

    def test_service_name_match_is_case_insensitive(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="CartService is degraded"),
        ])
        matched, _ = _detect_affected_component_category(
            e, ontology, case_services=["cartservice"],
        )
        assert matched

    def test_no_match_when_service_name_absent(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="generic anomaly detected"),
        ])
        matched, _ = _detect_affected_component_category(
            e, ontology, case_services=["cartservice", "frontend"],
        )
        assert not matched

    def test_microservice_class_uri_matches(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}MicroService"),
        ])
        matched, _ = _detect_affected_component_category(
            e, ontology, case_services=[],
        )
        assert matched

    def test_empty_service_list_with_no_uri_returns_false(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="anomaly on cartservice"),
        ])
        matched, _ = _detect_affected_component_category(
            e, ontology, case_services=[],
        )
        assert not matched

    def test_whole_token_match_not_substring(self, ontology):
        """``adservice`` is a content token; ``loadservice_proxy``
        tokenises to ``loadservice``/``proxy``, neither of which
        equals ``adservice``. No match."""
        e = _explain_with([
            ExplanationAtom(text="loadservice_proxy reports anomaly"),
        ])
        matched, _ = _detect_affected_component_category(
            e, ontology, case_services=["adservice"],
        )
        assert not matched


# ---- 4. mitigation detector -----------------------------------------------


class TestMitigationDetector:
    def test_rec_individual_uri_matches(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}Rec_CpuSaturation"),
        ])
        matched, atoms = _detect_mitigation_category(e, ontology)
        assert matched
        assert len(atoms) == 1

    def test_recommendation_class_uri_matches(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}Recommendation"),
        ])
        matched, _ = _detect_mitigation_category(e, ontology)
        assert matched

    def test_fault_uri_does_not_match_mitigation(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),
        ])
        matched, _ = _detect_mitigation_category(e, ontology)
        assert not matched

    def test_unrelated_text_does_not_match(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="cartservice anomaly"),
        ])
        matched, _ = _detect_mitigation_category(e, ontology)
        assert not matched


# ---- 5. overall scoring ---------------------------------------------------


class TestOverallScoring:
    """The four-valued aggregate. Each category is a binary; total = count/3."""

    def test_all_three_categories_scores_one(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="cartservice anomaly"),
            ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation"),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == pytest.approx(1.0, abs=1e-9)

    def test_two_categories_scores_two_thirds(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="cartservice anomaly"),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == pytest.approx(2.0 / 3.0, abs=1e-9)

    def test_one_category_scores_one_third(self, ontology):
        """MR/CR/Micro/BARO scenario: only the component shows up."""
        e = _explain_with([
            ExplanationAtom(text="cartservice ranked top-1"),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == pytest.approx(1.0 / 3.0, abs=1e-9)

    def test_no_category_scores_zero(self, ontology):
        """Methods that emit no grounded atoms and no service names."""
        e = _explain_with([
            ExplanationAtom(text="opaque attention vector dim 42"),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == 0.0

    def test_empty_explanation_returns_zero(self, ontology):
        s = ExplanationCompleteness().score(
            CanonicalExplanation(), ontology, case_services=["cartservice"],
        )
        assert s == 0.0


# ---- 6. score_with_breakdown contract -------------------------------------


class TestScoreWithBreakdown:
    def test_breakdown_fields_present(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="cartservice anomaly"),
            ExplanationAtom(text="rec", ontology_class=f"{_NS}Rec_CpuSaturation"),
        ])
        br = ExplanationCompleteness().score_with_breakdown(
            e, ontology, case_services=["cartservice"],
        )
        assert set(br.keys()) == {
            "overall", "categories_present", "has_cause", "has_component",
            "has_mitigation", "detection_details",
        }
        assert set(br["detection_details"].keys()) == {
            "cause_atoms", "component_atoms", "mitigation_atoms",
        }

    def test_categories_present_lists_matched_categories(self, ontology):
        e = _explain_with([
            ExplanationAtom(text="cpu", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="cartservice anomaly"),
        ])
        br = ExplanationCompleteness().score_with_breakdown(
            e, ontology, case_services=["cartservice"],
        )
        assert br["categories_present"] == ["cause", "component"]
        assert br["has_cause"] is True
        assert br["has_component"] is True
        assert br["has_mitigation"] is False

    def test_detection_details_atom_ids_traceable(self, ontology):
        cpu = ExplanationAtom(
            text="cpu", ontology_class=f"{_NS}CpuSaturation",
        )
        rec = ExplanationAtom(
            text="rec", ontology_class=f"{_NS}Rec_CpuSaturation",
        )
        svc = ExplanationAtom(text="cartservice anomaly")
        e = _explain_with([cpu, rec, svc])
        br = ExplanationCompleteness().score_with_breakdown(
            e, ontology, case_services=["cartservice"],
        )
        assert cpu.id in br["detection_details"]["cause_atoms"]
        assert rec.id in br["detection_details"]["mitigation_atoms"]
        assert svc.id in br["detection_details"]["component_atoms"]

    def test_breakdown_for_empty_explanation(self, ontology):
        br = ExplanationCompleteness().score_with_breakdown(
            CanonicalExplanation(), ontology,
        )
        assert br["overall"] == 0.0
        assert br["categories_present"] == []
        assert not br["has_cause"]
        assert not br["has_component"]
        assert not br["has_mitigation"]
        assert br["detection_details"]["cause_atoms"] == []


# ---- 7. tokenisation helper ----------------------------------------------


class TestContentTokens:
    def test_lowercases_and_strips_punctuation(self):
        assert _content_tokens("CartService is DOWN!") == frozenset(
            {"cartservice", "down"}
        )

    def test_drops_short_tokens(self):
        assert _content_tokens("a b cd cpu of") == frozenset({"cpu"})


# ---- 8. realistic method shape regressions -------------------------------


class TestMethodShapeRegressions:
    """Quick spot-checks for the per-method expected EC pattern from
    the brief: FCP=1.0, yRCA=0.667, MR/CR/Micro/BARO=0.333."""

    def test_fcp_style_explanation_scores_one(self, ontology):
        """FCP atoms typically carry Fault-prototype + service-name
        text + Recommendation-tagged atom."""
        e = _explain_with([
            ExplanationAtom(
                text="#1 cartservice → CpuSaturation H=0.85",
                ontology_class=f"{_NS}CpuSaturation",
            ),
            ExplanationAtom(
                text="Recommendation for cartservice: Rec_CpuSaturation",
                ontology_class=f"{_NS}Rec_CpuSaturation",
            ),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice", "frontend"],
        )
        assert s == pytest.approx(1.0, abs=1e-9)

    def test_yrca_style_explanation_scores_two_thirds(self, ontology):
        """yRCA atoms name a service in text and carry a fault-like
        text token (yRCA's text typically includes things like
        ``cpu_high``). No mitigation."""
        e = _explain_with([
            ExplanationAtom(
                text="final_root_cause: cartservice cpu saturation",
                ontology_class="yrca:Role/final_root_cause",
            ),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == pytest.approx(2.0 / 3.0, abs=1e-9)

    def test_mr_style_explanation_scores_one_third(self, ontology):
        """MR/CR/Micro/BARO predict a service name only — no fault
        type, no mitigation."""
        e = _explain_with([
            ExplanationAtom(text="cartservice ranked #1 by personalized pagerank"),
        ])
        s = ExplanationCompleteness().score(
            e, ontology, case_services=["cartservice"],
        )
        assert s == pytest.approx(1.0 / 3.0, abs=1e-9)
