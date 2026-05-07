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
- `BoutiqueLoader`
- `Foda12Loader`

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

### Online Boutique

Source: <https://github.com/GoogleCloudPlatform/microservices-demo>

Online Boutique itself does not ship a benchmark — we capture our own
fault-injection runs (chaos-mesh + Prometheus) and persist them as one folder
per case. `BoutiqueLoader` accepts the same per-case folder layout as
`RCAEvalLoader` so the two are interchangeable. Two formats are supported per
case:

1. **Combined CSV** (`simple_metrics.csv` / `data.csv` / `metrics.csv`) —
   identical to the RCAEval layout.
2. **Per-service CSVs** (`{service}_metrics.csv`) — merged on the `time`
   column. Use this when scraping Prometheus per pod.

If a case includes a `manifest.json`, its `root_cause` and `fault_type`
fields override the directory-name parser, and an optional `topology`
field is passed through to `BenchmarkCase.system_topology`. This is the
preferred path once chaos-mesh capture lands, since it removes any naming
constraint on case folders.

```python
from evaluation.benchmarks.boutique_loader import BoutiqueLoader

loader = BoutiqueLoader("~/datasets/boutique-chaos/run-2026-05/")
for case in loader.iter_cases():
    print(case.id, case.ground_truth_root_cause, case.system_topology)
```

### FODA-12

The 12-scenario synthetic benchmark used in our paper. The authoritative
definition still lives in Java
(`fuzzy-rca-engine/src/main/java/com/foda/rca/evaluation/SyntheticScenarioBuilder.java`);
`Foda12Loader` consumes an export of those scenarios in this format:

```
foda12/
  S01/
    case.json     # required
    metrics.csv   # required
  S09/
    ...
```

Where `case.json` looks like:

```json
{
  "id": "S01",
  "name": "LATENCY_FANOUT",
  "fault_type": "LATENCY_ANOMALY",
  "ground_truth_root_cause": "service-A",
  "ontology_mapping": {
    "service-A": "http://foda.example.org/onto#LatencyFault",
    "service-B": "http://foda.example.org/onto#NormalOperation"
  },
  "topology": { "service-A": ["service-B"], "service-B": [] },
  "inject_time": 1700000020
}
```

What makes FODA-12 distinct from the other benchmarks is that
`ontology_mapping` is **required**, not optional. Every scenario annotates
each service in its topology with an ontology class URI so that
ontology-aware methods (FODA-FCP) and explanation-quality metrics
(semantic groundedness, semantic coherence) have something concrete to
reason against. The mapping flows through unchanged into
`BenchmarkCase.ontology_mapping`.

The Java→disk export pipeline is tracked separately; until it lands, see
`evaluation/tests/fixtures/foda12_fake/` for two synthetic cases that match
the on-disk schema.
