"""Abstract base classes for ranking metrics and semantic-quality
metrics.

Two ABCs live here because the two metric families have different
inputs:

* :class:`Metric` reduces ``(case, output)`` to a numeric score and is
  the right shape for ranking metrics (AC@k, MRR, S(M)). The contract
  predates Paper 6 Phase 2.

* :class:`SemanticMetric` reduces ``(explanation, ontology)`` to a
  numeric score and is the shape Paper 6 Phase 2's four semantic-
  quality metrics (SemanticGroundedness, SemanticCoherence,
  ExplanationCompleteness, ConfidenceCalibration) share. The contract
  is method-agnostic — the metric never sees the original case or the
  method that produced the explanation, only the structured
  :class:`CanonicalExplanation` graph and the ontology it claims to
  ground into.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ..extraction.canonical_explanation import (
    BenchmarkCase,
    CanonicalExplanation,
    DiagnosticOutput,
)

if TYPE_CHECKING:
    from .ontology_adapter import OntologyAdapter


class Metric(ABC):
    """A metric reduces a (case, output) pair to a numeric score."""

    name: str = ""

    @abstractmethod
    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        ...


class SemanticMetric(ABC):
    """A method-agnostic semantic-quality metric that scores a
    :class:`CanonicalExplanation` against an ontology.

    All four Paper 6 Phase 2 metrics share this contract. The metric
    deliberately does NOT see the original case, the method name, the
    ground truth, or the method's confidence — its job is to measure
    a property of the explanation graph itself.

    Implementations should:

    * Return a scalar in ``[0.0, 1.0]`` from :meth:`score`.
    * Return a dict with at least an ``overall`` key and a per-atom
      breakdown from :meth:`score_with_breakdown`.
    * Treat empty explanations as ``0.0`` (no evidence to score).
    """

    name: str = ""

    @abstractmethod
    def score(
        self,
        explanation: CanonicalExplanation,
        ontology: "OntologyAdapter",
    ) -> float:
        """Return a scalar score in ``[0.0, 1.0]``."""

    @abstractmethod
    def score_with_breakdown(
        self,
        explanation: CanonicalExplanation,
        ontology: "OntologyAdapter",
    ) -> dict[str, Any]:
        """Return the overall score plus per-atom subscores and any
        diagnostic counts useful for cross-method analysis. The shape
        is metric-specific but must include an ``overall`` key whose
        value equals :meth:`score`'s output.
        """
