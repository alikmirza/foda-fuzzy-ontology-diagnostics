"""Loader for the FODA-12 internal benchmark."""

from __future__ import annotations

from typing import Iterator

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


class Foda12Loader(BenchmarkLoader):
    name = "foda-12"

    def __init__(self, root: str) -> None:
        self.root = root

    def load(self) -> Iterator[BenchmarkCase]:
        raise NotImplementedError("FODA-12 loader not yet implemented")
