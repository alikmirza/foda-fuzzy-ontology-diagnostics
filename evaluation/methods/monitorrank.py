"""MonitorRank baseline (Kim et al., 2013)."""

from __future__ import annotations

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import RCAMethod


class MonitorRank(RCAMethod):
    name = "monitorrank"

    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        raise NotImplementedError("MonitorRank wrapper not yet implemented")
