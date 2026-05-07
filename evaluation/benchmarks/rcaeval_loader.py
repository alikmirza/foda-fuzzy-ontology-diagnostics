"""Loader for the RCAEval benchmark suite (https://github.com/phamquiluan/RCAEval).

RCAEval ships 735 failure cases across three microservice systems:
online-boutique, sock-shop, and train-ticket. The on-disk layout the
official README documents is one directory per case, with names of the
form `{prefix}_{service}_{fault}_{instance}` — for example
`OB_cartservice_CPU_1` or `RE1_SS_carts_cpu_1`. Each case folder contains
a metrics file (one of `simple_metrics.csv`, `data.csv`, `metrics.csv`,
or `metrics.json`) and an optional `inject_time.txt` with a Unix
timestamp marking when the fault was injected.

Ground truth is encoded directly in the directory name: the
second-to-last underscore segment is the fault type, the third-to-last
is the root-cause service. Any preceding segments describe the dataset
release / system and are kept verbatim in `BenchmarkCase.id` so the
caller can group results by system.

This loader does not attempt to download or unpack RCAEval — point it
at an already-extracted folder. See `evaluation/README.md` for download
instructions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


_METRICS_FILENAMES = (
    "simple_metrics.csv",
    "data.csv",
    "metrics.csv",
    "metrics.json",
)

_SYSTEM_PREFIXES: dict[str, str] = {
    "OB": "online-boutique",
    "SS": "sock-shop",
    "TT": "train-ticket",
}


class RCAEvalLoader(BenchmarkLoader):
    """Lazy loader for the RCAEval dataset.

    Parameters
    ----------
    data_path:
        Path to a directory whose immediate children are per-case folders.
    """

    name = "rcaeval"

    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)
        if not self.data_path.is_dir():
            raise FileNotFoundError(
                f"RCAEval data_path does not exist or is not a directory: "
                f"{self.data_path}"
            )

    # ---- discovery ----

    def _case_dirs(self) -> list[Path]:
        return sorted(
            p
            for p in self.data_path.iterdir()
            if p.is_dir() and self._find_metrics_file(p) is not None
        )

    @staticmethod
    def _find_metrics_file(case_dir: Path) -> Path | None:
        for name in _METRICS_FILENAMES:
            candidate = case_dir / name
            if candidate.is_file():
                return candidate
        return None

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
            raise KeyError(f"unknown RCAEval case id: {case_id!r}")
        if self._find_metrics_file(case_dir) is None:
            raise KeyError(
                f"RCAEval case {case_id!r} has no recognized metrics file "
                f"(expected one of {_METRICS_FILENAMES})"
            )
        return self._load_case(case_dir)

    # ---- per-case loading ----

    def _load_case(self, case_dir: Path) -> BenchmarkCase:
        case_id = case_dir.name
        service, fault = _parse_case_name(case_id)
        metrics_path = self._find_metrics_file(case_dir)
        assert metrics_path is not None  # guarded by _case_dirs / get_case
        metrics_df = _read_metrics(metrics_path)
        inject_time = _read_inject_time(case_dir / "inject_time.txt")
        system = _system_for_case(case_id)

        telemetry: dict[str, object] = {"metrics": metrics_df}
        if inject_time is not None:
            telemetry["inject_time"] = inject_time
        if system is not None:
            telemetry["system"] = system

        return BenchmarkCase(
            id=case_id,
            telemetry=telemetry,
            ground_truth_root_cause=service,
            ground_truth_fault_type=fault,
            system_topology=None,
        )


# ---- helpers ----


def _parse_case_name(case_id: str) -> tuple[str, str]:
    """Return ``(service, fault)`` parsed from an RCAEval case directory name.

    The convention is ``{prefix...}_{service}_{fault}_{instance}`` where
    ``instance`` is a non-negative integer. A few real cases include
    underscores in the service name; we treat the last numeric segment
    as the instance, and split the remaining tail as ``service_fault``.
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
    fault = parts[-2]
    service = parts[-3]
    return service, fault


def _system_for_case(case_id: str) -> str | None:
    """Best-effort guess at the microservice system from the case prefix."""
    head = case_id.split("_", 1)[0].upper()
    if head in _SYSTEM_PREFIXES:
        return _SYSTEM_PREFIXES[head]
    # Some releases prefix with a dataset tag (RE1/RE2/RE3) followed by
    # the system code; check the second segment too.
    parts = case_id.split("_")
    if len(parts) >= 2:
        second = parts[1].upper()
        if second in _SYSTEM_PREFIXES:
            return _SYSTEM_PREFIXES[second]
    return None


def _read_metrics(path: Path) -> pd.DataFrame:
    if path.suffix == ".json":
        with path.open() as fh:
            payload = json.load(fh)
        # RCAEval stores metrics.json as either a records list or a
        # column-oriented dict; pandas handles both via DataFrame().
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
