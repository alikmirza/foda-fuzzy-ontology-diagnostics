# fuzzy-rca-engine — FCP-RCA Implementation

**Fuzzy Confidence Propagation Root Cause Analysis (FCP-RCA)**
Research module for the FODA project — microservice fault localisation via
fuzzy inference and weighted graph propagation.

---

## Paper–Code Mapping

This module implements the algorithm described in **Section 3** of the paper.
The table below maps each paper section to the corresponding Java source.

| Paper section | Description | Java class(es) |
|---|---|---|
| §3.1 Fuzzification | Trapezoidal/triangular membership functions; metric → fuzzy vector | `FaultFuzzifierImpl`, `TrapezoidalMF`, `TriangularMF` |
| §3.2 Fault Inference | Mamdani IF-THEN rules; firing strength, max-aggregation | `MamdaniFuzzyRuleEngine`, `FuzzyRule` |
| §3.3 Confidence Propagation | Noisy-OR backward propagation; damping factor δ | `WeightedConfidencePropagator`, `DampedConfidencePropagator` |
| §3.3.2 Cycle-safe propagation | Jacobi fixed-point iteration for cyclic graphs (Eq. 5) | `IterativeConfidencePropagator` |
| §3.3 Auto-selection | Runtime DAG vs. cyclic graph detection | `AdaptiveConfidencePropagator`, `ServiceDependencyGraph#hasCycle()` |
| §3.4 Ranking | Top-k cause ranking with threshold filtering | `TopKCauseRanker`, `CauseRanker` |
| §3.5 Explanation | Natural-language explanation generation | `NaturalLanguageExplanationBuilder` |
| §4 Pipeline | Orchestrating 5-phase pipeline | `FuzzyRcaEngineImpl` |
| §5.1 Benchmark | Synthetic fault-injection scenarios (FODA-8) | `SyntheticScenarioBuilder` |
| §5.2 Metrics | P@k, R@k, MRR, NDCG@k evaluation | `RcaEvaluator` |
| §5.3 Ablation | LocalOnly, UniformWeight, MaxPropagation baselines | `LocalOnlyPropagator`, `UniformWeightPropagator`, `MaxPropagationBaseline` |
| §5.4 Rule base | Externalisable YAML rule file | `FuzzyRuleLoader`, `rca-rules.yaml` |

---

## FCP-RCA Algorithm — Pseudocode

```
Algorithm FCP-RCA(M, G, k, δ, ε, MAX_ITER):

  Input:
    M = {m_1, ..., m_n}          -- service metric observations
    G = (S, E, W)                 -- weighted dependency graph; edge (s→t) means s calls t
    k                             -- number of top root-cause candidates to return
    δ ∈ (0, 1]                   -- damping factor (default 0.85)
    ε > 0                        -- iterative convergence threshold (default 1e-6)
    MAX_ITER                      -- maximum Jacobi iterations (default 100)

  Output:
    ranked_causes = [(s, C(s), explanation)] — top-k candidates, highest C first

  ── Phase 1: Fuzzification (§3.1) ───────────────────────────────────────────
  for each m_i in M:
    v_i ← fuzzify(m_i)           -- maps cpu, latency, memory, errorRate, throughput
                                  -- to fuzzy labels via trapezoidal/triangular MFs

  ── Phase 2: Mamdani Fault Inference (§3.2) ─────────────────────────────────
  for each service s ∈ S:
    for each rule r in rule_base:
      α_r ← CF_r × min{ v_s(a) : a ∈ antecedents(r) }  -- Eq. 2 (min-conjunction)
    H(s) ← max{ α_r : rules fired }                      -- Eq. 3 (max-aggregation)
    category(s) ← argmax_cat { α_r : consequent(r) = cat }

  ── Phase 3: Confidence Propagation (§3.3) ──────────────────────────────────
  if G is acyclic:                -- detected via topological sort
    C ← DampedPropagation(H, G, δ)        -- exact O(|S|+|E|) pass (Eq. 4)
  else:
    C ← IterativePropagation(H, G, δ, ε, MAX_ITER)  -- Jacobi (Eq. 5)

  DampedPropagation(H, G, δ):
    C ← copy(H)
    for each s in reverse_topological_order(G):   -- leaf callees first
      P(s) ← 1 – ∏_{t ∈ callees(s)} (1 – C(t) × w(s,t) × δ)   -- Eq. 4a
      C(s) ← 1 – (1 – H(s)) × (1 – P(s))                        -- Eq. 4b
    return C

  IterativePropagation(H, G, δ, ε, MAX_ITER):
    C⁰(s) ← H(s)   for all s
    for k = 1, 2, ..., MAX_ITER:
      C_prev ← snapshot(C^(k-1))          -- Jacobi: use full previous snapshot
      for each s ∈ S:
        P(s) ← 1 – ∏_{t ∈ callees(s)} (1 – C_prev(t) × w(s,t) × δ)   -- Eq. 5a
        C^k(s) ← 1 – (1 – H(s)) × (1 – P(s))                           -- Eq. 5b
      if max_s |C^k(s) – C_prev(s)| ≤ ε: break
    return C^k

  ── Phase 4: Top-k Ranking (§3.4) ───────────────────────────────────────────
  candidates ← { s ∈ S : C(s) > threshold }   -- threshold = 0.10
  ranked_causes ← sort(candidates, key=C, descending)[:k]
  for each cause in ranked_causes:
    cause.causal_path ← backtrack(cause, C, G)  -- greedy highest-confidence path

  ── Phase 5: Explanation Generation (§3.5) ──────────────────────────────────
  for each cause in ranked_causes:
    cause.explanation ← generate_nl_explanation(cause, v_s, H(s), C(s))

  return ranked_causes
```

