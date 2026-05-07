"""MicroRCA baseline (Wu et al., 2020)."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class MicroRCA(RCAMethod):
    name = "microrca"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("MicroRCA wrapper not yet implemented")
