"""SemanticCoherence — direction-and-typicality scoring of an
explanation's causal links against the fault-propagation patterns
encoded in DiagnosticKB.

Where SemanticGroundedness scores ATOMS (do the nodes in the
explanation graph reference real ontology entities?),
SemanticCoherence scores LINKS (do the edges in the explanation graph
respect known fault-propagation directions?). The two metrics measure
orthogonal properties of the same :class:`CanonicalExplanation`.

Variant 4 design (current)
--------------------------

The metric scores each link by **direction agreement with the
ontology's Propagation table, scaled by typicality**. Concretely:

* **propagation-claim** links (``relation_type`` in
  :data:`PROPAGATION_RELATIONS`) are scored:

  - **coherent** when both endpoints are fault prototypes and the
    ``(source_class, target_class)`` pair (after back-flow direction
    swap, if applicable) appears in the ontology's Propagation table.
    The subscore is the ontology's declared strength
    ``ω ∈ {0.5, 1.0}`` — variant 4's signature: a typical
    propagation (1.0) scores higher than a conditional one (0.5),
    and the link's own ``weight`` is *not* used to penalise the
    score. The link weight was the bug in v2: FCP's Noisy-OR-
    attenuated contribution magnitudes (mean ≈ 0.05) are not
    commensurable with ontology typicalities (≈ 0.79), and
    ``1 − |ω − w|`` punished direction-correct claims for failing
    to match a number they were never measuring. See findings.md
    §"Phase 2 Week 2 v3" for the diagnostic that motivated the
    switch.

  - **incoherent** when both endpoints are fault prototypes but
    the ontology has no Propagation individual for the pair. The
    method is making an atypical-propagation claim; subscore 0.0.

  - **unmapped** when either endpoint is not a fault prototype
    (Recommendation individual, abstract ContributingFactor class,
    foreign-namespace URI like ``yrca:Role/*``, or missing
    ``ontology_class``). SC has no opinion about such links;
    subscore 0.0 but accounted separately from incoherent.

* **mitigation-claim** links (``relation_type`` containing
  ``"mitigation"``, ``"recommend"``, or ``"suggests"``) are
  **excluded from SC entirely**: subscore 0.0, ``match_type =
  "excluded_mitigation"``, and they do *not* count in the
  denominator. The methodological rationale: mitigation links
  encode "given this fault, what should an operator do?", which
  is a different question from "do these faults typically
  propagate?". Including them in SC's denominator would punish
  methods that surface mitigation suggestions for structurally
  not being propagation claims — the wrong kind of incentive.

* **non-propagation, non-mitigation** links (relation_type ``None``,
  ``"anomaly-correlates-with"``, ``"rule_derived_explanation"``,
  …) are classified ``unmapped``: not a propagation claim, not a
  mitigation, no opinion.

Back-flow relation handling
---------------------------

Within :data:`PROPAGATION_RELATIONS`, three shapes flow in the
**back-flow / evidence direction** ``effect → cause``:
``contributes_to`` (FCP's Noisy-OR shape), ``explained_by``
(yRCA's rule-head shape), and ``caused_by`` (a generic
back-pointer). The remaining three (``causes``, ``propagates_to``,
``leads_to``) flow in the forward ``cause → effect`` direction.
SC swaps ``(source_class, target_class)`` before looking the
propagation up so the table — which is forward-direction —
returns the right strength regardless of which convention the
adapter emits.

Overall scoring
---------------

The overall score is the **mean of per-link subscores over links
that are NOT excluded as mitigation**. An explanation with no
non-mitigation links returns ``0.0``. Method adapters that emit
only atoms with no edges (e.g. MonitorRank in its current form)
score 0.0 by construction.

Configurable knobs
------------------

:data:`PROPAGATION_RELATIONS` — the relation-type prefixes that
count as propagation claims. Adapters can extend this if they
emit a custom propagation shape (e.g. ``"derived_from"``).

:data:`_BACK_FLOW_RELATIONS` — the subset of propagation
relations whose direction is reversed before the Propagation
lookup.

:data:`_MITIGATION_TOKENS` — substrings whose presence in a
relation_type marks the link as mitigation-excluded.

The propagation strengths live in the ontology, not in this
module; see :class:`OntologyAdapter` for the table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..extraction.canonical_explanation import (
    CanonicalExplanation,
    CausalLink,
    ExplanationAtom,
)
from .base import SemanticMetric
from .ontology_adapter import OntologyAdapter


#: Relation-type prefixes that mark a link as a **propagation claim**
#: (the kind SC is designed to score). Adapters that emit a custom
#: propagation shape (e.g. ``"derived_from"``, ``"observed_under"``)
#: should add their prefix here to bring those links in-scope.
#:
#: * ``contributes_to`` — FCP's Noisy-OR back-flow.
#: * ``explained_by`` — yRCA's rule-head shape (back-flow).
#: * ``caused_by`` — generic back-pointer.
#: * ``causes`` — generic forward.
#: * ``propagates_to`` — generic forward, common in rule-based RCA.
#: * ``leads_to`` — generic forward (alternative naming).
PROPAGATION_RELATIONS: frozenset[str] = frozenset({
    "contributes_to",
    "explained_by",
    "caused_by",
    "causes",
    "propagates_to",
    "leads_to",
})


#: Subset of :data:`PROPAGATION_RELATIONS` whose direction is reversed
#: before the ontology lookup. Back-flow relations flow
#: ``effect → cause``; the Propagation table is forward
#: (``cause → effect``); so SC swaps the pair to recover the right
#: lookup key.
_BACK_FLOW_RELATIONS: frozenset[str] = frozenset({
    "contributes_to",
    "explained_by",
    "caused_by",
})


#: Substrings whose presence in a ``relation_type`` marks the link as a
#: **mitigation claim**. Mitigation links are excluded from SC's
#: denominator entirely — they're a different question from propagation
#: typicality. FCP's ``suggests_mitigation:recommendation:fault_prototype``
#: matches all three tokens.
_MITIGATION_TOKENS: frozenset[str] = frozenset({
    "mitigation",
    "recommend",
    "suggests",
})


# ---- per-link scoring ------------------------------------------------------


@dataclass(frozen=True)
class _LinkScore:
    """Per-link subscore + diagnostic info."""

    subscore: float
    #: ``"coherent" | "incoherent" | "unmapped" | "excluded_mitigation"``.
    #: Mitigation links are excluded from SC's denominator; the other
    #: three count toward the mean.
    match_type: str
    ontology_strength: float | None
    link_weight: float | None


def _fault_prototype_uris(ontology: OntologyAdapter) -> frozenset[str]:
    """URIs that participate in **at least one** Propagation individual
    as source or target. These are the ontology's fault prototypes
    (``CpuSaturation``, ``MemoryLeak``, …) — the classes the
    Propagation table has an opinion about.

    Memoised on the adapter so repeated metric calls don't rescan the
    propagation table. The set is small (≈8 entries on
    DiagnosticKB.owl), so the cache cost is negligible.
    """
    cached = getattr(ontology, "_fault_prototype_uris_cache", None)
    if cached is not None:
        return cached
    uris: set[str] = set()
    for src, tgt, _strength in ontology.list_propagations():
        uris.add(src)
        uris.add(tgt)
    cache = frozenset(uris)
    ontology._fault_prototype_uris_cache = cache  # type: ignore[attr-defined]
    return cache


def _matches_prefix(relation_type: str | None, prefixes: frozenset[str]) -> bool:
    """Return True when ``relation_type`` starts with one of the
    prefixes in ``prefixes``. Used to test both
    :data:`PROPAGATION_RELATIONS` and :data:`_BACK_FLOW_RELATIONS`
    against ``relation_type`` values that carry suffixes like
    ``"contributes_to:propagation:noisy_or"``."""
    if not relation_type:
        return False
    return any(relation_type.startswith(p) for p in prefixes)


def _is_propagation(relation_type: str | None) -> bool:
    return _matches_prefix(relation_type, PROPAGATION_RELATIONS)


def _is_back_flow(relation_type: str | None) -> bool:
    """Return True when the propagation direction is
    ``effect → cause`` and SC should swap the endpoints before the
    ontology lookup."""
    return _matches_prefix(relation_type, _BACK_FLOW_RELATIONS)


def _is_mitigation(relation_type: str | None) -> bool:
    """Return True when ``relation_type`` contains any of
    :data:`_MITIGATION_TOKENS` as a substring. Mitigation links are
    excluded from SC's denominator."""
    if not relation_type:
        return False
    return any(tok in relation_type for tok in _MITIGATION_TOKENS)


