"""BARO baseline."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class BARO(RCAMethod):
    name = "baro"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("BARO wrapper not yet implemented")
