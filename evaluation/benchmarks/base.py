"""Abstract base class for benchmark loaders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ..extraction.canonical_explanation import BenchmarkCase


class BenchmarkLoader(ABC):
    """Yields `BenchmarkCase` objects from a particular benchmark dataset."""

    name: str = ""

    @abstractmethod
    def load(self) -> Iterator[BenchmarkCase]:
        """Iterate over all cases in the benchmark."""
        ...

    def __iter__(self) -> Iterator[BenchmarkCase]:
        return self.load()
