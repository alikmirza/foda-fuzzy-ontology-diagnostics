"""Lightweight adapter wrapping the DiagnosticKB.owl ontology for
semantic-quality metrics.

Loads the OWL file once at construction via :mod:`owlready2`, materialises
URI ⇄ label tables, and exposes three lookup primitives that Paper 6's
semantic-quality metrics share:

* :meth:`has_class` — does this URI resolve to a known entity in the
  ontology? "Class" is used loosely: DiagnosticKB declares its fault
  prototypes (``CpuSaturation``, ``MemoryLeak``, …) as
  :class:`owl:NamedIndividual` instances of the ``Fault`` class, not as
  OWL classes themselves. The semantic-quality metrics treat both
  ``owl:Class`` and ``owl:NamedIndividual`` URIs as "known entities" —
  the question SG cares about is "is this URI defined by the ontology
  the method claims to be grounding into?", and an atom tagged with
  ``#CpuSaturation`` (an individual) is semantically grounded in
  exactly the way the metric wants to reward.

* :meth:`list_classes` — return ALL known URIs (classes + individuals).
  The name follows the brief's contract; the docstring documents the
  broader semantics.

* :meth:`find_class_by_label` — fuzzy match a free-text snippet against
  every label declared in the ontology (both class ``rdfs:label`` and
  individual ``rdfs:label``). The match uses
  :func:`rapidfuzz.process.extractOne` with a configurable threshold
  (default 0.7 on a 0–1 scale; ``rapidfuzz`` scores in 0–100 so we
  normalise).

The adapter is intentionally minimal: SG and the three sibling metrics
hit only these primitives. Keeping the interface narrow makes the
metrics easy to mock for unit tests, and keeps the ontology library
swap-out cost low if we later migrate from owlready2 to RDFLib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import owlready2
from rapidfuzz import utils


DEFAULT_ONTOLOGY_PATH: Path = (
    Path(__file__).resolve().parents[2] / "ontology" / "DiagnosticKB.owl"
)

#: Conversion factor between the internal 0–100 score and the 0–1
#: scale the public API uses.
_SCORE_SCALE: float = 100.0

#: Tokens shorter than this length are dropped before computing
#: label-vs-atom coverage. Filters out function words ("a", "is",
#: "of") and short symbols that survive ``utils.default_process``
#: (number fragments, single letters). Three characters is the
#: smallest length where a domain term like ``"cpu"`` is meaningful.
_MIN_TOKEN_LEN: int = 3

#: Local names of abstract OWL classes excluded from the fuzzy-match
#: pool by default. These classes name generic concepts ("Anomaly",
#: "Severity", "Metric") that match almost any anomaly explanation
#: text by substring partial-ratio — a method whose atom text says
#: "service X is anomalous" would fuzzy-match every atom against
#: ``Anomaly``, giving an artificially high SemanticGroundedness
#: score. We retain the semantic-concept classes (``RootCause``,
#: ``ContributingFactor``, ``Recommendation``) and every individual
#: (specific fault prototypes, recommendations, contributing factors,
#: severities) because matching against THOSE labels reflects real
#: semantic grounding rather than coincidental word overlap.
#:
#: This is a tunable knob: callers can override via the
#: ``fuzzy_class_blacklist`` constructor argument.
_DEFAULT_FUZZY_CLASS_BLACKLIST: frozenset[str] = frozenset({
    "Fault",
    "Anomaly",
    "Severity",
    "Metric",
    "MicroService",
    "DiagnosticResult",
    "MLModel",
    "Symptom",
})


def _content_tokens(text: str) -> frozenset[str]:
    """Tokenise ``text`` via :func:`utils.default_process` (case-fold +
    punctuation strip), split on whitespace, and drop tokens shorter
    than :data:`_MIN_TOKEN_LEN`.

    Module-private helper shared by every label-matching path so the
    same tokenisation rules apply on both sides of the overlap
    comparison (atom text and label).
    """
    processed = utils.default_process(text)
    if not processed:
        return frozenset()
    return frozenset(t for t in processed.split() if len(t) >= _MIN_TOKEN_LEN)


@dataclass
class OntologyAdapter:
    """Read-only handle on DiagnosticKB.owl.

    Construct once and pass to every metric — there is no per-call I/O.

    Parameters
    ----------
    ontology_path:
        Path to a local OWL file. Defaults to ``ontology/DiagnosticKB.owl``
        relative to the repository root, matching the file
        :class:`OntologyGroundedExplanationBuilder` reads on the Java
        side and the file ``foda_fcp.py`` tags atoms against.
    """

    ontology_path: Path = field(default_factory=lambda: DEFAULT_ONTOLOGY_PATH)
    #: Local names (e.g. ``"Anomaly"``) of OWL classes to exclude from
    #: the fuzzy-match label pool. Default suppresses abstract
    #: metaclasses that match too generically; pass an empty set to
    #: search every label. Does NOT affect :meth:`has_class` — direct
    #: URI lookups still resolve these classes.
    fuzzy_class_blacklist: frozenset[str] = field(
        default_factory=lambda: _DEFAULT_FUZZY_CLASS_BLACKLIST
    )

    # Populated by __post_init__.
    _uris: frozenset[str] = field(init=False, repr=False)
    _classes: frozenset[str] = field(init=False, repr=False)
    _labels: dict[str, str] = field(init=False, repr=False)
    _fuzzy_labels: dict[str, str] = field(init=False, repr=False)
    _base_iri: str = field(init=False, repr=False)
    #: ``(source_uri, target_uri) → strength`` materialised from every
    #: :class:`Propagation` individual. Missing keys → strength 0.0
    #: per the ontology's "only explicit propagations are typical"
    #: convention.
    _propagations: dict[tuple[str, str], float] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        path = Path(self.ontology_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(
                f"OntologyAdapter: file not found at {path!s}"
            )
        # owlready2 expects a file:// URI; load() returns the parsed
        # ontology bound to its declared base IRI.
        onto = owlready2.get_ontology(f"file://{path}").load()
        self._base_iri = onto.base_iri

        classes = {c.iri for c in onto.classes()}
        individuals = {i.iri for i in onto.individuals()}
        self._classes = frozenset(classes)
        self._uris = frozenset(classes | individuals)

        labels: dict[str, str] = {}
        for entity in list(onto.classes()) + list(onto.individuals()):
            # owlready2 makes ``label`` a multi-valued FuncProp; pick the
            # first non-empty string label, falling back to the local
            # name. Local names are the form ``CpuSaturation`` — they're
            # human-readable enough to serve as a label of last resort.
            label_values = list(entity.label) if entity.label else []
            label_values = [str(v) for v in label_values if str(v).strip()]
            if label_values:
                labels[entity.iri] = label_values[0]
            else:
                # owlready2 exposes ``name`` (the local name) on every
                # entity regardless of label presence.
                labels[entity.iri] = entity.name
        self._labels = labels

        # Fuzzy-search pool excludes the configured blacklist of abstract
        # class local names. Resolves blacklist entries to their full URI
        # so :meth:`find_class_by_label` doesn't need to re-derive them.
        blacklisted_uris = {
            f"{self._base_iri}{local_name}"
            for local_name in self.fuzzy_class_blacklist
        }
        self._fuzzy_labels = {
            uri: label for uri, label in labels.items()
            if uri not in blacklisted_uris
        }

        # Propagation patterns: walk every individual that's an instance
        # of the Propagation class and read its (source, target, strength)
        # via the three propagation properties defined in DiagnosticKB.
        # Stored as ``{(source_uri, target_uri): strength}`` for O(1)
        # lookup in :meth:`get_propagation_strength`. Ordered pairs not
        # present in the dict have implicit strength 0.0.
        propagations: dict[tuple[str, str], float] = {}
        prop_class = onto.search_one(iri=f"{self._base_iri}Propagation")
        if prop_class is not None:
            for inst in onto.search(type=prop_class):
                src = list(getattr(inst, "propagationSource", []) or [])
                tgt = list(getattr(inst, "propagationTarget", []) or [])
                strength = list(getattr(inst, "propagationStrength", []) or [])
                if not src or not tgt or not strength:
                    continue
                propagations[(src[0].iri, tgt[0].iri)] = float(strength[0])
        self._propagations = propagations

    # ---- public API ----

    def has_class(self, uri: str) -> bool:
        """Return whether ``uri`` is a known entity (class OR individual)
        in the ontology.

        The brief's contract calls this method ``has_class``; in the
        DiagnosticKB.owl design, fault prototypes are declared as
        ``NamedIndividual`` instances of the ``Fault`` class rather
        than as OWL classes. We deliberately accept both so an atom
        tagged with ``#CpuSaturation`` (an individual) is recognised
        as grounded, matching the metric's intent.
        """
        return uri in self._uris

    def is_strict_class(self, uri: str) -> bool:
        """Return ``True`` only when ``uri`` is a declared ``owl:Class``.

        Provided for callers (e.g. SemanticCoherence) that need the
        strict class-vs-individual distinction. SG does not use it.
        """
        return uri in self._classes

    def list_classes(self) -> list[str]:
        """Return every known entity URI (classes ∪ individuals),
        sorted for determinism.

        Misnomer for backwards compatibility with the brief's contract.
        Use :meth:`list_strict_classes` when you genuinely need only
        ``owl:Class`` URIs.
        """
        return sorted(self._uris)

    def list_strict_classes(self) -> list[str]:
        """Return only ``owl:Class`` URIs, sorted."""
        return sorted(self._classes)

    def list_labels(self) -> dict[str, str]:
        """Return a copy of the URI → label map.

        Every known entity has exactly one entry; entities without an
        ``rdfs:label`` annotation get their local name as the label
        (e.g. ``Symptom`` for ``http://…/diagnostic#Symptom`` when no
        explicit label is declared).
        """
        return dict(self._labels)

    def find_class_by_label(
        self,
        text: str,
        threshold: float = 0.7,
    ) -> str | None:
        """Token-aligned fuzzy match: return the entity URI whose label
        has the highest fraction of content tokens appearing as whole
        tokens in ``text``, or ``None`` if no label clears
        ``threshold``.

        Tokenisation: ``text`` and every candidate label are passed
        through :func:`utils.default_process` (case-folded,
        punctuation/diacritic-stripped) and split on whitespace.
        Tokens shorter than :data:`_MIN_TOKEN_LEN` characters are
        dropped from both the atom and the label to avoid spurious
        overlap on function words ("is", "of"), single letters, and
        number fragments produced by punctuation stripping
        (``"α=0.435"`` → ``["0", "435"]``).

        Coverage rule::

            content_overlap = label_content_tokens ∩ atom_content_tokens
            coverage = |content_overlap| / |label_content_tokens|
            match succeeds when coverage * 100 >= threshold * 100

        This is the **upgrade from partial-ratio character matching**
        that suppressed three classes of false positive on RE1-OB:

        * Character-substring artifacts. ``"from cartservice"`` no
          longer partial-matches the label ``"root cause"`` (no
          whole-token overlap), so DejaVu attention-attribution atoms
          stop spuriously scoring against ``#RootCause``.
        * Morphological stem mismatch. ``"anomalous"`` no longer
          matches ``"anomaly"`` (the two are different whole tokens);
          the abstract-class blacklist (still in force as a defence
          in depth) and the strict tokenisation jointly suppress this.
        * Embedded-substring matches against generic short labels
          (``"Metric"``, ``"Fault"``). Coverage is now computed
          against label content, so a single-word label needs that
          exact word to appear whole.

        The yRCA legitimate match ``"final_root_cause"`` ⇒
        ``RootCause`` still fires: ``default_process`` rewrites the
        underscore to a space, producing the tokens ``"root"`` and
        ``"cause"`` which whole-match the label.

        Ties between labels with equal coverage are broken by label
        length (shorter labels first — they're typically more
        specific) and then by URI for determinism.

        Queries shorter than :data:`_MIN_TOKEN_LEN` characters (after
        stripping) return ``None`` unconditionally because no label
        can score above zero against an empty content-token set.
        """
        if not text or not text.strip():
            return None
        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                f"threshold must be in [0, 1], got {threshold}"
            )
        if not self._fuzzy_labels:
            return None
        stripped = text.strip()
        if len(stripped) < _MIN_TOKEN_LEN:
            return None

        atom_content = _content_tokens(stripped)
        if not atom_content:
            return None

        threshold_pct = threshold * _SCORE_SCALE
        best_score = -1.0
        best_uri: str | None = None
        best_label_len = 0
        for uri, label in self._fuzzy_labels.items():
            label_content = _content_tokens(label)
            if not label_content:
                continue
            overlap = atom_content & label_content
            coverage = len(overlap) / len(label_content)
            score = coverage * _SCORE_SCALE
            if score < threshold_pct:
                continue
            # Tiebreaker: prefer shorter label (more specific), then
            # lexically smaller URI for full determinism.
            label_len = len(label)
            if score > best_score or (
                score == best_score and (
                    label_len < best_label_len
                    or (label_len == best_label_len and (best_uri is None or uri < best_uri))
                )
            ):
                best_score = score
                best_uri = uri
                best_label_len = label_len
        return best_uri

    # ---- propagation lookups (Phase 2 Week 2 — SemanticCoherence) ----

    def get_propagation_strength(
        self, source_class: str, target_class: str,
    ) -> float:
        """Typical propagation strength of ``source_class →
        target_class``.

        Returns the strength encoded on the matching
        :class:`Propagation` individual in DiagnosticKB
        (``1.0`` = typical, ``0.5`` = conditional). Returns ``0.0``
        when no Propagation individual reifies that ordered pair —
        the ontology's convention is "only explicit propagations are
        typical; everything else is atypical".

        Direction matters: ``CpuSaturation → LatencySpike`` is a
        typical propagation (strength 1.0); the reverse
        ``LatencySpike → CpuSaturation`` has no Propagation
        individual and returns 0.0. Self-loops (e.g.
        ``CpuSaturation → CpuSaturation``) are not declared and
        likewise return 0.0.
        """
        return self._propagations.get((source_class, target_class), 0.0)

    def list_propagations(self) -> list[tuple[str, str, float]]:
        """Every declared Propagation as a
        ``(source_uri, target_uri, strength)`` tuple, sorted by
        source then target for determinism."""
        return sorted(
            (src, tgt, strength)
            for (src, tgt), strength in self._propagations.items()
        )

    # ---- introspection helpers ----

    @property
    def base_iri(self) -> str:
        """The ontology's declared base IRI
        (``http://foda.com/ontology/diagnostic#``)."""
        return self._base_iri

    def __len__(self) -> int:
        """Number of known entities (classes + individuals)."""
        return len(self._uris)
