# FCP-RCA Evaluation Results

Reproducible benchmark output for the Fuzzy Confidence Propagation Root Cause Analysis
(FCP-RCA) engine, intended for inclusion in the Scopus journal paper (Section 5,
Table 4 reproduction).

## 1. Run metadata

- **Date executed:** 2026-04-29
- **Module:** `fuzzy-rca-engine` (1.0.0-SNAPSHOT)
- **Repository:** `github.com/alikmirza/foda-fuzzy-ontology-diagnostics` @ branch `main`
- **OS:** Linux 6.17.0-20-generic (x86_64)
- **JDK:** OpenJDK 21.0.10 (Ubuntu 24.04 build, target bytecode = Java 17)
- **Maven:** Apache Maven 3.8.7
- **Commit baseline:** `778e101` (Phase 7: FCP-RCA fuzzy root cause analysis engine)

## 2. Test execution summary

| Phase                       | Command                              | Result                                |
|-----------------------------|--------------------------------------|---------------------------------------|
| Compilation                 | `mvn clean compile`                  | **BUILD SUCCESS** (34 sources)        |
| Unit + integration tests    | `mvn test`                           | **119 passed, 0 failed, 0 skipped**   |
| Benchmark execution         | `mvn test -Dtest=BenchmarkRunner`    | **1 passed** (FODA-8 suite, k=3)      |

No tests were disabled, no calibration drift was observed, and no algorithm code,
rule weights, or test assertions were modified during this run. `CALIBRATION_DRIFT.md`
is therefore not produced.

## 3. Aggregated results — FODA-8 benchmark, k=3

Source: `target/rca-results.csv` (verbatim).

| Algorithm    | P@3   | std    | R@3   | std   | MRR   | std    | NDCG@3 | std    | Top-1 Acc. |
|--------------|------:|-------:|------:|------:|------:|-------:|-------:|-------:|-----------:|
| FCP-RCA      | 0.438 | 0.295  | 1.000 | 0.000 | 0.875 | 0.354  | 0.875  | 0.354  | 0.875      |
| -Damping     | 0.438 | 0.295  | 1.000 | 0.000 | 0.875 | 0.354  | 0.875  | 0.354  | 0.875      |
| -Propagation | 0.875 | 0.354  | 1.000 | 0.000 | 0.875 | 0.354  | 0.875  | 0.354  | 0.875      |
| -Weights     | 0.438 | 0.295  | 1.000 | 0.000 | 0.813 | 0.372  | 0.829  | 0.359  | 0.750      |
| +MaxProp     | 0.438 | 0.295  | 1.000 | 0.000 | 0.875 | 0.354  | 0.875  | 0.354  | 0.875      |

(Standard deviations are sample std with Bessel correction, n=8 scenarios. The
healthy-baseline scenario S08 contributes a 0 to MRR and NDCG by construction —
empty ground truth — and explains the ~0.354 std seen across all algorithms.)

## 4. Per-algorithm interpretation

- **FCP-RCA** (δ=0.85, adaptive propagator): MRR = 0.875, NDCG@3 = 0.875, Top-1
  accuracy = 0.875. Tied for the best ranking quality among all five algorithms;
  the only scenario it does not solve top-1 is S08 (healthy baseline, empty truth set).
- **-Damping** (δ=1.0, no damping): identical aggregate metrics to FCP-RCA on this
  suite. The standard FODA-8 topology is short (≤ 2 hops from leaf to root), so
  damping does not change the top-1 candidate; on a deeper or cyclic topology this
  ablation is expected to diverge.
- **-Propagation** (LocalOnlyPropagator, no graph propagation): paradoxically reports
  the highest P@3 = 0.875 because it returns *only* services with strong local
  symptoms — a single candidate per scenario — so precision is not penalised by
  filler entries. This is the expected behaviour of the local-only baseline on
  acyclic, well-localised faults; on multi-hop or low-symptom root causes this
  ablation collapses (see paper §5.4 limitations of the local baseline).