---

## Edge Semantics

An edge `u → v` in `ServiceDependencyGraph` encodes:

> **`u` calls `v`** — weight `w(u,v)` is the probability that a fault at `v` (the callee)
> manifests as observable symptoms at `u` (the caller).

Fault confidence therefore propagates **backward** (from callees toward callers):

```
Topology:   gateway → order-svc → db-svc
                               (fault here)

Propagation: db-svc ←── order-svc ←── gateway
             C=0.90      C=0.78        C=0.65   (decreasing with each hop + damping)
```

This is the opposite of the call-flow direction and is the core insight of RCA:
*find the service that is causing symptoms in its callers*.

---

## Reproducing the Paper Experiments (Section 5)

### Prerequisites

```bash
# Java 17, Maven 3.9+
cd fuzzy-rca-engine
mvn clean test --no-transfer-progress
```

### Full benchmark comparison (Table 4)

```java
import com.foda.rca.core.FuzzyRcaEngineImpl;
import com.foda.rca.evaluation.*;
import com.foda.rca.propagation.*;
import java.nio.file.Path;
import java.util.*;

// 1. Define algorithms under comparison
Map<String, FuzzyRcaEngine> algorithms = new LinkedHashMap<>();
algorithms.put("FCP-RCA",      FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build());
algorithms.put("-Damping",     FuzzyRcaEngineImpl.builder().withDampingFactor(1.0).build());
algorithms.put("-Propagation", FuzzyRcaEngineImpl.builder().propagator(new LocalOnlyPropagator()).build());
algorithms.put("-Weights",     FuzzyRcaEngineImpl.builder().propagator(new UniformWeightPropagator(0.85)).build());
algorithms.put("+MaxProp",     FuzzyRcaEngineImpl.builder().propagator(new MaxPropagationBaseline()).build());

// 2. Load benchmark scenarios (FODA-8 — Section 5.1, Table 3)
List<GroundTruthScenario> suite = SyntheticScenarioBuilder.standardBenchmarkSuite();

// 3. Run evaluation (k=3)
RcaEvaluator evaluator = new RcaEvaluator();
Map<String, AggregatedEvaluation> results = evaluator.compare(algorithms, suite, 3);

// 4. Print LaTeX table (Table 4) and write CSV to target/
System.out.println(evaluator.toLatexTable(results));
evaluator.writeCsv(results, Path.of("target"));
evaluator.writePerScenarioCsv(results, Path.of("target"));
```

Output files:
- `target/rca-results.csv` — aggregated metrics (one row per algorithm)
- `target/rca-per-scenario.csv` — per-scenario metrics (one row per algorithm × scenario)

### Single diagnosis call

```java
FuzzyRcaEngine engine = FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build();

DiagnosisResult result = engine.diagnose(
    observations,      // List<ServiceMetrics>
    dependencyGraph,   // ServiceDependencyGraph
    3                  // top-3 candidates
);

result.getRankedCauses().forEach(cause ->
    System.out.printf("[%d] %s  C=%.3f  %s%n",
        cause.getRank(), cause.getServiceId(),
        cause.getFinalConfidence(), cause.getExplanation()));
```

