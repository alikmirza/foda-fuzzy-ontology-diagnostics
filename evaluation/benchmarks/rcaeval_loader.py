"""Loader for the RCAEval benchmark suite."""

from __future__ import annotations

from typing import Iterator

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


class RCAEvalLoader(BenchmarkLoader):
    name = "rcaeval"

    def __init__(self, root: str) -> None:
        self.root = root

    def load(self) -> Iterator[BenchmarkCase]:
        raise NotImplementedError("RCAEval loader not yet implemented")
