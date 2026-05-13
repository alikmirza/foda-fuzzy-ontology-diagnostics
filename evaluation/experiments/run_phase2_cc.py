"""Phase 2 Week 4 — score :class:`ConfidenceCalibration` (ECE) for every
method on RE1-OB, alongside SG / SC / EC and the AC@1 join needed for
cross-metric Spearman.

ConfidenceCalibration is the fourth (and final) Paper 6 Phase 2
semantic-quality metric, and the only one that's **aggregate**: ECE is
defined over a population of cases, not per-explanation. The brief's
Option A choice ships it as a standalone analyzer (no
``SemanticMetric`` subclass) — see DEVIATIONS.md →
``ConfidenceCalibration metric (Paper 6 Phase 2 Week 4)``.

This harness mirrors :mod:`evaluation.experiments.run_phase2_ec`'s
shape. Per-case rows carry the method's ``confidence`` and the binary
``correct`` (= AC@1) needed for ECE, plus the joined SG / SC / EC and a
``cal_error = |confidence − target|`` per-case proxy used only for
Spearman against the per-case metrics (the brief's Step 4).

The output CSV has one row per ``(method, fault)`` pair, plus a
``fault = "ALL"`` aggregate row per method. Schema:

    method, fault, n_cases, ece, mean_confidence, mean_accuracy,
    overconfidence_bins, underconfidence_bins

Usage::

    python -m evaluation.experiments.run_phase2_cc \\
        --data ~/research/rcaeval-tools/RCAEval/data/RE1/RE1-OB \\
        --out results/phase2_confidence_calibration.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..benchmarks.rcaeval_loader import RCAEvalLoader
from ..extraction.canonical_explanation import BenchmarkCase, DiagnosticOutput
from ..extraction.schema_normalizer import NormalizedCase, normalize_case
from ..methods.baro import BAROMethod
from ..methods.causalrca import CausalRCAMethod
from ..methods.dejavu import DejaVuMethod
from ..methods.foda_fcp import FodaFCPMethod
from ..methods.microrca import MicroRCAMethod
from ..methods.monitorrank import MonitorRankMethod
from ..methods.yrca import YRCAMethod
from ..metrics import (
    ConfidenceCalibration,
    ExplanationCompleteness,
    OntologyAdapter,
    SemanticCoherence,
    SemanticGroundedness,
    compute_ece,
    compute_reliability_diagram,
    per_case_calibration_error,
)


# DejaVu hyperparameters — same as the Week 3 harness so the 5-fold
# split is reproducible across the four Phase 2 weeks.
_DEJAVU_FOLDS: int = 5
_DEJAVU_EPOCHS: int = 80
_DEJAVU_HIDDEN: int = 32
_DEJAVU_SEED: int = 0

_DEFAULT_N_BINS: int = 10

# Aggregate-row sentinel for the per-fault CSV column. The CSV writer
# emits one row per (method, fault) and one row with this value as the
# fault column for each method's overall ECE.
_ALL_FAULTS_LABEL: str = "ALL"


# Per-method routing: which :class:`DiagnosticOutput` field to read as
# the calibration-axis confidence. Six of seven methods emit a [0, 1]-
# scaled confidence in the primary ``confidence`` field. BARO emits
# the BOCPD marginal posterior P(r_t=0 | x_{1:t}) in ``confidence``,
# which is bounded by ~1/T under BOCPD's hazard prior — fine for
# absolute probabilistic interpretation but scale-incomparable to
# head-ratio / softmax confidences used by every other method. BARO
# exposes ``peak_confidence`` (band-normalised posterior peak) on the
# same [0, 1] scale, and we read that for cross-method calibration.
# The routing decision is documented in DEVIATIONS.md → "Confidence
# Calibration metric (Paper 6 Phase 2 Week 4)".
_METHOD_CONFIDENCE_FIELD: dict[str, str] = {
    "BARO": "peak_confidence",
}


_SINGLE_SHOT_METHODS: dict[str, Any] = {
    "MR":       lambda: MonitorRankMethod(),
    "CR":       lambda: CausalRCAMethod(),
    "Micro":    lambda: MicroRCAMethod(),
    "BARO":     lambda: BAROMethod(),
    "yRCA":     lambda: YRCAMethod(),
    "FODA-FCP": lambda: FodaFCPMethod(),
}


def evaluate(
    data_path: Path,
    sg: SemanticGroundedness | None = None,
    sc: SemanticCoherence | None = None,
    ec: ExplanationCompleteness | None = None,
    cc: ConfidenceCalibration | None = None,
    ontology: OntologyAdapter | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Run every method on every case, score CC/SG/SC/EC/AC@1.

    Returns:

    * ``per_case_rows`` — 875 rows ``{method, case_id, fault,
      confidence, correct, cal_error, ac1, sg, sc, ec_overall}`` for
      cross-metric Spearman and the per-fault aggregation.
    * ``summary_rows`` — one row per ``(method, fault)`` + per-method
      aggregate row (fault = ``"ALL"``) for the CSV write.
    * ``per_method`` — dict keyed by method label, each value carries
      summary fields + the reliability-diagram dict; consumed by
      :func:`print_summary`.
    """
    sg = sg or SemanticGroundedness()
    sc = sc or SemanticCoherence()
    ec = ec or ExplanationCompleteness()
    cc = cc or ConfidenceCalibration(n_bins=_DEFAULT_N_BINS)
    ontology = ontology or OntologyAdapter()
    loader = RCAEvalLoader(data_path)
    cases = list(loader.iter_cases())
    if not cases:
        raise RuntimeError(f"no cases under {data_path}")

    per_case_rows: list[dict[str, Any]] = []
    for label, factory in _SINGLE_SHOT_METHODS.items():
        method = factory()
        window_s = method.window_seconds
        norms = [normalize_case(c, window_seconds=window_s) for c in cases]
        for case, norm in zip(cases, norms):
            out = method.diagnose_normalized(norm)
            per_case_rows.append(
                _score_row(label, case, norm, out, sg, sc, ec, ontology),
            )
    per_case_rows.extend(_dejavu_rows(cases, sg, sc, ec, ontology))

    summary_rows, per_method = _summarize(per_case_rows, cc)
    return per_case_rows, summary_rows, per_method


