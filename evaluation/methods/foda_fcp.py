"""FODA fuzzy causal-path RCA — the method under test."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class FodaFCP(RCAMethod):
    name = "foda-fcp"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("FODA FCP-RCA wrapper not yet implemented")
