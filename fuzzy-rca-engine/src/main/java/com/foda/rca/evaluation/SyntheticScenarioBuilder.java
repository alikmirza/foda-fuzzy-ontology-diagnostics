package com.foda.rca.evaluation;

import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceMetrics;

import java.util.List;
import java.util.Set;

/**
 * Factory for reproducible fault injection scenarios used in the benchmark suite
 * (Section 5.1, Table 3 of the paper).
 *
 * <h2>Benchmark topology</h2>
 * <pre>
 *   [gateway] ──0.9──▶ [order-svc] ──0.80──▶ [inventory-svc]
 *                  └──0.75──▶ [payment-svc] ──0.85──▶ [db-svc]
 *                                              ↑
 *                             [inventory-svc] ──0.60──┘
 * </pre>
 * Services: gateway (entry point), order-svc, payment-svc, inventory-svc, db-svc (leaf).
 *
 * <h2>Scenario taxonomy</h2>
 * <p>Eight scenarios are defined, two per fault category (except CASCADING which has two),
 * giving broad coverage of the fault space while remaining reproducible for publication:</p>
 *
 * <table border="1">
 *   <tr><th>ID</th><th>Fault type</th><th>Root cause</th></tr>
 *   <tr><td>S01</td><td>LATENCY_ANOMALY + SERVICE_ERROR</td><td>db-svc</td></tr>
 *   <tr><td>S02</td><td>CPU_SATURATION</td><td>gateway</td></tr>
 *   <tr><td>S03</td><td>MEMORY_PRESSURE</td><td>payment-svc</td></tr>
 *   <tr><td>S04</td><td>SERVICE_ERROR</td><td>inventory-svc</td></tr>
 *   <tr><td>S05</td><td>CPU_SATURATION + LATENCY_ANOMALY</td><td>order-svc</td></tr>
 *   <tr><td>S06</td><td>CASCADING_FAILURE</td><td>db-svc, payment-svc</td></tr>
 *   <tr><td>S07</td><td>RESOURCE_CONTENTION</td><td>db-svc</td></tr>
 *   <tr><td>S08</td><td>HEALTHY baseline</td><td>{} (no fault)</td></tr>
 * </table>
 */
public final class SyntheticScenarioBuilder {

    private SyntheticScenarioBuilder() {}

    // -----------------------------------------------------------------------
    // Standard 5-service topology
    // -----------------------------------------------------------------------

    /**
     * Constructs the standard benchmark dependency graph used in all synthetic scenarios.
     * Edge weights represent calibrated coupling strengths (proportion of request failures
     * attributable to the callee's state).
     */
    public static ServiceDependencyGraph standardGraph() {
        return ServiceDependencyGraph.builder()
                .addEdge("gateway",       "order-svc",      0.90)
                .addEdge("order-svc",     "payment-svc",    0.75)
                .addEdge("order-svc",     "inventory-svc",  0.80)
                .addEdge("payment-svc",   "db-svc",         0.85)
                .addEdge("inventory-svc", "db-svc",         0.60)
                .build();
    }

    // -----------------------------------------------------------------------
    // Individual scenarios
    // -----------------------------------------------------------------------

