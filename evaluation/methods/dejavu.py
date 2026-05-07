"""DejaVu baseline."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class DejaVu(RCAMethod):
    name = "dejavu"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("DejaVu wrapper not yet implemented")
