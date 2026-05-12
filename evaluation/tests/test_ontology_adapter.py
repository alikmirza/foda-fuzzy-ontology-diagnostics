"""Tests for ``evaluation.metrics.ontology_adapter.OntologyAdapter``."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.metrics.ontology_adapter import (
    DEFAULT_ONTOLOGY_PATH,
    OntologyAdapter,
)


_NS = "http://foda.com/ontology/diagnostic#"

# Known classes (owl:Class declarations in DiagnosticKB.owl).
_KNOWN_CLASSES = {
    "Fault", "MicroService", "RootCause", "Anomaly", "MLModel",
    "ContributingFactor", "DiagnosticResult", "Metric", "Recommendation",
    "Severity", "Symptom",
}

# Known individuals (NamedIndividuals — fault prototypes, recommendations,
# severities). FODA-FCP tags atoms against these.
_KNOWN_INDIVIDUALS_SAMPLE = {
    "CpuSaturation", "MemoryLeak", "LatencySpike", "HighErrorRate",
    "ResourceContention", "Rec_CpuSaturation", "Rec_MemoryLeak",
    "Low", "Medium", "High", "Critical",
}


# ---- 1. construction / loading --------------------------------------------


class TestLoad:
    def test_default_path_resolves(self):
        assert DEFAULT_ONTOLOGY_PATH.is_file(), (
            f"DiagnosticKB.owl not found at {DEFAULT_ONTOLOGY_PATH!s} — "
            f"the adapter's default path is wrong"
        )

    def test_construction_loads_known_entity_count(self):
        o = OntologyAdapter()
        # 11 classes + 36 individuals = 47 known entities at the time
        # of writing. Be tolerant of small ontology evolution: assert
        # roughly the expected counts.
        assert len(o.list_strict_classes()) >= 10
        assert len(o) >= 40, (
            f"expected >= 40 known entities (classes+individuals), got {len(o)}"
        )

    def test_base_iri_matches_ontology_namespace(self):
        o = OntologyAdapter()
        assert o.base_iri == _NS

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="not found"):
            OntologyAdapter(ontology_path=tmp_path / "does_not_exist.owl")


# ---- 2. has_class / is_strict_class ---------------------------------------


class TestHasClass:
    @pytest.fixture(scope="class")
    def adapter(self) -> OntologyAdapter:
        return OntologyAdapter()

    @pytest.mark.parametrize("local_name", sorted(_KNOWN_CLASSES))
    def test_known_classes_return_true(self, adapter, local_name):
        assert adapter.has_class(f"{_NS}{local_name}")

    @pytest.mark.parametrize("local_name", sorted(_KNOWN_INDIVIDUALS_SAMPLE))
    def test_known_individuals_return_true(self, adapter, local_name):
        """FODA-FCP atoms are tagged with individuals like
        ``#CpuSaturation``. ``has_class`` accepts these because the
        metric's intent is "is this URI defined in the ontology"."""
        assert adapter.has_class(f"{_NS}{local_name}")

    def test_made_up_uri_returns_false(self, adapter):
        assert not adapter.has_class(f"{_NS}DefinitelyNotInOntology")

    def test_malformed_uri_returns_false(self, adapter):
        assert not adapter.has_class("not-a-uri")
        assert not adapter.has_class("")
        assert not adapter.has_class(
            "http://different-ontology.com/foo#CpuSaturation"
        )

    def test_is_strict_class_distinguishes_class_from_individual(self, adapter):
        assert adapter.is_strict_class(f"{_NS}Fault")             # class
        assert not adapter.is_strict_class(f"{_NS}CpuSaturation")  # individual

    def test_list_classes_is_superset_of_list_strict_classes(self, adapter):
        broad = set(adapter.list_classes())
        strict = set(adapter.list_strict_classes())
        assert strict.issubset(broad)
        assert len(broad) > len(strict)  # individuals exist


# ---- 3. list_labels --------------------------------------------------------


class TestLabels:
    @pytest.fixture(scope="class")
    def adapter(self) -> OntologyAdapter:
        return OntologyAdapter()

    def test_every_known_entity_has_a_label(self, adapter):
        labels = adapter.list_labels()
        for uri in adapter.list_classes():
            assert uri in labels
            assert labels[uri]  # non-empty

    def test_returns_a_copy(self, adapter):
        a = adapter.list_labels()
        b = adapter.list_labels()
        a["mutated"] = "value"
        assert "mutated" not in b


# ---- 4. find_class_by_label -----------------------------------------------


