"""Loader for the FODA-12 benchmark.

FODA-12 is the 12-scenario synthetic benchmark used in our paper. The
authoritative definition lives in Java today
(``fuzzy-rca-engine/src/main/java/com/foda/rca/evaluation/SyntheticScenarioBuilder.java``);
the Python harness consumes an export of those scenarios written one
folder per case. The export pipeline is tracked separately — this
loader assumes it has already run.

What sets FODA-12 apart from RCAEval / Online Boutique is that every
scenario carries **ontology-class annotations** for the services
involved: each service in the topology is tagged with a URI from the
FODA OWL ontology so that ontology-aware methods (FODA-FCP) and
explanation-quality metrics (semantic groundedness, semantic coherence)
have something concrete to reason against. Those annotations are passed
through to ``BenchmarkCase.ontology_mapping`` verbatim.

Per-case layout::

    foda12/
      S01/
        case.json       # required
        metrics.csv     # required
      S02/
        ...

`case.json` schema::

    {
      "id":                       "S01",
      "name":                     "LATENCY_FANOUT",
      "fault_type":               "LATENCY_ANOMALY",
      "ground_truth_root_cause":  "service-A",
      "ontology_mapping": {
        "service-A": "http://foda.example.org/onto#LatencyFault",
        "service-B": "http://foda.example.org/onto#NormalOperation"
      },
      "topology": {                  # optional
        "service-A": ["service-B"],
        "service-B": []
      },
      "inject_time": 1700000020      # optional Unix timestamp
    }

`id` is informational; the directory name is the canonical case id.
`ontology_mapping` is mandatory for FODA-12 — a case without it is a
malformed scenario.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


_CASE_FILENAME = "case.json"
_METRICS_FILENAME = "metrics.csv"

_REQUIRED_KEYS: tuple[str, ...] = (
    "fault_type",
    "ground_truth_root_cause",
    "ontology_mapping",
)


class Foda12Loader(BenchmarkLoader):
    """Lazy loader for the FODA-12 synthetic benchmark."""

    name = "foda-12"

    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)
        if not self.data_path.is_dir():
            raise FileNotFoundError(
                f"FODA-12 data_path does not exist or is not a directory: "
                f"{self.data_path}"
            )

    # ---- discovery ----

    def _case_dirs(self) -> list[Path]:
        return sorted(
            p
            for p in self.data_path.iterdir()
            if p.is_dir()
            and (p / _CASE_FILENAME).is_file()
            and (p / _METRICS_FILENAME).is_file()
        )

    # ---- public API ----

    def __len__(self) -> int:
        return len(self._case_dirs())

    def iter_cases(self) -> Iterator[BenchmarkCase]:
        for case_dir in self._case_dirs():
            yield self._load_case(case_dir)

    def load(self) -> Iterator[BenchmarkCase]:
        return self.iter_cases()

    def get_case(self, case_id: str) -> BenchmarkCase:
        case_dir = self.data_path / case_id
        if not case_dir.is_dir():
            raise KeyError(f"unknown FODA-12 case id: {case_id!r}")
        for fname in (_CASE_FILENAME, _METRICS_FILENAME):
            if not (case_dir / fname).is_file():
                raise KeyError(
                    f"FODA-12 case {case_id!r} is missing required file "
                    f"{fname!r}"
                )
        return self._load_case(case_dir)

    # ---- per-case loading ----

    def _load_case(self, case_dir: Path) -> BenchmarkCase:
        case_id = case_dir.name
        case_json = _read_case_json(case_dir / _CASE_FILENAME, case_id)
        metrics_df = pd.read_csv(case_dir / _METRICS_FILENAME)

        ontology_mapping = case_json["ontology_mapping"]
        if not isinstance(ontology_mapping, dict) or not ontology_mapping:
            raise ValueError(
                f"FODA-12 case {case_id!r}: ontology_mapping must be a "
                f"non-empty object"
            )
        if case_json["ground_truth_root_cause"] not in ontology_mapping:
            raise ValueError(
                f"FODA-12 case {case_id!r}: root cause "
                f"{case_json['ground_truth_root_cause']!r} is not in "
                f"ontology_mapping (every scenario must annotate at least "
                f"the root-cause service)"
            )

        telemetry: dict[str, object] = {"metrics": metrics_df}
        if "inject_time" in case_json:
            telemetry["inject_time"] = float(case_json["inject_time"])
        if "name" in case_json:
            telemetry["scenario_name"] = case_json["name"]

        return BenchmarkCase(
            id=case_id,
            telemetry=telemetry,
            ground_truth_root_cause=case_json["ground_truth_root_cause"],
            ground_truth_fault_type=case_json["fault_type"],
            system_topology=case_json.get("topology"),
            ontology_mapping=ontology_mapping,
        )


# ---- helpers ----


def _read_case_json(path: Path, case_id: str) -> dict:
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    missing = [k for k in _REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(
            f"FODA-12 case {case_id!r}: case.json missing required keys "
            f"{missing!r}"
        )
    return data
