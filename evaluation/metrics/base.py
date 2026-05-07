"""Abstract base class for metrics."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput


class Metric(ABC):
    """A metric reduces a (case, output) pair to a numeric score."""

    name: str = ""

    @abstractmethod
    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        ...