class TestFindClassByLabel:
    @pytest.fixture(scope="class")
    def adapter(self) -> OntologyAdapter:
        return OntologyAdapter()

    @pytest.mark.parametrize(
        "query,expected_local",
        [
            ("CPU Saturation",   "CpuSaturation"),
            ("Memory Leak",      "MemoryLeak"),
            ("Latency Spike",    "LatencySpike"),
            ("Resource Contention", "ResourceContention"),
        ],
    )
    def test_exact_label_resolves_to_correct_uri(
        self, adapter, query, expected_local
    ):
        uri = adapter.find_class_by_label(query)
        assert uri == f"{_NS}{expected_local}"

    @pytest.mark.parametrize(
        "query",
        ["Cpu Saturation", "cpu saturation", "CPU SATURATION"],
    )
    def test_fuzzy_matches_cpu_saturation_case_variants(self, adapter, query):
        """Token-aligned: every label content token (``cpu``,
        ``saturation``) must appear as a whole token in the query.
        Case is normalised by ``utils.default_process``; underscores
        are split into separate tokens; stem variants
        (``"saturated"``) are NOT whole tokens and do NOT match —
        documented behaviour change from the partial-ratio era."""
        uri = adapter.find_class_by_label(query)
        assert uri == f"{_NS}CpuSaturation", (
            f"query {query!r} did not token-match CpuSaturation"
        )

    def test_stem_variant_does_not_match(self, adapter):
        """``"saturated"`` is a different whole token from
        ``"saturation"``; token-aligned matching correctly rejects
        the stem variant. Regression vs the partial-ratio version,
        where character-level alignment falsely passed this case."""
        assert adapter.find_class_by_label("cpu saturated") is None

    def test_atom_text_embedding_label_matches(self, adapter):
        """Atom text embedding the label as separate whole tokens
        still matches. ``"CpuSaturation"`` (no space, a single token)
        does NOT match by itself — atoms emitted with such a tag
        should set ``ontology_class`` directly rather than rely on
        the fuzzy text fallback."""
        atom_text = "#1 db → Cpu Saturation (H=0.92, C=0.95)"
        uri = adapter.find_class_by_label(atom_text)
        assert uri is not None
        assert "CpuSaturation" in uri

    def test_underscore_separated_label_in_text_matches(self, adapter):
        """``"final_root_cause"`` becomes the tokens ``"final"`` /
        ``"root"`` / ``"cause"`` after default_process, so atom text
        containing the underscored phrase whole-matches the
        RootCause label (yRCA's legitimate fuzzy match)."""
        atom = "adservice [final_root_cause] severity=748.11"
        assert adapter.find_class_by_label(atom) == f"{_NS}RootCause"

    @pytest.mark.parametrize(
        "query",
        [
            "banana split",
            "completely unrelated nonsense",
            "frontend service is healthy",  # no label substring overlap
        ],
    )
    def test_nonsense_returns_none(self, adapter, query):
        assert adapter.find_class_by_label(query) is None

    @pytest.mark.parametrize("query", ["", " ", "  \t  "])
    def test_empty_returns_none(self, adapter, query):
        assert adapter.find_class_by_label(query) is None

    @pytest.mark.parametrize("query", ["a", "I", "is", "to"])
    def test_too_short_returns_none(self, adapter, query):
        """Short queries below the minimum length filter return None,
        preventing partial-ratio false positives."""
        assert adapter.find_class_by_label(query) is None

    def test_partial_label_coverage_below_threshold(self, adapter):
        """``"cpu running hot"`` covers 1 of 2 RootCause-like label
        tokens (just ``"cpu"`` of ``{"cpu", "saturation"}`` ⇒ 50%
        coverage), below the 70% default threshold."""
        assert adapter.find_class_by_label("cpu running hot") is None

    def test_threshold_must_be_in_unit_interval(self, adapter):
        with pytest.raises(ValueError, match="threshold"):
            adapter.find_class_by_label("Cpu", threshold=-0.1)
        with pytest.raises(ValueError, match="threshold"):
            adapter.find_class_by_label("Cpu", threshold=1.1)

    def test_default_threshold_is_seven_tenths(self, adapter):
        """A 1-of-2 label-token coverage scores 50% — below the
        default 0.7. A 2-of-2 label-token coverage scores 100% —
        above. The default threshold is honoured both ways."""
        # "memory" alone is 1 of 2 MemoryLeak tokens → 50% → no match.
        assert adapter.find_class_by_label("memory issue here") is None
        # "memory leak" is 2 of 2 → 100% → matches.
        assert adapter.find_class_by_label("memory leak") is not None
        # At threshold 0.99 even the 2-of-2 case clears (coverage = 1.0 ≥ 0.99).
        assert adapter.find_class_by_label("memory leak", threshold=0.99) is not None


# ---- 4b. fuzzy class blacklist --------------------------------------------


