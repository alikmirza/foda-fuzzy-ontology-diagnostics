# FODA Evaluation Framework

Cross-method, cross-benchmark evaluation harness for the FODA fuzzy-ontology
diagnostics paper.

## Layout

- `benchmarks/` — loaders for RCAEval, Online Boutique, and FODA-12.
- `methods/` — wrappers around baseline RCA methods (MonitorRank, CausalRCA,
  MicroRCA, DejaVu, YRCA, BARO) and the FODA FCP-RCA method under test.
- `metrics/` — ranking metrics (AC@k, MRR) and the explanation-quality metrics
  introduced in the paper (semantic groundedness, coherence, completeness,
  confidence calibration).
- `extraction/` — canonical explanation graph types and ontology-mapping
  utilities used to normalize each method's output into a common form.
- `experiments/` — top-level orchestration and post-hoc analysis.
- `tests/` — unit tests.

## Running

```bash
pip install -e evaluation
pytest evaluation/tests/
```

## Status

This package is being filled in incrementally. Implemented today:
- canonical explanation types
- ranking metrics (AC@k, MRR)

Everything else is a typed placeholder that raises `NotImplementedError`.
