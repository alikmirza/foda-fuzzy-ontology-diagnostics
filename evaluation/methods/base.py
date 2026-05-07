"""Abstract base class for RCA methods under evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput


class RCAMethod(ABC):
    """Common interface every method must implement.

    Implementations are responsible for converting their native output into
    a `DiagnosticOutput` (including building a `CanonicalExplanation`),
    so all methods can be compared on common metrics.
    """

    name: str = ""

    @abstractmethod
    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        ...
