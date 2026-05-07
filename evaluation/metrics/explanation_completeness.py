"""Explanation completeness — coverage of the ground-truth fault chain
(symptom -> intermediate -> root cause) by the produced explanation graph.
"""

from __future__ import annotations

from typing import Any

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import Metric


class ExplanationCompleteness(Metric):
    name = "explanation_completeness"

    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        raise NotImplementedError("explanation completeness not yet implemented")