class TestFuzzyClassBlacklist:
    """Abstract OWL classes (``Anomaly``, ``Severity``, ``Metric``, …)
    are short, generic single-token labels — under token alignment a
    free-text atom containing the exact word ``"severity"`` or
    ``"anomaly"`` would still whole-token-match. The blacklist gives
    defence in depth: even when an atom literally mentions one of
    these generic class names, we suppress the match so SG rewards
    grounding against SPECIFIC concept entities only. Direct URI
    lookups still resolve blacklisted classes."""

    def test_default_blacklist_suppresses_severity_match(self):
        """yRCA atoms contain the literal token ``"severity"``; the
        ``Severity`` class would whole-token-match under token
        alignment. The default blacklist suppresses this so yRCA's
        SG credit comes from the more specific ``RootCause`` match
        rather than from generic Severity mentions."""
        adapter = OntologyAdapter()
        atom = "adservice [final_root_cause] severity=748.11"
        # Must NOT return Severity — should fall through to RootCause.
        match = adapter.find_class_by_label(atom)
        assert match != f"{_NS}Severity"
        assert match == f"{_NS}RootCause"

    def test_direct_class_lookup_still_resolves_blacklisted(self):
        """The blacklist suppresses FUZZY matching only.
        :meth:`has_class` still returns True for blacklisted classes."""
        adapter = OntologyAdapter()
        for local in ["Anomaly", "Severity", "Metric", "MicroService"]:
            assert adapter.has_class(f"{_NS}{local}")

    def test_explicit_label_lookup_for_blacklisted_returns_none(self):
        """Searching for the literal label ``"Anomaly"`` (or
        ``"Severity"``) returns ``None`` because the entity is in the
        blacklist; specific concepts (individuals like CpuSaturation)
        are unaffected."""
        adapter = OntologyAdapter()
        assert adapter.find_class_by_label("Anomaly") is None
        assert adapter.find_class_by_label("Severity report") is None
        assert adapter.find_class_by_label("CPU Saturation") is not None

    def test_empty_blacklist_lets_severity_match(self):
        """With the blacklist cleared, ``"severity"`` whole-token-
        matches Severity. Confirms the blacklist (not the
        tokenisation) is what suppresses generic-class matches in
        the default configuration."""
        adapter = OntologyAdapter(fuzzy_class_blacklist=frozenset())
        atom = "adservice [final_root_cause] severity=748.11"
        match = adapter.find_class_by_label(atom)
        # With Severity unblocked the atom whole-token-matches both
        # Severity (1/1 coverage = 100%) and RootCause (2/2 coverage =
        # 100%). The tiebreaker prefers the shorter label.
        assert match in {f"{_NS}Severity", f"{_NS}RootCause"}

    def test_custom_blacklist_filters_specified_labels(self):
        """Caller-controlled blacklist: exclude only ``RootCause``.
        ``"final_root_cause"`` text then falls through to other
        candidates (or returns ``None`` when nothing else matches)."""
        adapter = OntologyAdapter(
            fuzzy_class_blacklist=frozenset({"RootCause"})
        )
        match = adapter.find_class_by_label(
            "service db is the root cause"
        )
        assert match != f"{_NS}RootCause"


# ---- 4c. token-alignment regression tests ---------------------------------


class TestTokenAlignmentRegressions:
    """Three named regression cases that lock in the documented
    semantics of the token-aligned fuzzy matcher. These derive from
    the spot-check that uncovered the partial-ratio character-
    substring artifact on DejaVu attention atoms; the fix is to
    require WHOLE-TOKEN coverage of every content token in the label."""

    def test_dejavu_attention_atom_does_not_match_rootcause(self):
        """DejaVu attention atoms of shape ``"attended: X (α=… from
        Y)"`` previously partial-matched the RootCause class at
        exactly 70% via the character substring ``"rt cause"`` inside
        ``"from cartservice"``. Under token alignment the atom has
        no whole token matching either ``"root"`` or ``"cause"``, so
        the match is correctly suppressed."""
        adapter = OntologyAdapter()
        for text in (
            "attended: shippingservice (α=0.435 from cartservice)",
            "attended: checkoutservice (α=0.156 from cartservice)",
            "attended: frontend (α=0.115 from cartservice)",
        ):
            match = adapter.find_class_by_label(text)
            assert match is None, (
                f"text {text!r} unexpectedly matched {match!r}; "
                f"DejaVu attention attribution must not score "
                f"against any DiagnosticKB class"
            )

    def test_yrca_role_atom_matches_rootcause(self):
        """yRCA atoms with ``[final_root_cause]`` role tags MUST
        still whole-token-match the ``RootCause`` class — the
        documented legitimate fuzzy-match path that scores 0.5 in
        SemanticGroundedness for every yRCA case."""
        adapter = OntologyAdapter()
        atom = "adservice [final_root_cause] severity=748.11, derived_by_rules=['R1']"
        assert adapter.find_class_by_label(atom) == f"{_NS}RootCause"

    def test_token_alignment_rejects_character_substring(self):
        """Pure character-substring overlap is rejected: the token
        ``"cartservice"`` contains the character substring
        ``"rt"`` ⊂ ``"root"`` and ``"ca"`` ⊂ ``"cause"`` but as a
        single whole token does not match either of RootCause's
        content tokens. Locks in that the upgrade from partial_ratio
        suppresses this class of accident."""
        adapter = OntologyAdapter()
        assert adapter.find_class_by_label("cartservice") is None
        # Another character-substring trap: "metric" appears INSIDE
        # the longer token "metrics" but they are different whole tokens.
        assert adapter.find_class_by_label("anomalies in cpu metrics") is None


