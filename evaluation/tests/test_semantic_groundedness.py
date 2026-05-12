"""Tests for ``evaluation.metrics.semantic_groundedness.SemanticGroundedness``."""

from __future__ import annotations

import pytest

from evaluation.extraction.canonical_explanation import (
    CanonicalExplanation,
    CausalLink,
    ExplanationAtom,
)
from evaluation.metrics.ontology_adapter import OntologyAdapter
from evaluation.metrics.semantic_groundedness import (
    SemanticGroundedness,
    _score_atom,
)


_NS = "http://foda.com/ontology/diagnostic#"


@pytest.fixture(scope="module")
def ontology() -> OntologyAdapter:
    return OntologyAdapter()


def _explanation_with(*atoms: ExplanationAtom) -> CanonicalExplanation:
    e = CanonicalExplanation()
    for a in atoms:
        e.add_atom(a)
    return e


# ---- 1. contract ----------------------------------------------------------


class TestContract:
    def test_default_weights(self):
        m = SemanticGroundedness()
        assert m.direct_weight == 1.0
        assert m.fuzzy_weight == 0.5
        assert m.fuzzy_threshold == 0.7

    def test_name(self):
        assert SemanticGroundedness().name == "semantic_groundedness"

    def test_score_returns_float_in_unit_interval(self, ontology):
        m = SemanticGroundedness()
        e = _explanation_with(
            ExplanationAtom(text="adservice", ontology_class=f"{_NS}CpuSaturation"),
        )
        s = m.score(e, ontology)
        assert isinstance(s, float)
        assert 0.0 <= s <= 1.0

    def test_breakdown_overall_matches_score(self, ontology):
        m = SemanticGroundedness()
        e = _explanation_with(
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="y", ontology_class=f"{_NS}NotARealClass"),
        )
        assert m.score(e, ontology) == m.score_with_breakdown(e, ontology)["overall"]


# ---- 2. direct match ------------------------------------------------------


class TestDirectMatch:
    def test_atom_with_known_class_uri_scores_one(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(
            text="adservice → CpuSaturation",
            ontology_class=f"{_NS}CpuSaturation",
        )
        assert m.score(_explanation_with(atom), ontology) == 1.0

    def test_atom_with_known_individual_uri_scores_one(self, ontology):
        """FODA-FCP tags atoms with NamedIndividual URIs (CpuSaturation,
        Rec_CpuSaturation). The metric MUST treat these as direct
        matches."""
        m = SemanticGroundedness()
        rec_atom = ExplanationAtom(
            text="Recommendation for adservice",
            ontology_class=f"{_NS}Rec_CpuSaturation",
        )
        assert m.score(_explanation_with(rec_atom), ontology) == 1.0

    def test_breakdown_match_type_direct(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="x", ontology_class=f"{_NS}MemoryLeak")
        br = m.score_with_breakdown(_explanation_with(atom), ontology)
        assert br["per_atom"][0]["match_type"] == "direct"
        assert br["per_atom"][0]["matched_class"] == f"{_NS}MemoryLeak"
        assert br["direct_matches"] == 1
        assert br["fuzzy_matches"] == 0
        assert br["unmatched"] == 0


# ---- 3. fuzzy match -------------------------------------------------------


class TestFuzzyMatch:
    def test_atom_text_containing_label_scores_half(self, ontology):
        """Atom with no ontology_class but text containing a known
        label substring falls back to fuzzy match."""
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="The diagnosis is CPU Saturation")
        s = m.score(_explanation_with(atom), ontology)
        assert s == 0.5

    def test_atom_text_with_foreign_ontology_class_falls_through(self, ontology):
        """yRCA-style atoms have ontology_class set to a foreign URI
        (``yrca:Role/final_root_cause``). When that URI doesn't
        resolve in DiagnosticKB, the metric falls back to fuzzy text
        match — NOT a hard zero."""
        m = SemanticGroundedness()
        atom = ExplanationAtom(
            text="db [final_root_cause] severity=5.2",
            ontology_class="yrca:Role/final_root_cause",
        )
        br = m.score_with_breakdown(_explanation_with(atom), ontology)
        # Token-aligned: ``final_root_cause`` is split into the tokens
        # ``"final"`` / ``"root"`` / ``"cause"`` by default_process, so
        # the atom whole-token-matches the RootCause class (2-of-2
        # content tokens). Severity is blacklisted so the literal
        # ``"severity"`` token does NOT match the Severity class.
        assert br["per_atom"][0]["match_type"] == "fuzzy"
        assert br["per_atom"][0]["matched_class"] == (
            "http://foda.com/ontology/diagnostic#RootCause"
        )

    def test_breakdown_match_type_fuzzy(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="The fault is Memory Leak")
        br = m.score_with_breakdown(_explanation_with(atom), ontology)
        assert br["per_atom"][0]["match_type"] == "fuzzy"
        assert br["fuzzy_matches"] == 1