- **-Weights** (UniformWeightPropagator, all edge weights = 1): MRR drops to 0.813,
  Top-1 to 0.750 — the only ablation that actually misranks a scenario (S07,
  `DB_RESOURCE_CONTENTION`, where without coupling-strength weighting the upstream
  `order-svc` is hoisted above the true cause `db-svc`). This is the cleanest
  evidence in the suite that calibrated edge weights are load-bearing.
- **+MaxProp** (MaxPropagationBaseline): identical aggregates to FCP-RCA on this
  suite; the max-aggregation rule produces the same top-1 ordering as Noisy-OR
  on the FODA-8 single- and dual-root-cause scenarios.

## 5. Disabled or skipped tests

None. All 119 unit/integration tests passed; the BenchmarkRunner test passed on
the first execution. No `@Disabled` annotations were added.

## 6. Reproducibility

```bash
# 1. Compile
cd fuzzy-rca-engine
mvn clean compile --no-transfer-progress

# 2. Run unit + integration tests (119 tests)
mvn test --no-transfer-progress

# 3. Run the benchmark (writes target/rca-results.csv,
#    target/rca-per-scenario.csv, target/rca-results.tex)
mvn test -Dtest=BenchmarkRunner --no-transfer-progress
```

### Fixed parameters

| Parameter      | Value  | Set in                                                     |
|----------------|--------|------------------------------------------------------------|
| δ (damping)    | 0.85   | `BenchmarkRunner.java` via `withDampingFactor(0.85)`       |
| ε (convergence)| 1e-6   | `IterativeConfidencePropagator.DEFAULT_EPSILON`            |
| MAX_ITER       | 100    | `IterativeConfidencePropagator.DEFAULT_MAX_ITERATIONS`     |
| k (top-k)      | 3      | `BenchmarkRunner.K`                                        |

### Rule base

- **Path:** `fuzzy-rca-engine/src/main/resources/rca-rules.yaml`
- **Rules:** 20 Mamdani rules (R01–R20), unchanged for this run.

### Scenario suite

- **Provider:** `SyntheticScenarioBuilder.standardBenchmarkSuite()`
- **Source:** `fuzzy-rca-engine/src/main/java/com/foda/rca/evaluation/SyntheticScenarioBuilder.java`
- **No scenarios were added, removed, or modified.**

## 7. FODA-8 benchmark composition

The standard suite contains **8 scenarios**, all defined on a single fixed
service-dependency graph:

### Topology (identical across all 8 scenarios)

```
[gateway] ──0.90──▶ [order-svc] ──0.75──▶ [payment-svc] ──0.85──▶ [db-svc]
                              └──0.80──▶ [inventory-svc] ──0.60──▶ [db-svc]
```

- **Services (nodes):** 5 — `gateway`, `order-svc`, `payment-svc`, `inventory-svc`, `db-svc`
- **Edges:** 5 (caller → callee, weight = coupling strength)
- **Has cycle:** No (DAG; the AdaptiveConfidencePropagator therefore selects the
  DampedConfidencePropagator path — Eq. 4)

### Per-scenario detail

Source: `SyntheticScenarioBuilder.java` (extracted directly, not invented).

| ID  | Scenario name              | Fault category       | Ground-truth root cause(s)   |
|-----|----------------------------|----------------------|------------------------------|
| S01 | DB_CRITICAL_LATENCY        | LATENCY_ANOMALY      | `db-svc`                     |
| S02 | GATEWAY_CPU_SATURATION     | CPU_SATURATION       | `gateway`                    |
| S03 | PAYMENT_MEMORY_PRESSURE    | MEMORY_PRESSURE      | `payment-svc`                |
| S04 | INVENTORY_HIGH_ERROR_RATE  | SERVICE_ERROR        | `inventory-svc`              |
| S05 | ORDER_CPU_LATENCY          | CPU_SATURATION       | `order-svc`                  |
| S06 | CASCADING_DB_PAYMENT       | CASCADING_FAILURE    | `db-svc`, `payment-svc`      |
| S07 | DB_RESOURCE_CONTENTION     | RESOURCE_CONTENTION  | `db-svc`                     |
| S08 | ALL_HEALTHY_BASELINE       | NONE                 | ∅ (empty — no fault)         |

