"""Core dataclasses describing benchmark cases, method outputs, and the
canonical explanation graph used to compare methods on a level field.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Iterator

import networkx as nx


@dataclass
class ExplanationAtom:
    """A single node in a canonical explanation graph.

    `text` is the human-readable claim. `ontology_class` is an optional URI
    pointing into the FODA ontology (or another OWL ontology), and lets
    metrics ask whether two atoms refer to the same concept across methods.
    `fuzzy_membership` is the degree to which this atom holds, when the
    producing method is fuzzy.
    """

    text: str
    ontology_class: str | None = None
    fuzzy_membership: float | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self) -> None:
        if self.fuzzy_membership is not None and not (
            0.0 <= self.fuzzy_membership <= 1.0
        ):
            raise ValueError(
                f"fuzzy_membership must be in [0, 1], got {self.fuzzy_membership}"
            )


@dataclass
class CausalLink:
    """A directed edge between two atoms.

    `weight` is the strength of the causal claim in [0, 1] when available;
    `relation_type` is a free-form label (e.g. "causes", "precedes",
    "manifestsAs") that downstream metrics may interpret.
    """

    source_atom_id: str
    target_atom_id: str
    weight: float | None = None
    relation_type: str | None = None

    def __post_init__(self) -> None:
        if self.weight is not None and not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be in [0, 1], got {self.weight}")


class CanonicalExplanation:
    """A directed graph of `ExplanationAtom`s connected by `CausalLink`s.

    Backed by `networkx.DiGraph`. The graph is allowed to have cycles;
    metrics that need a DAG should check or topologically sort themselves.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._atoms: dict[str, ExplanationAtom] = {}

    def add_atom(self, atom: ExplanationAtom) -> str:
        if atom.id in self._atoms:
            raise ValueError(f"atom id {atom.id!r} already in graph")
        self._atoms[atom.id] = atom
        self._graph.add_node(atom.id)
        return atom.id

    def add_link(self, link: CausalLink) -> None:
        if link.source_atom_id not in self._atoms:
            raise KeyError(f"unknown source atom {link.source_atom_id!r}")
        if link.target_atom_id not in self._atoms:
            raise KeyError(f"unknown target atom {link.target_atom_id!r}")
        self._graph.add_edge(
            link.source_atom_id,
            link.target_atom_id,
            weight=link.weight,
            relation_type=link.relation_type,
        )

    def get_atom(self, atom_id: str) -> ExplanationAtom:
        return self._atoms[atom_id]

    def atoms(self) -> Iterator[ExplanationAtom]:
        return iter(self._atoms.values())

    def links(self) -> Iterator[CausalLink]:
        for src, dst, data in self._graph.edges(data=True):
            yield CausalLink(
                source_atom_id=src,
                target_atom_id=dst,
                weight=data.get("weight"),
                relation_type=data.get("relation_type"),
            )

    def roots(self) -> list[ExplanationAtom]:
        return [
            self._atoms[n]
            for n in self._graph.nodes
            if self._graph.in_degree(n) == 0
        ]

    def leaves(self) -> list[ExplanationAtom]:
        return [
            self._atoms[n]
            for n in self._graph.nodes
            if self._graph.out_degree(n) == 0
        ]

    @property
    def graph(self) -> nx.DiGraph:
        return self._graph

    def __len__(self) -> int:
        return len(self._atoms)

    def __contains__(self, atom_id: object) -> bool:
        return atom_id in self._atoms


@dataclass
class BenchmarkCase:
    """One labeled fault scenario from a benchmark.

    `telemetry` is method-agnostic raw input (typically a pandas DataFrame
    of metrics, or a dict of {modality: data}). `system_topology` is the
    service graph (e.g. a `networkx.DiGraph`). `ontology_mapping` is an
    optional mapping from telemetry symbols to ontology URIs that
    semantic-aware methods can consume.
    """

    id: str
    telemetry: Any
    ground_truth_root_cause: str
    ground_truth_fault_type: str
    system_topology: Any
    ontology_mapping: Any | None = None


@dataclass
class DiagnosticOutput:
    """The output of a single RCA method on a single case.

    ``peak_confidence`` is an optional **secondary** confidence summary
    intended for cross-method calibration analysis. It is currently set
    only by BARO, whose primary ``confidence`` is the BOCPD marginal
    posterior — a value mathematically bounded by ~1/T under BOCPD's
    hazard prior and therefore not directly comparable to head-ratio
    or softmax confidences emitted by the other methods. BARO's
    ``peak_confidence`` is the band-normalised peak of the same
    posterior — "probability mass at the peak moment, given the
    change point is in the search band" — which lies in [0, 1] and is
    directly comparable to other methods' confidences. See
    DEVIATIONS.md → "ConfidenceCalibration metric" for the routing
    rule the Phase 2 Week 4 harness applies.
    """

    ranked_list: list[tuple[str, float]]
    explanation_chain: CanonicalExplanation
    confidence: float | None
    raw_output: Any
    method_name: str
    wall_time_ms: float
    peak_confidence: float | None = None

    def __post_init__(self) -> None:
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0, 1] or None, got {self.confidence}"
            )
        if self.peak_confidence is not None and not (
            0.0 <= self.peak_confidence <= 1.0
        ):
            raise ValueError(
                f"peak_confidence must be in [0, 1] or None, "
                f"got {self.peak_confidence}"
            )