# ---- 4. no match ----------------------------------------------------------


class TestNoMatch:
    def test_unmatched_atom_scores_zero(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="totally unrelated frontend service name")
        assert m.score(_explanation_with(atom), ontology) == 0.0

    def test_atom_with_only_id_and_no_text_or_class_scores_zero(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="")
        assert m.score(_explanation_with(atom), ontology) == 0.0

    def test_breakdown_match_type_none(self, ontology):
        m = SemanticGroundedness()
        atom = ExplanationAtom(text="unrelated nonsense")
        br = m.score_with_breakdown(_explanation_with(atom), ontology)
        assert br["per_atom"][0]["match_type"] == "none"
        assert br["per_atom"][0]["matched_class"] is None
        assert br["unmatched"] == 1


# ---- 5. overall scoring ---------------------------------------------------


class TestOverallScoring:
    def test_mean_of_per_atom_scores(self, ontology):
        m = SemanticGroundedness()
        e = _explanation_with(
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),  # 1.0
            ExplanationAtom(text="The fault is Memory Leak"),                  # 0.5 fuzzy
            ExplanationAtom(text="totally unrelated"),                         # 0.0
        )
        # Mean = (1.0 + 0.5 + 0.0) / 3 = 0.5
        assert m.score(e, ontology) == pytest.approx(0.5, abs=1e-6)

    def test_empty_explanation_returns_zero(self, ontology):
        m = SemanticGroundedness()
        empty = CanonicalExplanation()
        assert m.score(empty, ontology) == 0.0

    def test_breakdown_for_empty_explanation(self, ontology):
        m = SemanticGroundedness()
        br = m.score_with_breakdown(CanonicalExplanation(), ontology)
        assert br == {
            "overall": 0.0,
            "per_atom": [],
            "atom_count": 0,
            "direct_matches": 0,
            "fuzzy_matches": 0,
            "unmatched": 0,
        }

    def test_links_are_ignored(self, ontology):
        """Links are scored by ExplanationCompleteness / SemanticCoherence,
        not by SemanticGroundedness. The metric must consider only
        atoms."""
        m = SemanticGroundedness()
        a = ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation")
        b = ExplanationAtom(text="y", ontology_class=f"{_NS}MemoryLeak")
        e = CanonicalExplanation()
        e.add_atom(a)
        e.add_atom(b)
        e.add_link(CausalLink(
            source_atom_id=a.id, target_atom_id=b.id,
            weight=0.5, relation_type="bogus_relation_not_in_ontology",
        ))
        # Two direct matches → 1.0, regardless of the bogus link.
        assert m.score(e, ontology) == 1.0


# ---- 6. breakdown output --------------------------------------------------


