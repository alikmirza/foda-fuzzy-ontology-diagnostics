"""SemanticGroundedness — fraction of explanation atoms whose claims
are anchored in a target ontology.

This is the method-agnostic generalisation of the Tbilisi LNNS 2026
paper's per-explanation semantic-groundedness component (which was
introduced for FODA-FCP outputs as one limb of a four-component
composite — see
``fuzzy-rca-engine/src/main/java/com/foda/rca/evaluation/ExplanationQualityMetric.java``).
Phase 2's version operates on :class:`CanonicalExplanation` atoms
directly rather than on a rendered natural-language string, so the
same metric scores every method in the suite on level terms.

Per-atom scoring
----------------

Each :class:`ExplanationAtom` is scored independently:

* **Direct match** (default weight ``1.0``). The atom carries an
  ``ontology_class`` URI and that URI is known to the target
  ontology (class or individual). This is the case for FODA-FCP
  atoms tagged with ``http://foda.com/ontology/diagnostic#...`` URIs.
* **Fuzzy match** (default weight ``0.5``). The atom's
  ``ontology_class`` is missing or refers to a foreign namespace
  (e.g. yRCA's ``"yrca:Role/final_root_cause"``), but the atom's
  ``text`` field fuzzy-matches an ontology label above
  ``fuzzy_threshold`` via
  :meth:`OntologyAdapter.find_class_by_label`. The half-credit
  reflects "the atom plausibly maps to ontology but the method didn't
  make that mapping explicit".
* **Unmatched** (default weight ``0.0``). Neither pathway resolves.

Overall scoring
---------------

The overall score is the **mean** of per-atom scores. An explanation
with no atoms returns ``0.0`` (no evidence to score).

The weights and threshold are constructor parameters; the defaults
match the Phase 2 brief. The :meth:`score_with_breakdown` API returns
per-atom match types and the matched ontology URI (when any) so the
case-study figure and the cross-method tables in Paper 6 §4 can drill
down past the aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..extraction.canonical_explanation import (
    CanonicalExplanation,
    ExplanationAtom,
)
from .base import SemanticMetric
from .ontology_adapter import OntologyAdapter


# ---- per-atom scoring ------------------------------------------------------


@dataclass(frozen=True)
class _AtomScore:
    """Per-atom subscore + diagnostic info.

    ``match_type`` is one of ``"direct"`` / ``"fuzzy"`` / ``"none"`` —
    the breakdown's per-atom rows expose this so the case-study
    figure can colour atoms by match category.
    """

    subscore: float
    match_type: str  # "direct" | "fuzzy" | "none"
    matched_class: str | None


def _score_atom(
    atom: ExplanationAtom,
    ontology: OntologyAdapter,
    direct_weight: float,
    fuzzy_weight: float,
    fuzzy_threshold: float,
) -> _AtomScore:
    """Score a single atom per the three-way rule documented in the
    module docstring."""
    if atom.ontology_class is not None and ontology.has_class(atom.ontology_class):
        return _AtomScore(
            subscore=direct_weight,
            match_type="direct",
            matched_class=atom.ontology_class,
        )
    if atom.text:
        fuzzy_uri = ontology.find_class_by_label(atom.text, threshold=fuzzy_threshold)
        if fuzzy_uri is not None:
            return _AtomScore(
                subscore=fuzzy_weight,
                match_type="fuzzy",
                matched_class=fuzzy_uri,
            )
    return _AtomScore(subscore=0.0, match_type="none", matched_class=None)


# ---- public metric ---------------------------------------------------------


class SemanticGroundedness(SemanticMetric):
    """Mean per-atom groundedness against the target ontology.

    Parameters
    ----------
    direct_weight:
        Score awarded when an atom's ``ontology_class`` URI resolves
        directly to a known entity in the ontology. Default ``1.0``.
    fuzzy_weight:
        Score awarded when the atom's ``text`` fuzzy-matches an
        ontology label above ``fuzzy_threshold``. Default ``0.5``.
    fuzzy_threshold:
        Threshold passed to
        :meth:`OntologyAdapter.find_class_by_label` for the fuzzy
        fallback. Default ``0.7`` (on a 0–1 scale).
    """

    name = "semantic_groundedness"

    def __init__(
        self,
        direct_weight: float = 1.0,
        fuzzy_weight: float = 0.5,
        fuzzy_threshold: float = 0.7,
    ) -> None:
        if not 0.0 <= direct_weight <= 1.0:
            raise ValueError(
                f"direct_weight must be in [0, 1], got {direct_weight}"
            )
        if not 0.0 <= fuzzy_weight <= direct_weight:
            raise ValueError(
                f"fuzzy_weight must be in [0, direct_weight={direct_weight}], "
                f"got {fuzzy_weight}"
            )
        if not 0.0 <= fuzzy_threshold <= 1.0:
            raise ValueError(
                f"fuzzy_threshold must be in [0, 1], got {fuzzy_threshold}"
            )
        self.direct_weight = direct_weight
        self.fuzzy_weight = fuzzy_weight
        self.fuzzy_threshold = fuzzy_threshold

    # ---- public API ----

    def score(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
    ) -> float:
        atoms = list(explanation.atoms())
        if not atoms:
            return 0.0
        total = 0.0
        for atom in atoms:
            s = _score_atom(
                atom, ontology,
                self.direct_weight, self.fuzzy_weight, self.fuzzy_threshold,
            )
            total += s.subscore
        return float(total / len(atoms))

    def score_with_breakdown(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
    ) -> dict[str, Any]:
        """Return ``score`` plus per-atom subscores and match-type
        counts useful for the cross-method analysis in Paper 6 §4."""
        atoms = list(explanation.atoms())
        if not atoms:
            return {
                "overall": 0.0,
                "per_atom": [],
                "atom_count": 0,
                "direct_matches": 0,
                "fuzzy_matches": 0,
                "unmatched": 0,
            }

        per_atom: list[dict[str, Any]] = []
        direct = fuzzy = unmatched = 0
        total = 0.0
        for atom in atoms:
            s = _score_atom(
                atom, ontology,
                self.direct_weight, self.fuzzy_weight, self.fuzzy_threshold,
            )
            total += s.subscore
            per_atom.append({
                "atom_id": atom.id,
                "subscore": float(s.subscore),
                "match_type": s.match_type,
                "matched_class": s.matched_class,
            })
            if s.match_type == "direct":
                direct += 1
            elif s.match_type == "fuzzy":
                fuzzy += 1
            else:
                unmatched += 1

        return {
            "overall": float(total / len(atoms)),
            "per_atom": per_atom,
            "atom_count": len(atoms),
            "direct_matches": direct,
            "fuzzy_matches": fuzzy,
            "unmatched": unmatched,
        }