def _score_link(
    link: CausalLink,
    source: ExplanationAtom,
    target: ExplanationAtom,
    ontology: OntologyAdapter,
) -> _LinkScore:
    """Score a single causal link per the variant-4 rule documented in
    the module docstring."""
    # Mitigation: excluded entirely.
    if _is_mitigation(link.relation_type):
        return _LinkScore(
            subscore=0.0,
            match_type="excluded_mitigation",
            ontology_strength=None,
            link_weight=link.weight,
        )

    # Anything that isn't a propagation claim is out of SC's scope.
    if not _is_propagation(link.relation_type):
        return _LinkScore(
            subscore=0.0,
            match_type="unmapped",
            ontology_strength=None,
            link_weight=link.weight,
        )

    src_class = source.ontology_class
    tgt_class = target.ontology_class

    # An endpoint with no ontology class, with a URI that doesn't
    # resolve, or whose class isn't a fault prototype, is unmapped:
    # SC has no opinion on it.
    fault_prototypes = _fault_prototype_uris(ontology)
    if (
        src_class is None
        or tgt_class is None
        or not ontology.has_class(src_class)
        or not ontology.has_class(tgt_class)
        or src_class not in fault_prototypes
        or tgt_class not in fault_prototypes
    ):
        return _LinkScore(
            subscore=0.0,
            match_type="unmapped",
            ontology_strength=None,
            link_weight=link.weight,
        )

    # Back-flow shapes emit edges effect→cause. The Propagation table
    # is forward-direction (cause→effect); swap before lookup. Forward
    # shapes pass through unchanged.
    if _is_back_flow(link.relation_type):
        lookup_src, lookup_tgt = tgt_class, src_class
    else:
        lookup_src, lookup_tgt = src_class, tgt_class

    ontology_strength = ontology.get_propagation_strength(lookup_src, lookup_tgt)
    if ontology_strength == 0.0:
        # Both endpoints are fault prototypes but the ontology has no
        # Propagation for this pair — atypical-propagation claim.
        return _LinkScore(
            subscore=0.0,
            match_type="incoherent",
            ontology_strength=0.0,
            link_weight=link.weight,
        )

    # Coherent: subscore is the ontology's typicality (1.0 for typical
    # propagations, 0.5 for conditional ones). Link weight is recorded
    # for downstream analysis but does NOT penalise the score — see
    # module docstring for the rationale.
    return _LinkScore(
        subscore=float(ontology_strength),
        match_type="coherent",
        ontology_strength=float(ontology_strength),
        link_weight=link.weight,
    )