Coverage notes:
- 6 single-root-cause scenarios (S01–S05, S07).
- 1 dual-root-cause scenario (S06) — exercises multi-cause recall.
- 1 no-fault baseline (S08) — exercises calibration of the empty-result path.
- 6 distinct fault categories from the YAML rule base are exercised.

### 7.1 FODA-12 extension (added 2026-04-30)

Source: `SyntheticScenarioBuilder.extendedBenchmarkSuite()` — wraps the
unchanged FODA-8 scenarios with 4 additional diverse-topology scenarios.

| ID  | Scenario name                    | Topology summary                                    | Has cycle | Fault category       | Ground-truth root cause |
|-----|----------------------------------|-----------------------------------------------------|-----------|----------------------|-------------------------|
| S09 | TWO_CYCLE_REPLICATED_PEERS       | 4 services, 4 edges; 2-cycle (svc-A ↔ svc-B)        | yes       | CPU_SATURATION       | `service-B`             |
| S10 | WORKER_CONTROLLER_LOOP           | 5 services, 5 edges; 3-cycle (sched→worker→ctrl→sched) | yes    | LATENCY_ANOMALY      | `storage`               |
| S11 | LARGE_TOPOLOGY_DEEP_PROPAGATION  | 11 services, 10 edges; longest fault path = 5 hops  | no        | RESOURCE_CONTENTION  | `profile-db`            |
| S12 | STRONG_COMPONENT_AMBIGUITY       | 5 services, 5 edges; 3-SCC (svc-A→svc-B→svc-C→svc-A) | yes      | SERVICE_ERROR        | `shared-cache`          |

Discrepancy note for S11: the original specification described 12 services / 11
edges, but the drawn ASCII topology only contains 11 services / 10 edges.
Implementation faithfully follows the drawn topology; this is documented in
the JavaDoc of `buildS11LargeTopologyDeep()`.

## 8. Output artefacts

| File                                                        | Purpose                                       |
|-------------------------------------------------------------|-----------------------------------------------|
| `target/rca-results.csv`                                              | Aggregated metrics (FODA-8), one row per algorithm        |
| `target/rca-per-scenario.csv`                                         | Per-(algorithm × scenario) metrics (FODA-8)               |
| `target/rca-results.tex`                                              | LaTeX table source (FODA-8, Table 4 of the paper)         |
| `target/rca-results-extended.csv`                                     | Aggregated metrics (FODA-12)                              |
| `target/rca-per-scenario-extended.csv`                                | Per-(algorithm × scenario) metrics (FODA-12)              |
| `target/rca-results-extended.tex`                                     | LaTeX table source (FODA-12)                              |
| `target/rca-cycle-activation.txt`                                     | Per-scenario propagator-selection trace (cycle evidence)  |
| `src/test/java/com/foda/rca/evaluation/BenchmarkRunner.java`          | FODA-8 reproducer (`-Dtest=BenchmarkRunner`)              |
| `src/test/java/com/foda/rca/evaluation/ExtendedBenchmarkRunner.java`  | FODA-12 reproducer (`-Dtest=ExtendedBenchmarkRunner`)     |

## 9. Extended FODA-12 results (added 2026-04-30)

The FODA-12 suite consists of the unchanged 8 scenarios from §7 plus 4 new
diverse-topology scenarios (§7.1). Aggregate metrics are NOT directly
comparable to §3 because the denominator is different (n=12 vs n=8); the
table below is the authoritative FODA-12 figure for the paper.

### 9.0 Aggregated results — FODA-12 benchmark, k=3

Source: `target/rca-results-extended.csv` (verbatim).