# ---- 4d. propagation lookups (Phase 2 Week 2 — SemanticCoherence) ---------


class TestPropagationStrength:
    """``get_propagation_strength`` and ``list_propagations`` expose
    the 22 typical fault-propagation patterns added to DiagnosticKB
    in Week 2. The metric SemanticCoherence consumes these to score
    whether causal links in method explanations respect known
    propagation directions."""

    @pytest.fixture(scope="class")
    def adapter(self) -> OntologyAdapter:
        return OntologyAdapter()

    def test_typical_propagation_returns_one(self, adapter):
        """``CpuSaturation → LatencySpike`` is one of the 12 strength-1.0
        patterns; cpu saturation almost always manifests as latency."""
        assert adapter.get_propagation_strength(
            f"{_NS}CpuSaturation", f"{_NS}LatencySpike",
        ) == 1.0

    def test_conditional_propagation_returns_half(self, adapter):
        """``MemoryLeak → CpuSaturation`` is one of the 10 strength-0.5
        patterns; GC pressure under a memory leak can pin a core."""
        assert adapter.get_propagation_strength(
            f"{_NS}MemoryLeak", f"{_NS}CpuSaturation",
        ) == 0.5

    def test_undeclared_pair_returns_zero(self, adapter):
        """``HighErrorRate → MemoryLeak`` is not a declared
        propagation; errors don't typically leak memory. Returns 0.0
        per the ontology's "only explicit propagations are typical"
        convention."""
        assert adapter.get_propagation_strength(
            f"{_NS}HighErrorRate", f"{_NS}MemoryLeak",
        ) == 0.0

    def test_self_loop_returns_zero(self, adapter):
        """No Propagation individual declares a self-loop; queries
        return 0.0."""
        assert adapter.get_propagation_strength(
            f"{_NS}CpuSaturation", f"{_NS}CpuSaturation",
        ) == 0.0

    def test_reverse_pair_is_asymmetric(self, adapter):
        """``CpuSaturation → LatencySpike`` is 1.0; the reverse
        ``LatencySpike → CpuSaturation`` is 0.0. Direction matters
        because fault propagation is causal."""
        assert adapter.get_propagation_strength(
            f"{_NS}CpuSaturation", f"{_NS}LatencySpike",
        ) == 1.0
        assert adapter.get_propagation_strength(
            f"{_NS}LatencySpike", f"{_NS}CpuSaturation",
        ) == 0.0

    def test_unknown_class_uri_returns_zero(self, adapter):
        """Malformed or non-DiagnosticKB URIs return 0.0 — never
        raise. The metric should treat unmapped atoms as 0.0
        coherence, not as errors."""
        assert adapter.get_propagation_strength(
            "http://example.com/foo#Bar", f"{_NS}LatencySpike",
        ) == 0.0
        assert adapter.get_propagation_strength(
            "", "",
        ) == 0.0

    def test_list_propagations_has_22_entries(self, adapter):
        """Spec: 12 strength-1.0 + 10 strength-0.5 = 22 typical
        propagation patterns."""
        propagations = adapter.list_propagations()
        assert len(propagations) == 22
        strengths = [s for _, _, s in propagations]
        assert sum(1 for s in strengths if s == 1.0) == 12
        assert sum(1 for s in strengths if s == 0.5) == 10

    def test_list_propagations_is_sorted_and_well_formed(self, adapter):
        propagations = adapter.list_propagations()
        assert propagations == sorted(propagations)
        for src, tgt, strength in propagations:
            assert src.startswith(_NS)
            assert tgt.startswith(_NS)
            assert 0.0 < strength <= 1.0


# ---- 5. introspection ------------------------------------------------------


class TestIntrospection:
    def test_len_matches_list_classes(self):
        o = OntologyAdapter()
        assert len(o) == len(o.list_classes())
