"""Tests for the canonical-explanation dataclasses."""

from __future__ import annotations

import pytest

from evaluation.extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    CausalLink,
    DiagnosticOutput,
    ExplanationAtom,
)


# ---------- ExplanationAtom ----------


def test_atom_minimal():
    a = ExplanationAtom(text="cpu spike on cart")
    assert a.text == "cpu spike on cart"
    assert a.ontology_class is None
    assert a.fuzzy_membership is None
    assert isinstance(a.id, str) and a.id  # auto-generated


def test_atom_full():
    a = ExplanationAtom(
        text="cpu spike",
        ontology_class="http://foda.example.org/onto#CPUSaturation",
        fuzzy_membership=0.7,
        id="atom-1",
    )
    assert a.id == "atom-1"
    assert a.fuzzy_membership == 0.7
    assert a.ontology_class.endswith("#CPUSaturation")


def test_atom_unique_default_ids():
    a = ExplanationAtom(text="x")
    b = ExplanationAtom(text="x")
    assert a.id != b.id


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
def test_atom_rejects_bad_membership(bad):
    with pytest.raises(ValueError):
        ExplanationAtom(text="x", fuzzy_membership=bad)


# ---------- CausalLink ----------


def test_link_minimal():
    link = CausalLink(source_atom_id="a", target_atom_id="b")
    assert link.source_atom_id == "a"
    assert link.weight is None
    assert link.relation_type is None


def test_link_full():
    link = CausalLink(
        source_atom_id="a",
        target_atom_id="b",
        weight=0.9,
        relation_type="causes",
    )
    assert link.weight == 0.9
    assert link.relation_type == "causes"


@pytest.mark.parametrize("bad", [-0.5, 1.01])
def test_link_rejects_bad_weight(bad):
    with pytest.raises(ValueError):
        CausalLink(source_atom_id="a", target_atom_id="b", weight=bad)


# ---------- CanonicalExplanation ----------


def _three_atom_chain() -> tuple[CanonicalExplanation, list[ExplanationAtom]]:
    g = CanonicalExplanation()
    a = ExplanationAtom(text="net latency", id="a")
    b = ExplanationAtom(text="downstream timeout", id="b")
    c = ExplanationAtom(text="checkout failure", id="c")
    for atom in (a, b, c):
        g.add_atom(atom)
    g.add_link(CausalLink(source_atom_id="a", target_atom_id="b"))
    g.add_link(CausalLink(source_atom_id="b", target_atom_id="c"))
    return g, [a, b, c]


def test_canonical_construction_roots_leaves():
    g, (a, _, c) = _three_atom_chain()
    assert len(g) == 3
    roots = g.roots()
    leaves = g.leaves()
    assert [r.id for r in roots] == ["a"]
    assert [l.id for l in leaves] == ["c"]
    assert "a" in g and "c" in g and "missing" not in g


def test_canonical_get_atom_and_iteration():
    g, (a, b, c) = _three_atom_chain()
    assert g.get_atom("b").text == "downstream timeout"
    ids = sorted(atom.id for atom in g.atoms())
    assert ids == ["a", "b", "c"]


def test_canonical_links_round_trip():
    g, _ = _three_atom_chain()
    links = list(g.links())
    pairs = {(l.source_atom_id, l.target_atom_id) for l in links}
    assert pairs == {("a", "b"), ("b", "c")}


def test_canonical_link_preserves_weight_and_relation():
    g = CanonicalExplanation()
    g.add_atom(ExplanationAtom(text="x", id="x"))
    g.add_atom(ExplanationAtom(text="y", id="y"))
    g.add_link(
        CausalLink(
            source_atom_id="x",
            target_atom_id="y",
            weight=0.42,
            relation_type="manifestsAs",
        )
    )
    [link] = list(g.links())
    assert link.weight == 0.42
    assert link.relation_type == "manifestsAs"


def test_canonical_duplicate_atom_rejected():
    g = CanonicalExplanation()
    g.add_atom(ExplanationAtom(text="x", id="x"))
    with pytest.raises(ValueError):
        g.add_atom(ExplanationAtom(text="x-other", id="x"))


def test_canonical_link_to_unknown_atom_rejected():
    g = CanonicalExplanation()
    g.add_atom(ExplanationAtom(text="x", id="x"))
    with pytest.raises(KeyError):
        g.add_link(CausalLink(source_atom_id="x", target_atom_id="missing"))
    with pytest.raises(KeyError):
        g.add_link(CausalLink(source_atom_id="missing", target_atom_id="x"))


def test_canonical_isolated_atom_is_both_root_and_leaf():
    g = CanonicalExplanation()
    g.add_atom(ExplanationAtom(text="solo", id="solo"))
    assert [a.id for a in g.roots()] == ["solo"]
    assert [a.id for a in g.leaves()] == ["solo"]


# ---------- BenchmarkCase ----------


def test_benchmark_case_minimal():
    case = BenchmarkCase(
        id="case-1",
        telemetry={"cpu": [0.1, 0.9]},
        ground_truth_root_cause="svc-a",
        ground_truth_fault_type="cpu_saturation",
        system_topology={"svc-a": ["svc-b"]},
    )
    assert case.id == "case-1"
    assert case.ontology_mapping is None


def test_benchmark_case_with_mapping():
    case = BenchmarkCase(
        id="case-2",
        telemetry=None,
        ground_truth_root_cause="svc-x",
        ground_truth_fault_type="net_loss",
        system_topology=None,
        ontology_mapping={"cpu_pct": "http://foda#CPU"},
    )
    assert case.ontology_mapping == {"cpu_pct": "http://foda#CPU"}


# ---------- DiagnosticOutput ----------


def test_diagnostic_output_construction():
    g = CanonicalExplanation()
    out = DiagnosticOutput(
        ranked_list=[("svc-a", 0.9), ("svc-b", 0.4)],
        explanation_chain=g,
        confidence=0.8,
        raw_output={"any": "blob"},
        method_name="foda-fcp",
        wall_time_ms=12.5,
    )
    assert out.ranked_list[0] == ("svc-a", 0.9)
    assert out.method_name == "foda-fcp"
    assert out.confidence == 0.8


def test_diagnostic_output_confidence_none_allowed():
    g = CanonicalExplanation()
    out = DiagnosticOutput(
        ranked_list=[],
        explanation_chain=g,
        confidence=None,
        raw_output=None,
        method_name="x",
        wall_time_ms=0.0,
    )
    assert out.confidence is None


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_diagnostic_output_rejects_bad_confidence(bad):
    g = CanonicalExplanation()
    with pytest.raises(ValueError):
        DiagnosticOutput(
            ranked_list=[],
            explanation_chain=g,
            confidence=bad,
            raw_output=None,
            method_name="x",
            wall_time_ms=0.0,
        )
