"""ExplanationCompleteness — does a diagnosis answer the three
operator-actionable questions: *what kind of fault*, *which service*,
*what mitigation*?

Where :class:`SemanticGroundedness` scores how many atoms reference
ontology entities and :class:`SemanticCoherence` scores how well
causal-link directions agree with the ontology's propagation table,
:class:`ExplanationCompleteness` (EC) scores whether the three
information categories an operator needs to act are *present at all*.
The four metrics are deliberately complementary: a method can ground
some atoms (SG > 0) without surfacing a mitigation (EC < 1.0), or
emit a coherent propagation chain (SC > 0) without ever naming the
affected service.

Per-explanation scoring
-----------------------

EC is a flat binary OR-detector per category, aggregated as the
fraction of the three categories present::

    overall = (has_cause + has_component + has_mitigation) / 3.0

The score takes one of four discrete values:
``{0.0, 0.333, 0.667, 1.0}``. EC deliberately does NOT count *how
many* atoms in each category appear, only whether the category is
present — partial credit on a single missing category is what
differentiates EC from a count-based metric like SG.

Category detectors
------------------

Each ``_detect_*`` helper is method-agnostic: it inspects the
``CanonicalExplanation`` only, never the original case or method
name. Each returns ``True`` if any atom satisfies an
ontology-side OR a text-side rule. The text-side rule reuses the
token-aligned label-matching machinery shipped in Phase 2 Week 1
(SG) — same threshold (0.7 coverage), same tokenisation
(``rapidfuzz.utils.default_process`` + min-length-3 content
tokens) — so a method whose atoms carry free text can still score
positive when the text contains the right whole tokens.

* **Root cause category** — atom has ``ontology_class`` in
  :meth:`OntologyAdapter.list_fault_prototypes` (Fault class or
  any Fault individual), OR atom text token-matches a Fault
  prototype label via
  :meth:`OntologyAdapter.find_class_by_label` at coverage ≥ 0.7
  and that match resolves to a fault prototype.

* **Affected component category** — atom has ``ontology_class`` in
  :meth:`OntologyAdapter.list_microservices` (MicroService class
  or any declared MicroService individual), OR atom text contains
  any service name from ``case_services`` as a whole content
  token (case-insensitive, after default-process normalisation).
  The text rule is what MR/CR/Micro/BARO/DejaVu all satisfy —
  these methods predict service names and emit them as atom
  text — and is the only detector EC has for the affected-
  component axis because DiagnosticKB doesn't enumerate specific
  services (the runtime discovers them per case).

* **Mitigation category** — atom has ``ontology_class`` in
  :meth:`OntologyAdapter.list_recommendations` (Recommendation
  class or any ``Rec_*`` individual), OR atom text token-matches
  a Recommendation label at coverage ≥ 0.7. Only FODA-FCP
  currently emits Recommendation atoms; the other six methods
  score 0.0 on this category.

Threshold rationale
-------------------

The text-level fuzzy-match threshold is fixed at 0.7 to match
SG's contract — a method that token-grounds an atom for SG also
grounds it for EC, and vice versa. No per-metric tuning knob
since the underlying token alignment is shared with SG.

The whole-content-token rule for the service-name match defends
against false positives where an atom's text contains a service
name as a substring of another word (e.g. ``"adservice"`` in
``"loadservice_proxy"`` would not match because the tokenisation
is whitespace-and-punctuation-aware). Reuses the same
``default_process`` + min-length-3 token semantics as Week 1 SG.

Overall scoring contract
------------------------

* Empty explanation (no atoms) ⇒ ``overall = 0.0``.
* Score is always one of ``{0.0, 0.333…, 0.666…, 1.0}``.
* ``score`` and ``score_with_breakdown`` agree on the overall
  number; the breakdown additionally reports which categories
  matched and which atom IDs contributed.

Configurable knobs
------------------

* :data:`_TEXT_MATCH_THRESHOLD` — coverage cutoff for the
  token-aligned label match (0.7, same as SG).
* :data:`_MIN_TOKEN_LEN` — min content-token length for the
  service-name text rule (3 chars, same as SG).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rapidfuzz import utils

from ..extraction.canonical_explanation import CanonicalExplanation
from .base import SemanticMetric
from .ontology_adapter import OntologyAdapter


#: Coverage threshold for the token-aligned label match, mirroring
#: SG's contract. Atoms whose text content tokens cover ≥ 70 % of a
#: candidate label's content tokens count as a label match.
_TEXT_MATCH_THRESHOLD: float = 0.7

#: Min content-token length for the service-name text rule. Drops
#: function words and number fragments; matches Week 1 SG's setting.
_MIN_TOKEN_LEN: int = 3


# ---- tokenisation helper ---------------------------------------------------


def _content_tokens(text: str) -> frozenset[str]:
    """Case-fold + punctuation-strip ``text`` via
    :func:`rapidfuzz.utils.default_process`, split on whitespace,
    drop tokens shorter than :data:`_MIN_TOKEN_LEN`.

    Mirrors the helper of the same name in
    :mod:`evaluation.metrics.ontology_adapter` so EC's service-name
    matcher and SG's label matcher tokenise identically.
    """
    processed = utils.default_process(text)
    if not processed:
        return frozenset()
    return frozenset(t for t in processed.split() if len(t) >= _MIN_TOKEN_LEN)


def _text_matches_any_label(
    text: str,
    candidate_uris: set[str],
    ontology: OntologyAdapter,
    threshold: float = _TEXT_MATCH_THRESHOLD,
) -> bool:
    """Return True when ``text``'s content tokens cover ≥ ``threshold``
    of any candidate label's content tokens.

    This is the EC-specific complement of
    :meth:`OntologyAdapter.find_class_by_label`. The adapter's helper
    returns the **best** match URI across all labels in the fuzzy
    pool; EC wants a different question: "is there ANY label in
    this category that the text covers?". Asking only about a URI
    subset (e.g. fault prototypes) avoids the case where a more-
    specific label (``"Root Cause"``) outscores the category label
    (``"CPU Saturation"``) on a text that contains both, even when
    the category-specific label IS a valid match.
    """
    atom_tokens = _content_tokens(text)
    if not atom_tokens:
        return False
    labels = ontology.list_labels()
    for uri in candidate_uris:
        label = labels.get(uri)
        if not label:
            continue
        label_tokens = _content_tokens(label)
        if not label_tokens:
            continue
        coverage = len(atom_tokens & label_tokens) / len(label_tokens)
        if coverage >= threshold:
            return True
    return False


# ---- per-category detectors ------------------------------------------------


def _detect_root_cause_category(
    explanation: CanonicalExplanation,
    ontology: OntologyAdapter,
) -> tuple[bool, list[str]]:
    """Return ``(matched, contributing_atom_ids)``.

    Matches if any atom in the explanation carries a fault-prototype
    URI as its ``ontology_class``, OR if its text token-covers any
    Fault prototype label at the configured threshold.
    """
    fault_protos = ontology.list_fault_prototypes()
    matched: list[str] = []
    for atom in explanation.atoms():
        if atom.ontology_class is not None and atom.ontology_class in fault_protos:
            matched.append(atom.id)
            continue
        if _text_matches_any_label(atom.text, fault_protos, ontology):
            matched.append(atom.id)
    return (bool(matched), matched)


def _detect_affected_component_category(
    explanation: CanonicalExplanation,
    ontology: OntologyAdapter,
    case_services: Sequence[str],
) -> tuple[bool, list[str]]:
    """Return ``(matched, contributing_atom_ids)``.

    Matches if any atom carries a MicroService-category URI as its
    ``ontology_class``, OR if its text contains any service name
    from ``case_services`` as a whole content token (case-folded,
    min-length-3, same tokenisation as SG).
    """
    microservices = ontology.list_microservices()
    service_tokens = {
        tok
        for svc in case_services
        for tok in _content_tokens(svc)
    }
    matched: list[str] = []
    for atom in explanation.atoms():
        if atom.ontology_class is not None and atom.ontology_class in microservices:
            matched.append(atom.id)
            continue
        if service_tokens and (_content_tokens(atom.text) & service_tokens):
            matched.append(atom.id)
    return (bool(matched), matched)


def _detect_mitigation_category(
    explanation: CanonicalExplanation,
    ontology: OntologyAdapter,
) -> tuple[bool, list[str]]:
    """Return ``(matched, contributing_atom_ids)``.

    Matches if any atom carries a Recommendation-category URI as its
    ``ontology_class``, OR if its text token-covers any Recommendation
    label at the configured threshold.
    """
    recommendations = ontology.list_recommendations()
    matched: list[str] = []
    for atom in explanation.atoms():
        if atom.ontology_class is not None and atom.ontology_class in recommendations:
            matched.append(atom.id)
            continue
        if _text_matches_any_label(atom.text, recommendations, ontology):
            matched.append(atom.id)
    return (bool(matched), matched)


# ---- public metric ---------------------------------------------------------


class ExplanationCompleteness(SemanticMetric):
    """Mean of three binary category detectors: does the
    explanation answer *what fault*, *which service*, and *what
    mitigation*?

    The metric extends :class:`SemanticMetric`'s contract with one
    optional argument — ``case_services`` — needed only by the
    affected-component text-level detector. Passing an empty
    sequence (the default) disables the service-name text rule;
    the ontology-side MicroService URI check still runs.
    """

    name = "explanation_completeness"

    def __init__(self) -> None:
        pass

    # ---- public API ----

    def score(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
        case_services: Sequence[str] = (),
    ) -> float:
        if not list(explanation.atoms()):
            return 0.0
        has_cause, _ = _detect_root_cause_category(explanation, ontology)
        has_component, _ = _detect_affected_component_category(
            explanation, ontology, case_services,
        )
        has_mitigation, _ = _detect_mitigation_category(explanation, ontology)
        return float(has_cause + has_component + has_mitigation) / 3.0

    def score_with_breakdown(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
        case_services: Sequence[str] = (),
    ) -> dict[str, Any]:
        """Return overall + per-category flags + per-category
        contributing-atom IDs.

        ``categories_present`` is the human-readable list of the
        three category names that matched (subset of
        ``["cause", "component", "mitigation"]``).
        """
        atoms = list(explanation.atoms())
        if not atoms:
            return {
                "overall": 0.0,
                "categories_present": [],
                "has_cause": False,
                "has_component": False,
                "has_mitigation": False,
                "detection_details": {
                    "cause_atoms": [],
                    "component_atoms": [],
                    "mitigation_atoms": [],
                },
            }

        has_cause, cause_atoms = _detect_root_cause_category(
            explanation, ontology,
        )
        has_component, component_atoms = _detect_affected_component_category(
            explanation, ontology, case_services,
        )
        has_mitigation, mitigation_atoms = _detect_mitigation_category(
            explanation, ontology,
        )

        present: list[str] = []
        if has_cause:
            present.append("cause")
        if has_component:
            present.append("component")
        if has_mitigation:
            present.append("mitigation")

        return {
            "overall": float(has_cause + has_component + has_mitigation) / 3.0,
            "categories_present": present,
            "has_cause": bool(has_cause),
            "has_component": bool(has_component),
            "has_mitigation": bool(has_mitigation),
            "detection_details": {
                "cause_atoms": cause_atoms,
                "component_atoms": component_atoms,
                "mitigation_atoms": mitigation_atoms,
            },
        }
