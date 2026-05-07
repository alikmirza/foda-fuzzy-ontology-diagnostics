"""Semantic groundedness — fraction of explanation atoms whose claims are
supported by ontology classes consistent with the observed telemetry.
"""

from __future__ import annotations

from typing import Any

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import Metric


class SemanticGroundedness(Metric):
    name = "semantic_groundedness"

    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        raise NotImplementedError("semantic groundedness not yet implemented")
