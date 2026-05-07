"""Helpers that map raw telemetry symbols (metric names, log templates,
service identifiers) to ontology classes in the FODA OWL ontology.

Filled in alongside the per-method extractors in `methods/`.
"""

from __future__ import annotations

from typing import Any


def map_telemetry_to_ontology(telemetry: Any, ontology: Any) -> dict[str, str]:
    """Return a dict from telemetry-symbol -> ontology class URI."""
    raise NotImplementedError("ontology mapping not yet implemented")