| Algorithm    | P@3   | std    | R@3   | std    | MRR   | std    | NDCG@3 | std    | Top-1 Acc. |
|--------------|------:|-------:|------:|-------:|------:|-------:|-------:|-------:|-----------:|
| FCP-RCA      | 0.375 | 0.267  | 0.917 | 0.289  | 0.833 | 0.389  | 0.833  | 0.389  | 0.833      |
| -Damping     | 0.347 | 0.288  | 0.833 | 0.389  | 0.750 | 0.452  | 0.750  | 0.452  | 0.750      |
| -Propagation | 0.750 | 0.379  | 1.000 | 0.000  | 0.875 | 0.311  | 0.886  | 0.298  | 0.833      |
| -Weights     | 0.319 | 0.305  | 0.750 | 0.452  | 0.625 | 0.483  | 0.636  | 0.481  | 0.583      |
| +MaxProp     | 0.319 | 0.305  | 0.750 | 0.452  | 0.667 | 0.492  | 0.667  | 0.492  | 0.667      |

(`-Weights` and `+MaxProp` cannot run on the three cyclic scenarios at all —
their underlying propagators perform a topological sort, which is undefined on
cyclic graphs. The benchmark runner records those (algorithm × scenario)
cells as empty predictions, yielding zeros for all four metrics. This is
a faithful representation of the algorithms' applicability, not a runtime bug.)

### 9.1 Per-scenario interpretation for S09–S12

**S09 — TWO_CYCLE_REPLICATED_PEERS** (cyclic, fault at `service-B`).
FCP-RCA, -Damping, and -Propagation all rank `service-B` top-1 (correctly).
-Weights and +MaxProp produce empty predictions (cyclic-graph incompatibility).
The cycle-safe iterative propagator converged in **17 iterations** (max-Δ <
1e-6), confirming the iterative path was actually exercised — see §9.2.

**S10 — WORKER_CONTROLLER_LOOP** (cyclic, fault at `storage`).
**Every algorithm in the suite gets this scenario wrong** at top-1; FCP-RCA
predicts `worker` first. The reason is genuine: under the per-scenario metric
profile, `storage` has cpu=55 (medium, not high) while `worker`'s retries
push its cpu to 78 and latency to 410 ms — `worker`'s local fault score H is
strictly higher than `storage`'s. The damped-propagation contribution from
`worker → storage` (weight 0.80) does not overcome that local-symptom gap.
This is an **honest observation**, not a tuning failure: when a slow callee
causes its caller to saturate CPU via retries, the caller can outshine the
callee on local symptoms alone, and a propagator that respects local-symptom
strength will rank the caller higher. We report this as a known limitation
of symptom-strength-based scoring rather than adjusting the metric profile.
The cycle-safe iterative propagator converged in **12 iterations**.

**S11 — LARGE_TOPOLOGY_DEEP_PROPAGATION** (acyclic, 5-hop fault path,
fault at `profile-db`). All five algorithms (after wrap) rank `profile-db`
top-1; the deep DAG is solved correctly even by `-Damping`. See §9.3 for
the FCP-RCA vs `-Damping` comparison on this scenario.

**S12 — STRONG_COMPONENT_AMBIGUITY** (cyclic, fault at `shared-cache`,
where the upstream cause has WEAKER local symptoms than the SCC services).
This is the discriminating scenario:
- **FCP-RCA** ranks `shared-cache` top-1 (correctly) — the iterative
  propagator with damping correctly attributes the SCC's elevated symptoms
  back to their external dependency.
- **-Damping** (δ=1.0) ranks `svc-C → svc-B → frontend`, missing
  `shared-cache` from top-3 entirely. Without damping, the cycle members
  accumulate enough self-reinforcing confidence to crowd out the upstream
  cause. **This is the strongest evidence in the FODA-12 suite that damping
  is load-bearing on cyclic topologies.**
- **-Propagation** (LocalOnly) ranks `shared-cache` top-1 because it is the
  only service with errorRate ≥ 0.10 (firing the high-error rule strongly).
- **-Weights** and **+MaxProp** cannot evaluate this cyclic graph
  (incompatibility, see §9.0).

### 9.2 Cycle-safe propagator activation evidence

Source: `target/rca-cycle-activation.txt`, captured directly from
`ServiceDependencyGraph.hasCycle()` — the same predicate
`AdaptiveConfidencePropagator` uses to switch propagators.

| Scenario | hasCycle | Propagator selected by AdaptiveConfidencePropagator                |
|----------|----------|--------------------------------------------------------------------|
| S01–S08  | false    | DampedConfidencePropagator (Eq. 4)                                 |
| S09      | **true** | **IterativeConfidencePropagator** (Eq. 5, ε=1e-6, max_iter=100)    |
| S10      | **true** | **IterativeConfidencePropagator** (Eq. 5, ε=1e-6, max_iter=100)    |
| S11      | false    | DampedConfidencePropagator (Eq. 4)                                 |
| S12      | **true** | **IterativeConfidencePropagator** (Eq. 5, ε=1e-6, max_iter=100)    |

Convergence iterations observed in the runtime logs (Jacobi iteration with
δ=0.85, ε=1e-6 stopping criterion):

| Scenario | Iterations to convergence | Final Δ                     |
|----------|---------------------------|-----------------------------|
| S09      | 17                        | 9.04 × 10⁻⁷                 |
| S10      | 12                        | 8.20 × 10⁻⁷                 |
| S12      | 22 (FCP-RCA, δ=0.85)      | < 1e-6 (within max_iter=100)|

(Iteration counts above are taken from DEBUG-level log lines emitted by
`IterativeConfidencePropagator` during the FCP-RCA run; see surefire
log output of `mvn test -Dtest=ExtendedBenchmarkRunner -e -X` to reproduce.)

### 9.3 Damping effect on deep DAGs (S11)

S11 is the only acyclic scenario in the extension and has the deepest fault
path (5 hops from `edge-lb` → `profile-db`).

- **FCP-RCA (δ=0.85):** ranks `profile-db` top-1.
- **-Damping (δ=1.0):** also ranks `profile-db` top-1 — same per-scenario
  metrics as FCP-RCA on S11 specifically (both perfect: P=0.333, R=1, MRR=1,
  NDCG=1).

On THIS particular S11 metric profile, damping does not change the top-1
choice because `profile-db`'s local fault score H (cpu=95 → cpu_HIGH=1.0,
latency=480 → LAT_CRITICAL>0.4, errorRate=0.04 → ERR_LOW saturated, memory=85
→ MEM_HIGH=0.67) is still the strongest in the graph after 5 hops of
attenuation. The intermediate-hop services do not accumulate enough
propagated confidence to overtake the leaf cause even with δ=1.0.

This is a **negative result for the original paper claim** that damping is
specifically necessary on this topology. The aggregate-level effect of damping
in FODA-12 is driven instead by S12 (cycle case, see §9.1), not by S11
(deep-DAG case). The paper text should be revised to reflect that damping's
critical contribution is on cyclic graphs, not on deep acyclic ones, OR a
deeper topology (≥ 8 hops) should be designed where the leaf cause has
weaker symptoms — neither change is in scope for this run.

### 9.4 Reproducibility (FODA-12)

```bash
cd fuzzy-rca-engine
mvn clean compile --no-transfer-progress
mvn test --no-transfer-progress                              # 119 unit tests
mvn test -Dtest=BenchmarkRunner --no-transfer-progress       # FODA-8 outputs
mvn test -Dtest=ExtendedBenchmarkRunner --no-transfer-progress  # FODA-12 outputs
```

Run order matters: `ExtendedBenchmarkRunner` writes its own per-scenario
file directly to `rca-per-scenario-extended.csv` (does NOT clobber the
FODA-8 file via the canonical writer).

Parameters δ, ε, MAX_ITER, k are unchanged from §6 — same values, same rule
file (`src/main/resources/rca-rules.yaml`, 20 rules, untouched).