class TestBreakdown:
    def test_breakdown_lists_every_atom_in_order(self, ontology):
        m = SemanticGroundedness()
        atoms = [
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="The fault is Memory Leak"),
            ExplanationAtom(text="unrelated frontend service"),
        ]
        e = _explanation_with(*atoms)
        br = m.score_with_breakdown(e, ontology)
        assert br["atom_count"] == 3
        assert len(br["per_atom"]) == 3
        # Per-atom rows expose atom_id so downstream code can join.
        for row, atom in zip(br["per_atom"], atoms):
            assert row["atom_id"] == atom.id

    def test_counts_partition_atoms(self, ontology):
        """``direct_matches + fuzzy_matches + unmatched == atom_count``."""
        m = SemanticGroundedness()
        e = _explanation_with(
            ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation"),
            ExplanationAtom(text="The fault is Memory Leak"),
            ExplanationAtom(text="unrelated frontend service"),
            ExplanationAtom(text="y", ontology_class=f"{_NS}Rec_MemoryLeak"),
        )
        br = m.score_with_breakdown(e, ontology)
        assert (
            br["direct_matches"] + br["fuzzy_matches"] + br["unmatched"]
            == br["atom_count"]
        )


# ---- 7. configurable weights ---------------------------------------------


class TestConfigurableWeights:
    def test_custom_direct_weight(self, ontology):
        m = SemanticGroundedness(direct_weight=0.9, fuzzy_weight=0.4)
        atom = ExplanationAtom(text="x", ontology_class=f"{_NS}CpuSaturation")
        assert m.score(_explanation_with(atom), ontology) == 0.9

    def test_custom_fuzzy_weight(self, ontology):
        m = SemanticGroundedness(direct_weight=1.0, fuzzy_weight=0.25)
        atom = ExplanationAtom(text="The fault is Memory Leak")
        assert m.score(_explanation_with(atom), ontology) == 0.25

    def test_threshold_too_loose_picks_up_more_fuzzy_matches(self, ontology):
        """Threshold controls minimum label-content-token coverage.
        At 0.4 a 1-of-2 coverage (50%) clears; at 0.95 only full
        coverage suffices."""
        loose = SemanticGroundedness(fuzzy_threshold=0.4)
        tight = SemanticGroundedness(fuzzy_threshold=0.95)
        # "cpu only" covers ``"cpu"`` of the {"cpu", "saturation"}
        # CpuSaturation label tokens → 50%. Below tight's 95%, above
        # loose's 40%.
        atom = ExplanationAtom(text="cpu only here")
        assert loose.score(_explanation_with(atom), ontology) > tight.score(
            _explanation_with(atom), ontology
        )


# ---- 8. input validation --------------------------------------------------


class TestInputValidation:
    @pytest.mark.parametrize("w", [-0.1, 1.1, 2.0])
    def test_direct_weight_must_be_in_unit_interval(self, w):
        with pytest.raises(ValueError, match="direct_weight"):
            SemanticGroundedness(direct_weight=w)

    def test_fuzzy_weight_must_not_exceed_direct(self):
        with pytest.raises(ValueError, match="fuzzy_weight"):
            SemanticGroundedness(direct_weight=0.5, fuzzy_weight=0.8)

    @pytest.mark.parametrize("t", [-0.1, 1.1])
    def test_threshold_must_be_in_unit_interval(self, t):
        with pytest.raises(ValueError, match="fuzzy_threshold"):
            SemanticGroundedness(fuzzy_threshold=t)


# ---- 9. _score_atom unit tests --------------------------------------------


class TestScoreAtomHelper:
    def test_malformed_uri_falls_through_to_text_match(self, ontology):
        atom = ExplanationAtom(
            text="The fault is CPU Saturation",
            ontology_class="not://a/real/uri",
        )
        s = _score_atom(atom, ontology, 1.0, 0.5, 0.7)
        assert s.match_type == "fuzzy"
        assert s.subscore == 0.5

    def test_missing_text_with_unknown_class_scores_zero(self, ontology):
        atom = ExplanationAtom(
            text="",
            ontology_class="not://a/real/uri",
        )
        s = _score_atom(atom, ontology, 1.0, 0.5, 0.7)
        assert s.match_type == "none"
        assert s.subscore == 0.0
