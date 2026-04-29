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
    // FODA-12 extension scenarios (S09–S12)
    // Diverse topologies (cycles, deep DAGs) used to exercise the cycle-safe
    // IterativeConfidencePropagator and damping behaviour on long paths.
    // -----------------------------------------------------------------------

    /**
     * S09 — TWO_CYCLE_REPLICATED_PEERS.
     *
     * <p>Topology (4 services, 4 edges, contains a 2-cycle A ↔ B):
     * <pre>
     *   [client] ──0.85──▶ [service-A] ──0.70──▶ [service-B] ──0.80──▶ [db-svc]
     *                            ▲                    │
     *                            └────────0.70────────┘
     * </pre>
     * Replicated peers query each other, creating a feedback loop that
     * forces {@link com.foda.rca.propagation.AdaptiveConfidencePropagator}
     * to delegate to the cycle-safe iterative propagator (Eq. 5).</p>
     *
     * <p>Fault: service-B has high CPU and elevated latency; symptoms leak
     * back to service-A through mutual querying. Ground truth: service-B.</p>
     */
    private static GroundTruthScenario buildS09TwoCycleReplicated() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("client",    "service-A", 0.85)
                .addEdge("service-A", "service-B", 0.70)
                .addEdge("service-B", "service-A", 0.70)
                .addEdge("service-B", "db-svc",    0.80)
                .build();
        if (!g.hasCycle()) {
            throw new AssertionError("S09 topology must contain a cycle (service-A ↔ service-B)");
        }
        return GroundTruthScenario.builder()
                .scenarioId("S09")
                .scenarioName("TWO_CYCLE_REPLICATED_PEERS")
                .description("Replicated peers (A↔B) — service-B CPU saturation, "
                        + "feedback contaminates service-A symptoms")
                .faultType("CPU_SATURATION")
                .observations(List.of(
                        m("service-B", 92, 380, 55, 0.02, 950),
                        m("service-A", 65, 210, 50, 0.01, 950),
                        m("client",    40, 190, 45, 0.01, 950),
                        m("db-svc",    50,  80, 60, 0.0,  950)
                ))
                .dependencyGraph(g)
                .trueRootCauses(Set.of("service-B"))
                .build();
    }

    /**
     * S10 — WORKER_CONTROLLER_LOOP.
     *
     * <p>Topology (5 services, 5 edges, contains a 3-cycle
     * scheduler → worker → controller → scheduler):
     * <pre>
     *   [api] ──0.90──▶ [scheduler] ──0.85──▶ [worker] ──0.75──▶ [controller]
     *                        ▲                  │                     │
     *                        └─────0.65─────────┴──── 0.80 ──▶ [storage]
     * </pre>
     * </p>
     *
     * <p>Fault: storage is slow; the entire 3-cycle (scheduler / worker /
     * controller) shows elevated symptoms because of retries and back-pressure.
     * Ground truth: storage — sits OUTSIDE the cycle but adjacent to it.</p>
     */
    private static GroundTruthScenario buildS10WorkerControllerLoop() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("api",        "scheduler",  0.90)
                .addEdge("scheduler",  "worker",     0.85)
                .addEdge("worker",     "controller", 0.75)
                .addEdge("controller", "scheduler",  0.65)
                .addEdge("worker",     "storage",    0.80)
                .build();
        if (!g.hasCycle()) {
            throw new AssertionError("S10 topology must contain a cycle "
                    + "(scheduler → worker → controller → scheduler)");
        }
        return GroundTruthScenario.builder()
                .scenarioId("S10")
                .scenarioName("WORKER_CONTROLLER_LOOP")
                .description("3-cycle (scheduler-worker-controller) with slow storage outside the cycle; "
                        + "back-pressure drives all cycle members to elevated symptoms")
                .faultType("LATENCY_ANOMALY")
                .observations(List.of(
                        m("storage",    55, 520, 70, 0.05, 200),
                        m("worker",     78, 410, 60, 0.03, 200),
                        m("controller", 65, 380, 55, 0.04, 200),
                        m("scheduler",  70, 320, 55, 0.03, 200),
                        m("api",        45, 290, 50, 0.02, 950)
                ))
                .dependencyGraph(g)
                .trueRootCauses(Set.of("storage"))
                .build();
    }

    /**
     * S11 — LARGE_TOPOLOGY_DEEP_PROPAGATION.
     *
     * <p>Topology (11 services, 10 edges, no cycles; longest fault path = 5 hops
     * from edge-lb down to profile-db):
     * <pre>
     *   [edge-lb] ──0.92──▶ [api-gw] ──0.88──▶ [auth-svc] ──0.85──▶ [user-svc] ──0.80──▶ [profile-svc] ──0.75──▶ [profile-db]
     *                                                                       └─0.78──▶ [order-svc] ──0.82──▶ [order-db]
     *                                                                                              └──0.70──▶ [shipping-svc] ──0.65──▶ [shipping-db]
     *                                                                                                                            └──0.60──▶ [logistics-api]
     * </pre>
     * (Note: paper specification originally said 12 services / 11 edges, but the
     * drawn topology has 11 services / 10 edges — implementation follows the
     * drawn topology faithfully; the discrepancy is documented in
     * {@code EVALUATION_RESULTS.md} §9.)</p>
     *
     * <p>Fault: profile-db is overloaded; the symptoms attenuate over five hops
     * up to edge-lb. Without damping, the top-of-graph services are expected to
     * hoist above profile-db; with damping (δ=0.85) profile-db should remain top-1.</p>
     */
    private static GroundTruthScenario buildS11LargeTopologyDeep() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("edge-lb",       "api-gw",         0.92)
                .addEdge("api-gw",        "auth-svc",       0.88)
                .addEdge("auth-svc",      "user-svc",       0.85)
                .addEdge("user-svc",      "profile-svc",    0.80)
                .addEdge("profile-svc",   "profile-db",     0.75)
                .addEdge("user-svc",      "order-svc",      0.78)
                .addEdge("order-svc",     "order-db",       0.82)
                .addEdge("order-svc",     "shipping-svc",   0.70)
                .addEdge("shipping-svc",  "shipping-db",    0.65)
                .addEdge("shipping-svc",  "logistics-api",  0.60)
                .build();
        if (g.hasCycle()) {
            throw new AssertionError("S11 topology must be acyclic (deep DAG)");
        }
        return GroundTruthScenario.builder()
                .scenarioId("S11")
                .scenarioName("LARGE_TOPOLOGY_DEEP_PROPAGATION")
                .description("Deep acyclic topology — profile-db is overloaded; symptoms attenuate "
                        + "over 5 hops up to edge-lb")
                .faultType("RESOURCE_CONTENTION")
                .observations(List.of(
                        // fault path (5 hops) - symptoms attenuate up the chain
                        m("profile-db",    95, 480, 85, 0.04,  300),
                        m("profile-svc",   72, 420, 68, 0.03,  400),
                        m("user-svc",      58, 350, 55, 0.02,  550),
                        m("auth-svc",      48, 280, 48, 0.015, 720),
                        m("api-gw",        40, 220, 42, 0.01,  850),
                        m("edge-lb",       32, 180, 38, 0.005, 920),
                        // unaffected branches (order/shipping subtree)
                        m("order-svc",     14,  55, 24, 0.001, 950),
                        m("order-db",      12,  45, 22, 0.001, 970),
                        m("shipping-svc",  13,  50, 23, 0.001, 960),
                        m("shipping-db",   11,  42, 21, 0.001, 975),
                        m("logistics-api", 12,  48, 22, 0.001, 965)
                ))
                .dependencyGraph(g)
                .trueRootCauses(Set.of("profile-db"))
                .build();
    }

    /**
     * S12 — STRONG_COMPONENT_AMBIGUITY.
     *
     * <p>Topology (5 services, 5 edges, contains a 3-SCC svc-A → svc-B → svc-C → svc-A,
     * plus an external dependency on shared-cache):
     * <pre>
     *   [frontend] ──0.90──▶ [svc-A] ──0.80──▶ [svc-B] ──0.85──▶ [svc-C]
     *                          ▲                                    │
     *                          └─────────────0.70───────────────────┤
     *                                                               └──0.75──▶ [shared-cache]
     * </pre>
     * </p>
     *
     * <p>Fault: shared-cache is degraded (high error rate, low throughput, modest CPU).
     * Its weak local symptoms — error rate 0.18 but cpu only 45 — are SMALLER than
     * those of the SCC services (svc-C cpu 70, latency 340). A naive local-only
     * approach will rank svc-C above shared-cache. A correctly weighted upstream
     * propagator must identify shared-cache as the true cause despite its weaker
     * raw symptoms.</p>
     */
    private static GroundTruthScenario buildS12StrongComponentAmbiguity() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("frontend", "svc-A",        0.90)
                .addEdge("svc-A",    "svc-B",        0.80)
                .addEdge("svc-B",    "svc-C",        0.85)
                .addEdge("svc-C",    "svc-A",        0.70)
                .addEdge("svc-C",    "shared-cache", 0.75)
                .build();
        if (!g.hasCycle()) {
            throw new AssertionError("S12 topology must contain a cycle "
                    + "(svc-A → svc-B → svc-C → svc-A)");
        }
        return GroundTruthScenario.builder()
                .scenarioId("S12")
                .scenarioName("STRONG_COMPONENT_AMBIGUITY")
                .description("3-SCC (svc-A,B,C) with degraded external shared-cache; "
                        + "upstream cause has weaker local symptoms than downstream cycle members")
                .faultType("SERVICE_ERROR")
                .observations(List.of(
                        m("shared-cache", 45, 280, 50, 0.18, 200),
                        m("svc-C",        70, 340, 60, 0.12, 200),
                        m("svc-B",        65, 310, 55, 0.08, 200),
                        m("svc-A",        60, 290, 55, 0.07, 200),
                        m("frontend",     50, 270, 50, 0.06, 950)
                ))
                .dependencyGraph(g)
                .trueRootCauses(Set.of("shared-cache"))
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
     * Returns the FODA-12 extended benchmark suite: the eight FODA-8 scenarios
     * (unchanged) plus four new diverse-topology scenarios (S09–S12) that
     * exercise cycle-safe propagation and deep-DAG damping.
     *
     * <p>FODA-8 scenarios are referenced through {@link #standardBenchmarkSuite()}
     * so prior published results remain reproducible bit-for-bit.</p>
     */
    public static List<GroundTruthScenario> extendedBenchmarkSuite() {
        List<GroundTruthScenario> base = standardBenchmarkSuite();
        List<GroundTruthScenario> all  = new java.util.ArrayList<>(base.size() + 4);
        all.addAll(base);
        all.add(buildS09TwoCycleReplicated());
        all.add(buildS10WorkerControllerLoop());
        all.add(buildS11LargeTopologyDeep());
        all.add(buildS12StrongComponentAmbiguity());
        return List.copyOf(all);
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