    /**
     * S01 — db-svc critical database fault (critical latency + high error rate).
     * All callers are healthy (no local fault symptoms).
     * Expected top-1: {@code db-svc}.
     */
    public static GroundTruthScenario s01_databaseCritical(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S01")
                .scenarioName("DB_CRITICAL_LATENCY")
                .description("db-svc P99 latency spike to 1200 ms with 22% error rate")
                .faultType("LATENCY_ANOMALY")
                .observations(List.of(
                        m("db-svc",        90, 1200, 88, 0.22, 50),
                        m("payment-svc",   10,   55, 22, 0.001, 950),
                        m("inventory-svc", 11,   50, 20, 0.001, 960),
                        m("order-svc",      9,   45, 18, 0.001, 970),
                        m("gateway",        8,   40, 16, 0.001, 975)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("db-svc"))
                .build();
    }

    /**
     * S02 — gateway CPU saturation.
     * All downstream dependencies are healthy.
     * Expected top-1: {@code gateway}.
     */
    public static GroundTruthScenario s02_gatewayCpuSaturation(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S02")
                .scenarioName("GATEWAY_CPU_SATURATION")
                .description("gateway CPU utilisation at 95% with elevated latency")
                .faultType("CPU_SATURATION")
                .observations(List.of(
                        m("gateway",        95, 550, 60, 0.04, 200),
                        m("order-svc",      12,  55, 25, 0.001, 960),
                        m("inventory-svc",  10,  50, 22, 0.001, 970),
                        m("payment-svc",    11,  52, 24, 0.001, 965),
                        m("db-svc",          8,  40, 20, 0.001, 980)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("gateway"))
                .build();
    }

    /**
     * S03 — payment-svc memory pressure + slow throughput.
     * db-svc is healthy; gateway is healthy.
     * Expected top-1: {@code payment-svc}.
     */
    public static GroundTruthScenario s03_paymentMemoryPressure(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S03")
                .scenarioName("PAYMENT_MEMORY_PRESSURE")
                .description("payment-svc heap at 93%, throughput collapsed to 80 req/s")
                .faultType("MEMORY_PRESSURE")
                .observations(List.of(
                        m("payment-svc",   55, 380, 93, 0.03, 80),
                        m("db-svc",         8,  40, 20, 0.001, 980),
                        m("order-svc",     10,  48, 22, 0.001, 960),
                        m("inventory-svc",  9,  45, 21, 0.001, 965),
                        m("gateway",        8,  42, 18, 0.001, 975)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("payment-svc"))
                .build();
    }

    /**
     * S04 — inventory-svc high error rate.
     * Expected top-1: {@code inventory-svc}.
     */
    public static GroundTruthScenario s04_inventoryHighErrorRate(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S04")
                .scenarioName("INVENTORY_HIGH_ERROR_RATE")
                .description("inventory-svc returning 18% 5xx errors, CPU moderate")
                .faultType("SERVICE_ERROR")
                .observations(List.of(
                        m("inventory-svc", 55, 290, 62, 0.18, 300),
                        m("db-svc",         9,  42, 21, 0.001, 975),
                        m("order-svc",     11,  50, 24, 0.001, 960),
                        m("payment-svc",   10,  48, 22, 0.001, 965),
                        m("gateway",        9,  43, 19, 0.001, 972)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("inventory-svc"))
                .build();
    }

    /**
     * S05 — order-svc CPU + critical latency.
     * Expected top-1: {@code order-svc}.
     */
    public static GroundTruthScenario s05_orderCpuLatency(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S05")
                .scenarioName("ORDER_CPU_LATENCY")
                .description("order-svc CPU at 91%, P99 latency at 720 ms")
                .faultType("CPU_SATURATION")
                .observations(List.of(
                        m("order-svc",     91, 720, 58, 0.04, 220),
                        m("inventory-svc",  9,  44, 20, 0.001, 968),
                        m("payment-svc",   10,  46, 22, 0.001, 966),
                        m("db-svc",         8,  40, 18, 0.001, 978),
                        m("gateway",       10,  50, 22, 0.001, 962)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("order-svc"))
                .build();
    }

    /**
     * S06 — cascading failure at both db-svc and payment-svc.
     * Dual root cause scenario — tests multi-root-cause recall.
     * Expected: {@code db-svc} and {@code payment-svc} in top-3.
     */
    public static GroundTruthScenario s06_cascadingFailure(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S06")
                .scenarioName("CASCADING_DB_PAYMENT")
                .description("db-svc and payment-svc both failing; cascading CPU+error pattern")
                .faultType("CASCADING_FAILURE")
                .observations(List.of(
                        m("db-svc",        88,  950, 92, 0.20, 60),
                        m("payment-svc",   90, 1100, 89, 0.17, 40),
                        m("inventory-svc",  9,   44, 20, 0.001, 968),
                        m("order-svc",     10,   46, 22, 0.001, 966),
                        m("gateway",        9,   43, 19, 0.001, 972)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("db-svc", "payment-svc"))
                .build();
    }

    /**
     * S07 — db-svc resource contention (high CPU + high memory).
     * Expected top-1: {@code db-svc}.
     */
    public static GroundTruthScenario s07_dbResourceContention(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S07")
                .scenarioName("DB_RESOURCE_CONTENTION")
                .description("db-svc CPU at 89% and heap at 91% — resource contention")
                .faultType("RESOURCE_CONTENTION")
                .observations(List.of(
                        m("db-svc",        89, 480, 91, 0.05, 120),
                        m("payment-svc",    9,  44, 21, 0.001, 970),
                        m("inventory-svc",  8,  42, 20, 0.001, 975),
                        m("order-svc",     10,  46, 22, 0.001, 968),
                        m("gateway",        9,  43, 19, 0.001, 972)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of("db-svc"))
                .build();
    }

    /**
     * S08 — fully healthy baseline (no injected fault).
     * Ground-truth root causes = {} (empty set).
     * A well-calibrated algorithm should return zero candidates.
     */
    public static GroundTruthScenario s08_allHealthy(ServiceDependencyGraph graph) {
        return GroundTruthScenario.builder()
                .scenarioId("S08")
                .scenarioName("ALL_HEALTHY_BASELINE")
                .description("All services within SLO bounds; no fault injected")
                .faultType("NONE")
                .observations(List.of(
                        m("gateway",        12, 50, 25, 0.001, 950),
                        m("order-svc",      14, 55, 27, 0.001, 940),
                        m("payment-svc",    11, 48, 23, 0.001, 955),
                        m("inventory-svc",  10, 46, 22, 0.001, 960),
                        m("db-svc",          9, 42, 21, 0.001, 965)
                ))
                .dependencyGraph(graph)
                .trueRootCauses(Set.of())  // no fault → empty ground truth
                .build();
    }

    // -----------------------------------------------------------------------
    // Convenience: full benchmark suite
    // -----------------------------------------------------------------------

    /**
     * Returns all eight scenarios on the standard topology.
     * This is the complete benchmark suite referenced as "the FODA-8 benchmark" in the paper.
     */
    public static List<GroundTruthScenario> standardBenchmarkSuite() {
        ServiceDependencyGraph g = standardGraph();
        return List.of(
                s01_databaseCritical(g),
                s02_gatewayCpuSaturation(g),
                s03_paymentMemoryPressure(g),
                s04_inventoryHighErrorRate(g),
                s05_orderCpuLatency(g),
                s06_cascadingFailure(g),
                s07_dbResourceContention(g),
                s08_allHealthy(g)
        );
    }

    /**
     * Returns only the single-root-cause scenarios (S01–S05, S07) — useful when
     * standard P@1 / R@1 metrics are being reported without multi-cause weighting.
     */
    public static List<GroundTruthScenario> singleRootCauseSuite() {
        ServiceDependencyGraph g = standardGraph();
        return List.of(
                s01_databaseCritical(g),
                s02_gatewayCpuSaturation(g),
                s03_paymentMemoryPressure(g),
                s04_inventoryHighErrorRate(g),
                s05_orderCpuLatency(g),
                s07_dbResourceContention(g)
        );
    }

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    private static ServiceMetrics m(String id, double cpu, double lat,
                                     double mem, double err, double tput) {
        return ServiceMetrics.builder()
                .serviceId(id).cpuUsage(cpu).latencyMs(lat)
                .memoryUsage(mem).errorRate(err).throughput(tput)
                .timestamp("2026-02-23T00:00:00Z").build();
    }
}
