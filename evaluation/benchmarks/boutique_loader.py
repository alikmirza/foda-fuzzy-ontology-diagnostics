"""Loader for the Online Boutique fault-injection benchmark.

Online Boutique is Google's reference cloud-native demo
(https://github.com/GoogleCloudPlatform/microservices-demo). For our
paper we inject faults with a chaos tool (chaos-mesh / litmus) and
scrape Prometheus metrics for each affected window. There is no
canonical on-disk corpus shipped with that project — the benchmark we
evaluate is whatever we capture ourselves.

To stay compatible with the rest of the harness, this loader expects
the same directory pattern as `RCAEvalLoader`: one folder per case,
each folder containing a metrics file. Two extras:

- A per-case `manifest.json`, when present, overrides the
  directory-name-derived ground truth. This is the path we'll use once
  the chaos-mesh capture pipeline lands, since it doesn't constrain how
  cases are named on disk.
- Per-service CSVs (`{service}_metrics.csv`) are merged on the `time`
  column when no single combined CSV is found. Combined CSVs
  (`simple_metrics.csv`, `data.csv`, `metrics.csv`) take priority and
  match the RCAEval format byte-for-byte so existing RCAEval fixtures
  can be replayed through this loader.
"""

from __future__ import annotations

import json
from functools import reduce
from pathlib import Path
from typing import Iterator

import pandas as pd

from ..extraction.canonical_explanation import BenchmarkCase
from .base import BenchmarkLoader


_COMBINED_METRICS_FILENAMES = (
    "simple_metrics.csv",
    "data.csv",
    "metrics.csv",
)
_PER_SERVICE_GLOB = "*_metrics.csv"
_MANIFEST_FILENAME = "manifest.json"


class BoutiqueLoader(BenchmarkLoader):
    """Lazy loader for the Online Boutique fault-injection benchmark."""

    name = "online-boutique"

    def __init__(self, data_path: str | Path) -> None:
        self.data_path = Path(data_path)
        if not self.data_path.is_dir():
            raise FileNotFoundError(
                f"Boutique data_path does not exist or is not a directory: "
                f"{self.data_path}"
            )

    # ---- discovery ----

    def _case_dirs(self) -> list[Path]:
        return sorted(
            p
            for p in self.data_path.iterdir()
            if p.is_dir() and self._has_metrics(p)
        )

    @staticmethod
    def _has_metrics(case_dir: Path) -> bool:
        return _find_combined_metrics(case_dir) is not None or _has_per_service(
            case_dir
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
            raise KeyError(f"unknown Boutique case id: {case_id!r}")
        if not self._has_metrics(case_dir):
            raise KeyError(
                f"Boutique case {case_id!r} has no metrics file "
                f"(expected one of {_COMBINED_METRICS_FILENAMES} or "
                f"{_PER_SERVICE_GLOB})"
            )
        return self._load_case(case_dir)

    # ---- per-case loading ----

    def _load_case(self, case_dir: Path) -> BenchmarkCase:
        case_id = case_dir.name
        manifest = _read_manifest(case_dir / _MANIFEST_FILENAME)
        metrics_df = _read_metrics(case_dir)
        inject_time = _read_inject_time(case_dir / "inject_time.txt")

        root_cause, fault_type = _resolve_ground_truth(case_id, manifest)
        topology = manifest.get("topology") if manifest else None

        telemetry: dict[str, object] = {"metrics": metrics_df}
        if inject_time is not None:
            telemetry["inject_time"] = inject_time

        return BenchmarkCase(
            id=case_id,
            telemetry=telemetry,
            ground_truth_root_cause=root_cause,
            ground_truth_fault_type=fault_type,
            system_topology=topology,
        )


# ---- helpers ----


def _find_combined_metrics(case_dir: Path) -> Path | None:
    for name in _COMBINED_METRICS_FILENAMES:
        candidate = case_dir / name
        if candidate.is_file():
            return candidate
    return None


def _has_per_service(case_dir: Path) -> bool:
    for f in case_dir.glob(_PER_SERVICE_GLOB):
        if f.name not in _COMBINED_METRICS_FILENAMES and f.is_file():
            return True
    return False


def _read_metrics(case_dir: Path) -> pd.DataFrame:
    combined = _find_combined_metrics(case_dir)
    if combined is not None:
        return pd.read_csv(combined)

    per_service = sorted(
        f
        for f in case_dir.glob(_PER_SERVICE_GLOB)
        if f.name not in _COMBINED_METRICS_FILENAMES and f.is_file()
    )
    if not per_service:
        raise FileNotFoundError(
            f"no metrics files in {case_dir}; expected one of "
            f"{_COMBINED_METRICS_FILENAMES} or *_metrics.csv per service"
        )
    frames = [pd.read_csv(f) for f in per_service]
    if any("time" not in df.columns for df in frames):
        raise ValueError(
            f"per-service CSVs in {case_dir} must each contain a 'time' "
            f"column to be merged"
        )
    return reduce(
        lambda left, right: pd.merge(left, right, on="time", how="outer"),
        frames,
    ).sort_values("time").reset_index(drop=True)


def _read_inject_time(path: Path) -> float | None:
    if not path.is_file():
        return None
    text = path.read_text().strip()
    return float(text) if text else None


def _read_manifest(path: Path) -> dict | None:
    if not path.is_file():
        return None
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _resolve_ground_truth(
    case_id: str, manifest: dict | None
) -> tuple[str, str]:
    """Manifest wins; fall back to RCAEval-style directory parsing."""
    if manifest is not None:
        try:
            return manifest["root_cause"], manifest["fault_type"]
        except KeyError as exc:
            raise ValueError(
                f"Boutique manifest for {case_id!r} missing required key "
                f"{exc.args[0]!r}"
            ) from None
    return _parse_case_name(case_id)


def _parse_case_name(case_id: str) -> tuple[str, str]:
    """Mirror of RCAEvalLoader's parser: ``..._{service}_{fault}_{instance}``."""
    parts = case_id.split("_")
    if len(parts) < 3:
        raise ValueError(
            f"Boutique case id {case_id!r} does not match "
            f"'{{prefix}}_{{service}}_{{fault}}_{{instance}}' and no "
            f"manifest.json was found"
        )
    if not parts[-1].isdigit():
        raise ValueError(
            f"Boutique case id {case_id!r}: trailing segment {parts[-1]!r} "
            f"is not an instance number, and no manifest.json was found"
        )
    return parts[-3], parts[-2]
