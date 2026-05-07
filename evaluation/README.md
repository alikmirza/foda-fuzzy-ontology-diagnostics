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

This package is being filled in incrementally. Implemented:
- canonical explanation types
- ranking metrics (AC@k, MRR)
- `RCAEvalLoader`

Everything else is a typed placeholder that raises `NotImplementedError`.

## Datasets

Benchmark data is **not** committed to this repo — the RCAEval archives alone
are several GB. Download them yourself and point each loader at the extracted
directory.

### RCAEval

Source: <https://github.com/phamquiluan/RCAEval>

The official utilities `download_re1_dataset()`, `download_re2_dataset()`, and
`download_re3_dataset()` (or the GitHub release archives) extract one folder
per case named `{prefix}_{service}_{fault}_{instance}` — for example
`OB_cartservice_CPU_1`. Each case folder contains a metrics file
(`simple_metrics.csv`, `data.csv`, `metrics.csv`, or `metrics.json`) and an
`inject_time.txt` Unix timestamp.

Suggested layout — drop the extracted folders anywhere outside the repo and
pass that path to the loader:

```
~/datasets/rcaeval/RE1/
  OB_cartservice_CPU_1/
    simple_metrics.csv
    inject_time.txt
  OB_cartservice_MEM_1/
    ...
```

```python
from evaluation.benchmarks.rcaeval_loader import RCAEvalLoader

loader = RCAEvalLoader("~/datasets/rcaeval/RE1")
print(len(loader))
for case in loader.iter_cases():
    print(case.id, case.ground_truth_root_cause, case.ground_truth_fault_type)
```

`evaluation/tests/fixtures/rcaeval_fake/` ships two tiny synthetic cases (one
per metrics-file format) so the loader's tests do not depend on the real data.

### Online Boutique / FODA-12

Loaders are placeholders; download instructions will land with the
implementation.
