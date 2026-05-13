"""Metrics for evaluating RCA outputs.

Two metric families:

* **Ranking metrics** (:class:`Metric`): score ``(case, output)`` pairs;
  see :mod:`ranking_metrics`.
* **Semantic-quality metrics** (:class:`SemanticMetric`): score a
  :class:`CanonicalExplanation` against an
  :class:`OntologyAdapter`-wrapped ontology. Paper 6 Phase 2's four
  metrics (SemanticGroundedness, SemanticCoherence,
  ExplanationCompleteness, ConfidenceCalibration) share this contract.
"""

from .base import Metric, SemanticMetric
from .confidence_calibration import (
    ConfidenceCalibration,
    compute_ece,
    compute_reliability_diagram,
    per_case_calibration_error,
)
from .explanation_completeness import ExplanationCompleteness
from .ontology_adapter import OntologyAdapter
from .ranking_metrics import accuracy_at_k, mean_reciprocal_rank
from .semantic_coherence import SemanticCoherence
from .semantic_groundedness import SemanticGroundedness

__all__ = [
    "ConfidenceCalibration",
    "ExplanationCompleteness",
    "Metric",
    "SemanticMetric",
    "OntologyAdapter",
    "SemanticCoherence",
    "SemanticGroundedness",
    "accuracy_at_k",
    "compute_ece",
    "compute_reliability_diagram",
    "mean_reciprocal_rank",
    "per_case_calibration_error",
]
