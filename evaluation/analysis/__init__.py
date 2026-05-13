"""Cross-week integration utilities for Paper 6 Phase 2.

Weeks 1-4 each produced one metric and one harness CSV. Week 5 stitches
them into:

* A unified per-(method, case) DataFrame (:func:`load_all_phase2_results`).
* A 7-method × 5-metric headline table.
* Four AC@1-vs-semantic-metric scatter plots.
* A 5×5 Spearman correlation matrix (overall + per-method).

Source CSVs live in ``results/``; artefacts (PNGs, MD tables) land in
``paper/artifacts/`` and ``results/``.
"""

from .load_phase2_results import load_all_phase2_results

__all__ = ["load_all_phase2_results"]