def _score_row(
    method_label: str,
    case: BenchmarkCase,
    norm: NormalizedCase,
    out: DiagnosticOutput,
    sg: SemanticGroundedness,
    sc: SemanticCoherence,
    ec: ExplanationCompleteness,
    ontology: OntologyAdapter,
) -> dict[str, Any]:
    """One per-(method, case) row carrying confidence + per-case
    metric values + the per-case calibration-error proxy.

    The metric values are joined here so the harness emits a single
    rectangular table for cross-metric Spearman without downstream
    merges.
    """
    sg_overall = sg.score(out.explanation_chain, ontology)
    sc_overall = sc.score(out.explanation_chain, ontology)
    ec_overall = ec.score(out.explanation_chain, ontology, case_services=norm.services)
    ac1 = (
        1.0
        if out.ranked_list and out.ranked_list[0][0] == case.ground_truth_root_cause
        else 0.0
    )
    correct = bool(ac1)
    # Method-specific routing: read peak_confidence for BARO,
    # confidence for everyone else. See _METHOD_CONFIDENCE_FIELD
    # for the rationale.
    field = _METHOD_CONFIDENCE_FIELD.get(method_label, "confidence")
    confidence_value = getattr(out, field)
    if confidence_value is None:
        raise RuntimeError(
            f"{method_label} returned None on field {field!r} for {case.id} — "
            f"all 7 Paper 6 methods must emit a non-None {field}"
        )
    confidence = float(confidence_value)
    return {
        "method": method_label,
        "case_id": case.id,
        "fault": case.ground_truth_fault_type,
        "confidence": confidence,
        "correct": int(correct),
        "cal_error": per_case_calibration_error(confidence, correct),
        "ac1": ac1,
        "sg": sg_overall,
        "sc": sc_overall,
        "ec_overall": ec_overall,
    }


# ---- DejaVu CV (same shape as Week 3 harness) -----------------------------


def _dejavu_fold_assignment(
    cases: list[BenchmarkCase], n_folds: int = _DEJAVU_FOLDS, seed: int = _DEJAVU_SEED,
) -> list[int]:
    by_fault: dict[str, list[BenchmarkCase]] = defaultdict(list)
    for c in cases:
        by_fault[c.ground_truth_fault_type].append(c)
    fold_of: dict[str, int] = {}
    for fault, group in sorted(by_fault.items()):
        ordered = sorted(
            group,
            key=lambda c: hashlib.sha256(f"{seed}|{c.id}".encode("utf-8")).digest(),
        )
        offset = int.from_bytes(
            hashlib.sha256(f"{seed}|{fault}".encode("utf-8")).digest()[:4], "big",
        ) % n_folds
        for i, c in enumerate(ordered):
            fold_of[c.id] = (offset + i) % n_folds
    return [fold_of[c.id] for c in cases]


