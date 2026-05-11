"""Loader for the RCAEval benchmark suite (https://github.com/phamquiluan/RCAEval).

Two on-disk layouts are supported:

1. **Nested RE1 layout** (the canonical RCAEval release layout)::

       <root>/<system>/<service>_<fault>/<instance>/data.csv
       <root>/<system>/<service>_<fault>/<instance>/inject_time.txt

   where ``<system>`` is one of ``RE1-OB``, ``RE1-SS``, ``RE1-TT``,
   ``<fault>`` is one of ``cpu``, ``mem``, ``disk``, ``delay``, ``loss``
   and ``<instance>`` is a small positive integer. The loader also
   accepts being pointed directly at a system directory
   (e.g. ``.../RE1/RE1-OB``); in that case ``<system>`` is taken from
   the directory name.

   Case IDs for nested cases are ``"{system}_{service}_{fault}_{instance}"``
   with ``system`` lowercased, e.g. ``re1-ob_adservice_cpu_1``.

2. **Flat layout** (legacy fixtures and the older RCAEval extraction
   shape): one directory per case, named
   ``{prefix}_{service}_{fault}_{instance}``, containing a metrics file
   (``simple_metrics.csv``, ``data.csv``, ``metrics.csv``, or
   ``metrics.json``) and an optional ``inject_time.txt``.

The loader auto-detects the layout from the directory structure, so
both can coexist under different roots without configuration.

If no ``data_path`` is passed, the loader reads ``RCAEVAL_DATA_PATH``
from the environment, falling back to
``~/research/rcaeval-tools/RCAEval/data/RE1/``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


DEFAULT_DATA_PATH = "~/research/rcaeval-tools/RCAEval/data/RE1/"
DATA_PATH_ENV_VAR = "RCAEVAL_DATA_PATH"


_METRICS_FILENAMES = (
    "simple_metrics.csv",
    "data.csv",
    "metrics.csv",
    "metrics.json",
)

_FAULT_TYPES = frozenset({"cpu", "mem", "disk", "delay", "loss"})

_SYSTEM_PREFIXES: dict[str, str] = {
    "OB": "online-boutique",
    "SS": "sock-shop",
    "TT": "train-ticket",
    "RE1-OB": "online-boutique",
    "RE1-SS": "sock-shop",
    "RE1-TT": "train-ticket",
}


@dataclass(frozen=True)
class _CaseDescriptor:
    """Where a case lives on disk and its parsed ground truth."""

    case_id: str
    case_dir: Path
    service: str
    fault: str
    system: str | None  # canonical RCAEval system name, when known


class RCAEvalLoader(BenchmarkLoader):
    """Lazy loader for the RCAEval dataset.

    Parameters
    ----------
    data_path:
        Path to either an RCAEval RE root (containing one or more system
        directories), a single system directory (containing
        ``{service}_{fault}/{instance}`` subdirs), or a directory of
        flat per-case folders. When ``None``, reads from the
        ``RCAEVAL_DATA_PATH`` env var, falling back to
        ``~/research/rcaeval-tools/RCAEval/data/RE1/``.
    """

    name = "rcaeval"

    def __init__(self, data_path: str | Path | None = None) -> None:
        if data_path is None:
            data_path = os.environ.get(DATA_PATH_ENV_VAR, DEFAULT_DATA_PATH)
        self.data_path = Path(data_path).expanduser()
        if not self.data_path.is_dir():
            raise FileNotFoundError(
                f"RCAEval data_path does not exist or is not a directory: "
                f"{self.data_path}"
            )

    # ---- discovery ----

    def _descriptors(self) -> list[_CaseDescriptor]:
        descriptors: list[_CaseDescriptor] = []
        for child in sorted(self.data_path.iterdir()):
            if not child.is_dir():
                continue
            # Flat layout: child is itself a case dir with metrics inside.
            if _find_metrics_file(child) is not None:
                descriptors.append(_flat_descriptor(child))
                continue
            # Service_fault dir directly under data_path → data_path is a
            # single system root.
            if _looks_like_service_fault_dir(child):
                system_dir_name = self.data_path.name
                descriptors.extend(
                    _instance_descriptors(child, system_dir_name=system_dir_name)
                )
                continue
            # Otherwise child is a system dir holding service_fault subdirs.
            for grandchild in sorted(child.iterdir()):
                if not grandchild.is_dir():
                    continue
                if not _looks_like_service_fault_dir(grandchild):
                    continue
                descriptors.extend(
                    _instance_descriptors(grandchild, system_dir_name=child.name)
                )
        return descriptors

    # ---- public API ----

    def __len__(self) -> int:
        return len(self._descriptors())

    def iter_cases(self) -> Iterator[BenchmarkCase]:
        for desc in self._descriptors():
            yield self._load_case(desc)

    def load(self) -> Iterator[BenchmarkCase]:
        return self.iter_cases()

    def get_case(self, case_id: str) -> BenchmarkCase:
        for desc in self._descriptors():
            if desc.case_id == case_id:
                return self._load_case(desc)
        # Fall back to flat-style direct lookup so we can produce the
        # historical error messages (KeyError for missing dir / missing
        # metrics, ValueError for unparseable names).
        candidate = self.data_path / case_id
        if candidate.is_dir():
            if _find_metrics_file(candidate) is None:
                raise KeyError(
                    f"RCAEval case {case_id!r} has no recognized metrics file "
                    f"(expected one of {_METRICS_FILENAMES})"
                )
            # Directory exists with metrics but parsing failed — surface the
            # parse error rather than KeyError.
            return self._load_case(_flat_descriptor(candidate))
        raise KeyError(f"unknown RCAEval case id: {case_id!r}")

    # ---- per-case loading ----

    def _load_case(self, desc: _CaseDescriptor) -> BenchmarkCase:
        metrics_path = _find_metrics_file(desc.case_dir)
        if metrics_path is None:
            raise FileNotFoundError(
                f"no metrics file in {desc.case_dir} "
                f"(expected one of {_METRICS_FILENAMES})"
            )
        metrics_df = _read_metrics(metrics_path)
        inject_time = _read_inject_time(desc.case_dir / "inject_time.txt")

        telemetry: dict[str, object] = {"metrics": metrics_df}
        if inject_time is not None:
            telemetry["inject_time"] = inject_time
        if desc.system is not None:
            telemetry["system"] = desc.system

        return BenchmarkCase(
            id=desc.case_id,
            telemetry=telemetry,
            ground_truth_root_cause=desc.service,
            ground_truth_fault_type=desc.fault,
            system_topology=None,
        )


# ---- helpers: descriptor construction ----


def _flat_descriptor(case_dir: Path) -> _CaseDescriptor:
    service, fault = _parse_flat_case_name(case_dir.name)
    return _CaseDescriptor(
        case_id=case_dir.name,
        case_dir=case_dir,
        service=service,
        fault=fault,
        system=_system_for_flat_case(case_dir.name),
    )


def _instance_descriptors(
    service_fault_dir: Path, system_dir_name: str
) -> list[_CaseDescriptor]:
    service, fault = _parse_service_fault(service_fault_dir.name)
    canonical_system = _canonical_system(system_dir_name)
    system_token = system_dir_name.lower()
    out: list[_CaseDescriptor] = []
    for inst_dir in sorted(service_fault_dir.iterdir()):
        if not inst_dir.is_dir():
            continue
        if _find_metrics_file(inst_dir) is None:
            continue
        case_id = f"{system_token}_{service_fault_dir.name}_{inst_dir.name}"
        out.append(
            _CaseDescriptor(
                case_id=case_id,
                case_dir=inst_dir,
                service=service,
                fault=fault,
                system=canonical_system,
            )
        )
    return out


def _looks_like_service_fault_dir(d: Path) -> bool:
    """A ``{service}_{fault}`` dir is one whose name ends with a known
    fault token and whose immediate children are instance dirs with
    metrics files inside."""
    name = d.name
    if "_" not in name:
        return False
    fault = name.rsplit("_", 1)[1]
    if fault.lower() not in _FAULT_TYPES:
        return False
    for child in d.iterdir():
        if child.is_dir() and _find_metrics_file(child) is not None:
            return True
    return False


# ---- helpers: I/O ----


def _find_metrics_file(case_dir: Path) -> Path | None:
    for name in _METRICS_FILENAMES:
        candidate = case_dir / name
        if candidate.is_file():
            return candidate
    return None


def _read_metrics(path: Path) -> pd.DataFrame:
    if path.suffix == ".json":
        with path.open() as fh:
            payload = json.load(fh)
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            return pd.DataFrame(payload)
        raise ValueError(
            f"unexpected metrics.json shape in {path}: {type(payload).__name__}"
        )
    return pd.read_csv(path)


def _read_inject_time(path: Path) -> float | None:
    if not path.is_file():
        return None
    text = path.read_text().strip()
    if not text:
        return None
    return float(text)


# ---- helpers: name parsing ----


def _parse_flat_case_name(case_id: str) -> tuple[str, str]:
    """``{prefix...}_{service}_{fault}_{instance}`` → ``(service, fault)``.

    The trailing segment must be a non-negative integer; the two
    segments before it are taken as ``service`` and ``fault``.
    """
    parts = case_id.split("_")
    if len(parts) < 3:
        raise ValueError(
            f"RCAEval case id {case_id!r} does not match "
            f"'{{prefix}}_{{service}}_{{fault}}_{{instance}}'"
        )
    if not parts[-1].isdigit():
        raise ValueError(
            f"RCAEval case id {case_id!r}: trailing segment {parts[-1]!r} "
            f"is not an instance number"
        )
    return parts[-3], parts[-2]


def _parse_service_fault(name: str) -> tuple[str, str]:
    """Nested-layout ``{service}_{fault}`` directory name. Service names
    may contain hyphens (``ts-auth-service``); the split is on the last
    underscore only."""
    if "_" not in name:
        raise ValueError(
            f"RCAEval service_fault dir {name!r} has no underscore separator"
        )
    service, fault = name.rsplit("_", 1)
    return service, fault


def _system_for_flat_case(case_id: str) -> str | None:
    """Best-effort guess at the microservice system from a flat case id."""
    head = case_id.split("_", 1)[0].upper()
    if head in _SYSTEM_PREFIXES:
        return _SYSTEM_PREFIXES[head]
    parts = case_id.split("_")
    if len(parts) >= 2:
        second = parts[1].upper()
        if second in _SYSTEM_PREFIXES:
            return _SYSTEM_PREFIXES[second]
    return None


def _canonical_system(system_dir_name: str) -> str | None:
    """Map a system directory name (e.g. ``RE1-OB``) to its canonical
    RCAEval system name (``online-boutique``). Returns ``None`` if the
    prefix is unrecognized."""
    key = system_dir_name.upper()
    if key in _SYSTEM_PREFIXES:
        return _SYSTEM_PREFIXES[key]
    # Try ``RE1-XX`` → ``XX`` fallback.
    if "-" in key:
        tail = key.rsplit("-", 1)[1]
        if tail in _SYSTEM_PREFIXES:
            return _SYSTEM_PREFIXES[tail]
    return None
