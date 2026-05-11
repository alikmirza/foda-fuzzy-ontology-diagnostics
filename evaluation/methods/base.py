"""Abstract base class for RCA methods under evaluation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput

if TYPE_CHECKING:
    from ..extraction.schema_normalizer import NormalizedCase


class RCAMethod(ABC):
    """Common interface every method must implement.

    Implementations are responsible for converting their native output into
    a `DiagnosticOutput` (including building a `CanonicalExplanation`),
    so all methods can be compared on common metrics.

    ``train`` is a no-op by default. Methods that need a training phase
    (e.g. DejaVu, which learns a neural classifier from historical
    failure cases) override it. The training set is expressed as a list
    of :class:`NormalizedCase`; training MAY read each case's
    ``ground_truth`` side channel because labels are exactly what makes
    a training case useful. ``diagnose`` at inference time MUST NOT —
    that distinction is what
    :func:`evaluation.methods._protocol.validate_no_ground_truth_peeking`
    enforces (the AST validator scans ``diagnose`` only).
    """

    name: str = ""

    def train(self, training_cases: "list[NormalizedCase]") -> None:
        """Train the method on labeled historical cases.

        Default is a no-op for methods that do not have a training phase
        (every adapter prior to DejaVu in this suite is single-shot at
        inference time and ignores ``training_cases``).
        """
        return None

    @abstractmethod
    def diagnose(self, case: BenchmarkCase) -> DiagnosticOutput:
        ...