def _dejavu_rows(
    cases: list[BenchmarkCase],
    sg: SemanticGroundedness,
    sc: SemanticCoherence,
    ec: ExplanationCompleteness,
    ontology: OntologyAdapter,
) -> list[dict[str, Any]]:
    method0 = DejaVuMethod(
        epochs=_DEJAVU_EPOCHS, hidden=_DEJAVU_HIDDEN, seed=_DEJAVU_SEED,
    )
    norms = [normalize_case(c, window_seconds=method0.window_seconds) for c in cases]
    folds = _dejavu_fold_assignment(cases)

    rows: list[dict[str, Any]] = []
    for fold_idx in range(_DEJAVU_FOLDS):
        train_norms = [n for n, f in zip(norms, folds) if f != fold_idx]
        test_indices = [i for i, f in enumerate(folds) if f == fold_idx]
        if not train_norms or not test_indices:
            continue
        method = DejaVuMethod(
            epochs=_DEJAVU_EPOCHS, hidden=_DEJAVU_HIDDEN, seed=_DEJAVU_SEED,
        )
        method.train(train_norms)
        for i in test_indices:
            out = method.diagnose_normalized(norms[i])
            rows.append(_score_row(
                "DejaVu", cases[i], norms[i], out, sg, sc, ec, ontology,
            ))
    return rows


# ---- aggregation ----------------------------------------------------------


