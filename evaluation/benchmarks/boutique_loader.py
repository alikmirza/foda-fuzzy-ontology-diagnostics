"""Loader for the Online Boutique fault-injection benchmark."""

from __future__ import annotations

from typing import Iterator

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


class BoutiqueLoader(BenchmarkLoader):
    name = "online-boutique"

    def __init__(self, root: str) -> None:
        self.root = root

    def load(self) -> Iterator[BenchmarkCase]:
        raise NotImplementedError("Online Boutique loader not yet implemented")
