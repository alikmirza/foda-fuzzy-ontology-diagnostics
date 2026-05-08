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

Ontology namespace
------------------

Annotation URIs use the namespace declared in
``ontology/DiagnosticKB.owl``:

    http://foda.com/ontology/diagnostic#

Fault-class fragments must match a class actually defined in that OWL
file (e.g. ``LatencySpike``, ``CpuSaturation``, ``MemoryLeak``,
``HighErrorRate``, ``NetworkCongestion``, ``DiskIoBottleneck``,
``ThroughputDegradation``). Healthy/non-fault services should be tagged
with the base ``MicroService`` class — there is no ``NormalOperation``
class in the ontology.

Per-case layout
---------------

Each case is one directory. Telemetry lives in a ``metrics/``
subdirectory, one CSV per service::

    foda12/
      S01/
        case.json                    # required
        metrics/
          service-A.csv              # required, one per service in ontology_mapping
          service-B.csv
          service-C.csv
      S02/
        ...

Each per-service CSV is loaded with ``pandas.read_csv`` and exposed via
``BenchmarkCase.telemetry["metrics"][<service>]`` as a DataFrame, so
methods get the real time-series rather than a summary. The set of
service CSVs must exactly match the keys of ``ontology_mapping``.

`case.json` schema
------------------

::

    {
      "id":                       "S01",
      "name":                     "LATENCY_FANOUT",
      "fault_type":               "LATENCY_ANOMALY",
      "ground_truth_root_cause":  "service-A",
      "inject_time":              1700000020,    # required, Unix timestamp
      "ontology_mapping": {
        "service-A": "http://foda.com/ontology/diagnostic#LatencySpike",
        "service-B": "http://foda.com/ontology/diagnostic#MicroService",
        "service-C": "http://foda.com/ontology/diagnostic#MicroService"
      },
      "topology": {                                # optional
        "service-A": ["service-B", "service-C"],
        "service-B": [],
        "service-C": []
      }
    }

`id` is informational; the directory name is the canonical case id.
`ontology_mapping` is mandatory for FODA-12 — a case without it is a
malformed scenario. `inject_time` is mandatory for every case so that
methods which window around the injection point (most of them) work
uniformly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


_CASE_FILENAME = "case.json"
_METRICS_DIRNAME = "metrics"

_REQUIRED_KEYS: tuple[str, ...] = (
    "fault_type",
    "ground_truth_root_cause",
    "ontology_mapping",
    "inject_time",
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
            and (p / _METRICS_DIRNAME).is_dir()
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
        if not (case_dir / _CASE_FILENAME).is_file():
            raise KeyError(
                f"FODA-12 case {case_id!r} is missing required file "
                f"{_CASE_FILENAME!r}"
            )
        if not (case_dir / _METRICS_DIRNAME).is_dir():
            raise KeyError(
                f"FODA-12 case {case_id!r} is missing required directory "
                f"{_METRICS_DIRNAME!r}/"
            )
        return self._load_case(case_dir)

    # ---- per-case loading ----

    def _load_case(self, case_dir: Path) -> BenchmarkCase:
        case_id = case_dir.name
        case_json = _read_case_json(case_dir / _CASE_FILENAME, case_id)

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

        metrics = _read_per_service_metrics(
            case_dir / _METRICS_DIRNAME, case_id, set(ontology_mapping.keys())
        )

        telemetry: dict[str, object] = {
            "metrics": metrics,
            "inject_time": float(case_json["inject_time"]),
        }
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


def _read_per_service_metrics(
    metrics_dir: Path, case_id: str, expected_services: set[str]
) -> dict[str, pd.DataFrame]:
    found = {p.stem: p for p in metrics_dir.glob("*.csv")}
    missing = expected_services - found.keys()
    extra = found.keys() - expected_services
    if missing:
        raise ValueError(
            f"FODA-12 case {case_id!r}: metrics/ is missing CSVs for "
            f"services {sorted(missing)!r} (one CSV per service in "
            f"ontology_mapping is required)"
        )
    if extra:
        raise ValueError(
            f"FODA-12 case {case_id!r}: metrics/ has CSVs for services "
            f"{sorted(extra)!r} that are not in ontology_mapping"
        )
    return {service: pd.read_csv(path) for service, path in found.items()}
