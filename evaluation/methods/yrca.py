"""YRCA baseline."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class YRCA(RCAMethod):
    name = "yrca"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("YRCA wrapper not yet implemented")
