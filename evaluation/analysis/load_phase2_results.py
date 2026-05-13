"""Unified per-(method, case) loader for Paper 6 Phase 2 results.

Stitches two persisted CSVs into a single 875-row DataFrame:

* ``results/phase2_explanation_completeness.csv`` — the Week 3 EC
  harness already joined per-case ``ac1``, ``sg``, ``sc``, and
  ``ec_overall`` for all seven methods × 125 cases.
* ``results/phase2_confidence_calibration_per_case.csv`` — the Week 4
  CC harness's per-case ``confidence``, ``correct``, and ``cal_error``
  (where ``cal_error = |confidence − target|`` is the Brier-style proxy
  used for per-case Spearman; see DEVIATIONS.md → ConfidenceCalibration
  metric).

The join is on ``(method, case_id)``. Output columns:

    method, case_id, fault,
    ac1, sg, sc, ec, ece_proxy,
    confidence, correct

Aggregate ECE per method is **not** in this DataFrame — ECE is a
population property, not per-case, and lives in
``results/phase2_confidence_calibration.csv``'s ``ALL`` rows.
:func:`load_aggregate_ece` exposes it.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


#: Default results-directory anchor. Resolved relative to the repo
#: root so the loader works whether called from the package or a
#: notebook in ``paper/``.
_DEFAULT_RESULTS_DIR = (
    Path(__file__).resolve().parents[2] / "results"
)


def load_all_phase2_results(
    results_dir: Path | None = None,
) -> pd.DataFrame:
    """Return a per-(method, case) DataFrame joining EC + CC outputs.

    Columns (in this order):

    * ``method`` — one of MR / CR / Micro / BARO / DejaVu / yRCA / FODA-FCP.
    * ``case_id`` — RE1-OB case identifier.
    * ``fault`` — fault type (cpu / mem / disk / delay / loss).
    * ``ac1`` — 0.0 / 1.0 (the method's top-1 prediction matches GT).
    * ``sg`` — SemanticGroundedness score in [0, 1].
    * ``sc`` — SemanticCoherence score in [0, 1].
    * ``ec`` — ExplanationCompleteness in {0, 1/3, 2/3, 1}.
    * ``ece_proxy`` — per-case ``|confidence − correct|`` in [0, 1].
      A per-case Brier-style proxy for calibration; the aggregate ECE
      is **not** decomposable per-case and is loaded separately via
      :func:`load_aggregate_ece`.
    * ``confidence`` — method-specific confidence routed per the Week 4
      rule (BARO ``peak_confidence``; others ``confidence``).
    * ``correct`` — bool (``ac1 == 1.0``).

    Raises ``RuntimeError`` if the join doesn't produce exactly 875
    rows or any column carries NaN — both signal a stale CSV that
    needs regenerating by the upstream harness.
    """
    results_dir = (results_dir or _DEFAULT_RESULTS_DIR).expanduser()

    ec_path = results_dir / "phase2_explanation_completeness.csv"
    cc_path = results_dir / "phase2_confidence_calibration_per_case.csv"
    if not ec_path.exists():
        raise FileNotFoundError(
            f"missing {ec_path} — run "
            "`python -m evaluation.experiments.run_phase2_ec`"
        )
    if not cc_path.exists():
        raise FileNotFoundError(
            f"missing {cc_path} — run "
            "`python -m evaluation.experiments.run_phase2_cc`"
        )

    ec = pd.read_csv(ec_path)
    cc = pd.read_csv(cc_path)

    # Rename EC's `ec_overall` to `ec` for the headline-table column.
    ec = ec.rename(columns={"ec_overall": "ec"})

    # Inner-join on (method, case_id). CC carries confidence + cal_error;
    # EC carries ac1 + sg + sc + ec. Fault is on both; prefer EC's copy.
    merged = ec.merge(
        cc[["method", "case_id", "confidence", "correct", "cal_error"]],
        on=["method", "case_id"],
        how="inner",
        validate="one_to_one",
    )

    merged["ece_proxy"] = merged["cal_error"]
    merged["correct"] = merged["correct"].astype(bool)

    out = merged[[
        "method", "case_id", "fault",
        "ac1", "sg", "sc", "ec",
        "ece_proxy",
        "confidence", "correct",
    ]].copy()

    _validate(out)
    return out


def load_aggregate_ece(
    results_dir: Path | None = None,
) -> pd.DataFrame:
    """Return a per-method DataFrame of aggregate ECE values.

    Loads ``ALL`` (per-method) rows from
    ``phase2_confidence_calibration.csv``. Columns:

    * ``method``
    * ``ece`` — aggregate ECE across all 125 cases for the method.
    * ``mean_confidence``, ``mean_accuracy`` — per-method aggregates.
    * ``overconfidence_bins``, ``underconfidence_bins`` — bin counters.

    Why a separate function: ECE is mathematically aggregate (see
    DEVIATIONS.md → "Aggregate-only contract"). The headline-table
    builder consumes this; the per-case loader does not.
    """
    results_dir = (results_dir or _DEFAULT_RESULTS_DIR).expanduser()
    cc_path = results_dir / "phase2_confidence_calibration.csv"
    if not cc_path.exists():
        raise FileNotFoundError(
            f"missing {cc_path} — run "
            "`python -m evaluation.experiments.run_phase2_cc`"
        )
    df = pd.read_csv(cc_path)
    return df[df["fault"] == "ALL"][[
        "method", "ece", "mean_confidence", "mean_accuracy",
        "overconfidence_bins", "underconfidence_bins",
    ]].reset_index(drop=True)


# ---- validation -----------------------------------------------------------


_EXPECTED_METHODS: frozenset[str] = frozenset({
    "MR", "CR", "Micro", "BARO", "DejaVu", "yRCA", "FODA-FCP",
})
_EXPECTED_TOTAL_ROWS: int = 875
_EXPECTED_PER_METHOD: int = 125
_METRIC_COLUMNS: tuple[str, ...] = (
    "ac1", "sg", "sc", "ec", "ece_proxy", "confidence",
)


def _validate(df: pd.DataFrame) -> None:
    """Loud-failure invariants. A mismatch always means a stale CSV."""
    if len(df) != _EXPECTED_TOTAL_ROWS:
        raise RuntimeError(
            f"joined dataframe has {len(df)} rows, expected "
            f"{_EXPECTED_TOTAL_ROWS} (7 methods × 125 cases) — one of "
            "the source CSVs is stale"
        )
    methods = set(df["method"].unique())
    if methods != _EXPECTED_METHODS:
        missing = _EXPECTED_METHODS - methods
        extra = methods - _EXPECTED_METHODS
        raise RuntimeError(
            f"method set mismatch: missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    counts = df.groupby("method").size()
    bad = counts[counts != _EXPECTED_PER_METHOD]
    if len(bad) > 0:
        raise RuntimeError(
            f"per-method case counts must be {_EXPECTED_PER_METHOD}; "
            f"got {bad.to_dict()}"
        )
    for col in _METRIC_COLUMNS:
        nans = df[col].isna().sum()
        if nans > 0:
            raise RuntimeError(
                f"column {col!r} has {nans} NaN entries — "
                "source CSVs disagree on (method, case_id) coverage"
            )
    if not df["ece_proxy"].between(0.0, 1.0).all():
        bad_rows = df[~df["ece_proxy"].between(0.0, 1.0)]
        raise RuntimeError(
            f"ece_proxy must be in [0, 1]; {len(bad_rows)} rows out of "
            f"range (first: {bad_rows.iloc[0].to_dict()})"
        )
