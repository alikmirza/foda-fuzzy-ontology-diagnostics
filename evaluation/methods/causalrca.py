"""CausalRCA baseline."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class CausalRCA(RCAMethod):
    name = "causalrca"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("CausalRCA wrapper not yet implemented")
