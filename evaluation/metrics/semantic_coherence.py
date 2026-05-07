"""Semantic coherence — internal consistency of an explanation graph
relative to the FODA ontology (no contradictory ontology classes along a
causal path, weights monotone where required, etc.).
"""

from __future__ import annotations

from typing import Any

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import Metric


class SemanticCoherence(Metric):
    name = "semantic_coherence"

    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        raise NotImplementedError("semantic coherence not yet implemented")
