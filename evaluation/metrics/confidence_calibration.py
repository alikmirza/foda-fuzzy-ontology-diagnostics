"""Confidence calibration — how well a method's reported confidence tracks
its actual top-1 accuracy across cases (ECE / reliability-curve style).
"""

from __future__ import annotations

from typing import Any

from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from .base import Metric


class ConfidenceCalibration(Metric):
    name = "confidence_calibration"

    def compute(self, output: DiagnosticOutput, case: BenchmarkCase) -> Any:
        raise NotImplementedError("confidence calibration not yet implemented")