### Using the YAML rule base

```java
// Load rules from rca-rules.yaml (reproducible, version-controlled)
FuzzyRuleEngine engine = MamdaniFuzzyRuleEngine.fromYaml();

// Or from a custom rule file for sensitivity analysis
FuzzyRuleEngine custom = MamdaniFuzzyRuleEngine.fromYaml("my-ablation-rules.yaml");
```

---

## Module Structure

```
fuzzy-rca-engine/
├── src/main/java/com/foda/rca/
│   ├── api/                   FuzzyRcaEngine (public interface)
│   ├── core/                  FuzzyRcaEngineImpl (pipeline orchestrator)
│   ├── model/                 ServiceMetrics, FuzzyVector, FaultHypothesis,
│   │                          ServiceDependencyGraph, RankedCause, DiagnosisResult
│   ├── fuzzification/         TrapezoidalMF, TriangularMF, FaultFuzzifierImpl   (§3.1)
│   ├── inference/             FuzzyRule, MamdaniFuzzyRuleEngine, FuzzyRuleLoader (§3.2)
│   ├── propagation/           WeightedConfidencePropagator                       (§3.3)
│   │                          DampedConfidencePropagator    (Eq. 4)
│   │                          IterativeConfidencePropagator (Eq. 5)
│   │                          AdaptiveConfidencePropagator  (auto-select)
│   │                          LocalOnlyPropagator, UniformWeightPropagator       (ablation)
│   │                          MaxPropagationBaseline                             (ablation)
│   ├── ranking/               TopKCauseRanker                                    (§3.4)
│   ├── explanation/           NaturalLanguageExplanationBuilder                  (§3.5)
│   └── evaluation/            RcaEvaluator, SyntheticScenarioBuilder,            (§5)
│                              GroundTruthScenario, ScenarioEvaluation,
│                              AggregatedEvaluation
├── src/main/resources/
│   └── rca-rules.yaml         Externalisable rule base (20 rules, 8 categories)  (§3.2)
└── src/test/java/com/foda/rca/
    ├── fuzzification/         TrapezoidalMFTest, FaultFuzzifierImplTest
    ├── inference/             MamdaniFuzzyRuleEngineTest, FuzzyRuleLoaderTest
    ├── propagation/           WeightedConfidencePropagatorTest,
    │                          DampedConfidencePropagatorTest,
    │                          IterativeConfidencePropagatorTest,
    │                          AdaptiveConfidencePropagatorTest,
    │                          MaxPropagationBaselineTest
    ├── core/                  FuzzyRcaEngineIntegrationTest
    └── evaluation/            RcaEvaluatorTest
```

---

## Key Parameters

| Parameter | Default | Description |
|---|---|---|
| `δ` (dampingFactor) | 0.85 | Per-hop attenuation; higher = less attenuation |
| `ε` (epsilon) | 1e-6 | Jacobi convergence threshold |
| `MAX_ITER` | 100 | Maximum Jacobi iterations |
| `k` | 3 | Number of top-k candidates to rank and explain |
| Ranking threshold | 0.10 | Minimum C(s) to be considered a candidate |

The damping factor δ = 0.85 was selected by grid search over {0.70, 0.75, 0.80, 0.85, 0.90}
on the FODA-8 benchmark, maximising mean MRR (Section 5.2).

---

## Certainty Factors and Rule Calibration

Rule CFs in `rca-rules.yaml` were calibrated from published microservice RCA benchmarks
(Chen et al. 2019; Ma et al. 2020). To perform sensitivity analysis:

1. Edit `rca-rules.yaml` (adjust CFs or add/remove rules).
2. Re-run: `mvn test -pl fuzzy-rca-engine --no-transfer-progress`
3. Compare MRR/NDCG@3 output from `RcaEvaluatorTest` against the baseline in Table 4.

---

## References

- Chen, P. et al. (2019). *Outage Prediction and Diagnosis for Cloud Service Systems*.
  WWW'19.
- Ma, M. et al. (2020). *Diagnosing Root Causes of Intermittent Slow Queries in Cloud
  Databases*. VLDB'20.
- Ikram, A. et al. (2022). *Root Cause Analysis of Failures in Microservices through
  Causal Discovery*. NeurIPS'22.