def _counts_toward_denominator(match_type: str) -> bool:
    """Mitigation links are excluded from SC's denominator. Everything
    else (coherent / incoherent / unmapped) counts."""
    return match_type != "excluded_mitigation"


# ---- public metric ---------------------------------------------------------


class SemanticCoherence(SemanticMetric):
    """Mean per-link coherence against the ontology's propagation
    table, scored under variant 4 (typicality-only, mitigation-
    excluded).

    No constructor parameters: the coherence rule is fixed by the
    ontology (strengths are looked up by URI pair) and the
    propagation-relation set is a module-level constant. Subclass
    and override :data:`PROPAGATION_RELATIONS` on the subclass to
    extend the relation vocabulary; override :meth:`_score_link` to
    change the per-link rule.
    """

    name = "semantic_coherence"

    def __init__(self) -> None:
        pass

    # ---- public API ----

    def score(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
    ) -> float:
        atom_by_id = {atom.id: atom for atom in explanation.atoms()}
        total = 0.0
        n = 0
        for link in explanation.links():
            source = atom_by_id.get(link.source_atom_id)
            target = atom_by_id.get(link.target_atom_id)
            if source is None or target is None:
                continue
            s = _score_link(link, source, target, ontology)
            if not _counts_toward_denominator(s.match_type):
                continue
            total += s.subscore
            n += 1
        if n == 0:
            return 0.0
        return float(total / n)

    def score_with_breakdown(
        self,
        explanation: CanonicalExplanation,
        ontology: OntologyAdapter,
    ) -> dict[str, Any]:
        """Return ``score`` plus per-link subscores and match-type
        counts useful for the cross-method analysis in Paper 6 §4.

        Per-link entries are returned for every link including
        ``excluded_mitigation`` ones, so callers can inspect what was
        excluded. The overall score's denominator counts only
        non-mitigation links.
        """
        links = list(explanation.links())
        if not links:
            return {
                "overall": 0.0,
                "per_link": [],
                "link_count": 0,
                "coherent_links": 0,
                "incoherent_links": 0,
                "unmapped_links": 0,
                "excluded_mitigation_links": 0,
                "scored_link_count": 0,
            }

        atom_by_id = {atom.id: atom for atom in explanation.atoms()}
        per_link: list[dict[str, Any]] = []
        coherent = incoherent = unmapped = excluded = 0
        total = 0.0
        scored = 0
        for link in links:
            source = atom_by_id.get(link.source_atom_id)
            target = atom_by_id.get(link.target_atom_id)
            if source is None or target is None:
                per_link.append({
                    "source_atom_id": link.source_atom_id,
                    "target_atom_id": link.target_atom_id,
                    "subscore": 0.0,
                    "match_type": "unmapped",
                    "ontology_strength": None,
                    "link_weight": link.weight,
                })
                unmapped += 1
                scored += 1
                continue
            s = _score_link(link, source, target, ontology)
            per_link.append({
                "source_atom_id": link.source_atom_id,
                "target_atom_id": link.target_atom_id,
                "subscore": float(s.subscore),
                "match_type": s.match_type,
                "ontology_strength": s.ontology_strength,
                "link_weight": s.link_weight,
            })
            if s.match_type == "coherent":
                coherent += 1
                total += s.subscore
                scored += 1
            elif s.match_type == "incoherent":
                incoherent += 1
                scored += 1
            elif s.match_type == "excluded_mitigation":
                excluded += 1
            else:
                unmapped += 1
                scored += 1

        overall = float(total / scored) if scored > 0 else 0.0
        return {
            "overall": overall,
            "per_link": per_link,
            "link_count": len(links),
            "coherent_links": coherent,
            "incoherent_links": incoherent,
            "unmapped_links": unmapped,
            "excluded_mitigation_links": excluded,
            "scored_link_count": scored,
        }