def _summarize(
    per_case_rows: list[dict[str, Any]],
    cc: ConfidenceCalibration,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Build per-(method, fault) summary rows for CSV + per-method
    aggregates carrying SG/SC/EC means and the reliability diagram.

    The per-fault rows aggregate over cases sharing a (method, fault)
    combination. The per-method aggregate row uses fault =
    ``_ALL_FAULTS_LABEL`` and consumes the same code path so the CSV
    schema is uniform.
    """
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_method_fault: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in per_case_rows:
        by_method[r["method"]].append(r)
        by_method_fault[(r["method"], r["fault"])].append(r)

    summary_rows: list[dict[str, Any]] = []
    per_method: dict[str, dict[str, Any]] = {}

    for method, method_rows in by_method.items():
        agg = cc.summarize(method_rows)
        diag = cc.reliability_diagram(method_rows)
        per_method[method] = {
            "n": len(method_rows),
            "ece": agg["ece"],
            "mean_confidence": agg["mean_confidence"],
            "mean_accuracy": agg["mean_accuracy"],
            "overconfidence_bins": agg["overconfidence_bins"],
            "underconfidence_bins": agg["underconfidence_bins"],
            "sg_mean": statistics.mean(r["sg"] for r in method_rows),
            "sc_mean": statistics.mean(r["sc"] for r in method_rows),
            "ec_mean": statistics.mean(r["ec_overall"] for r in method_rows),
            "reliability": diag,
            "per_fault": {},
        }
        summary_rows.append({
            "method": method,
            "fault": _ALL_FAULTS_LABEL,
            "n_cases": len(method_rows),
            "ece": agg["ece"],
            "mean_confidence": agg["mean_confidence"],
            "mean_accuracy": agg["mean_accuracy"],
            "overconfidence_bins": agg["overconfidence_bins"],
            "underconfidence_bins": agg["underconfidence_bins"],
        })

    # Iterate methods in the order they first appear in the row list
    # so the harness handles the canonical 7-method set AND any synthetic
    # method labels that smoke tests pass in.
    seen: list[str] = []
    for r in per_case_rows:
        if r["method"] not in seen:
            seen.append(r["method"])
    fault_order = sorted({r["fault"] for r in per_case_rows})
    for method in seen:
        for fault in fault_order:
            rs = by_method_fault.get((method, fault), [])
            if not rs:
                continue
            agg = cc.summarize(rs)
            per_method[method]["per_fault"][fault] = agg
            summary_rows.append({
                "method": method,
                "fault": fault,
                "n_cases": len(rs),
                "ece": agg["ece"],
                "mean_confidence": agg["mean_confidence"],
                "mean_accuracy": agg["mean_accuracy"],
                "overconfidence_bins": agg["overconfidence_bins"],
                "underconfidence_bins": agg["underconfidence_bins"],
            })

    return summary_rows, per_method


def spearman(rows: list[dict[str, Any]], x_key: str, y_key: str) -> float:
    """Tie-aware Spearman rank correlation between two per-row columns.

    Duplicated from :func:`run_phase2_ec.spearman` per the established
    convention that the weekly run scripts stay independent until 3+
    weeks share enough code to factor.
    """
    n = len(rows)
    if n < 2:
        return float("nan")
    pairs = [(r[x_key], r[y_key]) for r in rows]

    def _ranks(values: list[float]) -> list[float]:
        indexed = sorted(enumerate(values), key=lambda kv: kv[1])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(indexed):
            j = i
            while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    x_ranks = _ranks([float(p[0]) for p in pairs])
    y_ranks = _ranks([float(p[1]) for p in pairs])
    mean_x = statistics.mean(x_ranks)
    mean_y = statistics.mean(y_ranks)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_ranks, y_ranks))
    den_x = sum((x - mean_x) ** 2 for x in x_ranks) ** 0.5
    den_y = sum((y - mean_y) ** 2 for y in y_ranks) ** 0.5
    if den_x == 0.0 or den_y == 0.0:
        return float("nan")
    return num / (den_x * den_y)


# ---- IO -------------------------------------------------------------------


_SUMMARY_FIELDNAMES = (
    "method", "fault", "n_cases", "ece",
    "mean_confidence", "mean_accuracy",
    "overconfidence_bins", "underconfidence_bins",
)


#: Per-case CSV columns. Persisted so the Week 5 integration loader
#: can compute ``ece_proxy = |confidence − correct|`` per case without
#: re-running the CC harness. ``confidence`` is the routed field
#: (BARO ``peak_confidence``; others ``confidence``) — same scale ECE
#: bucketing uses.
_PER_CASE_FIELDNAMES = (
    "method", "case_id", "fault", "confidence", "correct", "cal_error",
)


def write_csv(summary_rows: list[dict[str, Any]], path: Path) -> None:
    """Write the (method, fault) summary table to ``path``.

    The CSV is the same shape as the brief specifies and matches the
    ``ALL`` per-method aggregate convention used in Week 3's
    bucketed CSV.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(_SUMMARY_FIELDNAMES),
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(summary_rows)


def write_per_case_csv(
    per_case_rows: list[dict[str, Any]], path: Path,
) -> None:
    """Write the per-(method, case) calibration columns to ``path``.

    Companion CSV to the aggregate summary. Week 5's integration
    loader joins this on (method, case_id) with
    ``phase2_explanation_completeness.csv`` to recover per-case AC@1
    / SG / SC / EC alongside per-case confidence / ece_proxy.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(_PER_CASE_FIELDNAMES),
            extrasaction="ignore",
        )
        w.writeheader()
        w.writerows(per_case_rows)


def _fmt_float(x: float, width: int = 6, precision: int = 3) -> str:
    if math.isnan(x):
        return f"{'nan':>{width}}"
    return f"{x:>{width}.{precision}f}"


def print_summary(
    per_method: dict[str, dict[str, Any]],
    correlations: dict[str, float],
    method_order: list[str] | None = None,
) -> None:
    """Print the Week-4 console summary: per-method ECE table,
    per-fault ECE matrix, reliability-diagram text dump, Spearman
    correlations, and alarm gates.
    """
    method_order = method_order or [
        "MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP",
    ]

    # ---- per-method headline table ----
    print(f"\n{'Method':<10} {'n':>5} {'ECE':>7} {'meanC':>7} {'meanA':>7} "
          f"{'SG':>7} {'SC':>7} {'EC':>7} {'over':>5} {'under':>6}")
    print("-" * 80)
    for m in method_order:
        if m not in per_method:
            continue
        r = per_method[m]
        print(
            f"{m:<10} {r['n']:>5} "
            f"{_fmt_float(r['ece'])} "
            f"{_fmt_float(r['mean_confidence'])} "
            f"{_fmt_float(r['mean_accuracy'])} "
            f"{_fmt_float(r['sg_mean'])} "
            f"{_fmt_float(r['sc_mean'])} "
            f"{_fmt_float(r['ec_mean'])} "
            f"{r['overconfidence_bins']:>5} "
            f"{r['underconfidence_bins']:>6}"
        )

    # ---- per-fault ECE matrix ----
    faults = sorted({
        f for m in per_method.values() for f in m["per_fault"]
    })
    if faults:
        header = "  ".join(f"{f:>7}" for f in faults)
        print(f"\nPer-fault ECE (lower better):")
        print(f"{'Method':<10} {header}")
        print("-" * (12 + len(faults) * 9))
        for m in method_order:
            if m not in per_method:
                continue
            cells = []
            for f in faults:
                v = per_method[m]["per_fault"].get(f, {}).get("ece", math.nan)
                cells.append(_fmt_float(v, width=7))
            print(f"{m:<10} {'  '.join(cells)}")

    # ---- reliability-diagram dump (textual) ----
    print("\nReliability diagrams (bin centers 0.05, 0.15, ... 0.95):")
    for m in method_order:
        if m not in per_method:
            continue
        diag = per_method[m]["reliability"]
        print(f"\n  {m}:")
        print(f"    {'bin':>7} {'count':>6} {'avgC':>7} {'acc':>7}")
        for i, c in enumerate(diag["bin_centers"]):
            count = diag["bin_counts"][i]
            if count == 0:
                continue
            print(
                f"    {c:>7.2f} {count:>6} "
                f"{_fmt_float(diag['bin_avg_confidence'][i])} "
                f"{_fmt_float(diag['bin_accuracy'][i])}"
            )
        print(
            f"    over={diag['overconfidence_bins']}  "
            f"under={diag['underconfidence_bins']}"
        )

    # ---- correlations ----
    n_pairs = sum(per_method[m]["n"] for m in per_method)
    print(f"\nSpearman rank correlations over all {n_pairs} case-method pairs:")
    print(f"  ρ(AC@1, cal_error) = {correlations['ac1']:+.3f}   "
          f"(predict negative)")
    print(f"  ρ(SG,   cal_error) = {correlations['sg']:+.3f}   "
          f"(predict near zero)")
    print(f"  ρ(SC,   cal_error) = {correlations['sc']:+.3f}   "
          f"(predict near zero)")
    print(f"  ρ(EC,   cal_error) = {correlations['ec']:+.3f}   "
          f"(predict near zero)")

    # ---- alarm gates (from brief Step 5 predicted bands) ----
    print("\nAlarm gates (predicted ECE bands from brief):")
    bands: dict[str, tuple[float, float]] = {
        "BARO":     (0.05, 0.20),
        "FODA-FCP": (0.10, 0.25),
        "MR":       (0.20, 0.45),
        "CR":       (0.20, 0.45),
        "Micro":    (0.20, 0.45),
        "DejaVu":   (0.15, 0.45),
        "yRCA":     (0.10, 0.40),
    }
    for m in method_order:
        if m not in per_method:
            continue
        ece = per_method[m]["ece"]
        lo, hi = bands[m]
        if math.isnan(ece):
            print(f"  ? {m} ECE = nan")
        elif ece > 0.50:
            print(f"  ⚠ {m} ECE = {ece:.3f} > 0.50 — out of all predicted bands")
        elif lo <= ece <= hi:
            print(f"  ✓ {m} ECE = {ece:.3f} ∈ [{lo:.2f}, {hi:.2f}]")
        else:
            print(f"  ⚠ {m} ECE = {ece:.3f} outside predicted [{lo:.2f}, {hi:.2f}]")


def _compute_correlations(per_case_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Spearman of per-case cal_error vs each per-case metric.

    The brief's Step 4 specifies these four signs:
    ρ(AC@1, ECE) negative; ρ(SG/SC/EC, ECE) near zero. Here we
    correlate against ``cal_error`` (the per-case proxy) — sign of
    ρ(AC@1, cal_error) should be negative because high AC@1 (=
    correct=1) cases are exactly the ones where cal_error = 1−conf is
    small (high-conf cases) or 1−0=1 (low-conf cases), so on average
    correctness suppresses cal_error.
    """
    return {
        "ac1": spearman(per_case_rows, "ac1", "cal_error"),
        "sg":  spearman(per_case_rows, "sg",  "cal_error"),
        "sc":  spearman(per_case_rows, "sc",  "cal_error"),
        "ec":  spearman(per_case_rows, "ec_overall", "cal_error"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, required=True,
        help="path to RCAEval data root (e.g. ~/datasets/rcaeval/RE1/RE1-OB)",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path("results/phase2_confidence_calibration.csv"),
    )
    parser.add_argument(
        "--per-case-out", type=Path,
        default=Path("results/phase2_confidence_calibration_per_case.csv"),
        help=(
            "per-(method, case) CSV with confidence + correct + cal_error. "
            "Consumed by the Week 5 integration loader."
        ),
    )
    parser.add_argument(
        "--n-bins", type=int, default=_DEFAULT_N_BINS,
        help="number of ECE bins (default: 10, matches Guo et al. 2017)",
    )
    args = parser.parse_args(argv)

    cc = ConfidenceCalibration(n_bins=args.n_bins)
    per_case_rows, summary_rows, per_method = evaluate(
        args.data.expanduser(), cc=cc,
    )
    write_csv(summary_rows, args.out)
    write_per_case_csv(per_case_rows, args.per_case_out)
    correlations = _compute_correlations(per_case_rows)
    print_summary(per_method, correlations)
    print(f"\nWrote {len(summary_rows)} (method, fault) summary rows to {args.out}")
    print(f"Wrote {len(per_case_rows)} per-case rows to {args.per_case_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
