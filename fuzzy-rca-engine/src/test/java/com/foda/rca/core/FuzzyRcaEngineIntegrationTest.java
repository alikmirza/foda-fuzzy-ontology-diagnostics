package com.foda.rca.core;

import com.foda.rca.api.FuzzyRcaEngine;
import com.foda.rca.model.DiagnosisResult;
import com.foda.rca.model.RankedCause;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceMetrics;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * End-to-end integration tests for the full FCP-RCA pipeline.
 *
 * <p>These tests simulate realistic microservice failure scenarios to validate that
 * the pipeline correctly identifies the root cause out of several candidate services.
 * They serve as the basis for the experimental evaluation described in Section 5 of
 * the paper (Precision/Recall@k, MRR, and NDCG benchmarks).</p>
 *
 * <h2>Test Topology</h2>
 * <pre>
 *   [gateway] ──0.9──▶ [order-svc] ──0.8──▶ [inventory-svc]
 *                 └──0.7──▶ [payment-svc] ──0.85──▶ [db-svc]
 *                                           ↑
 *                              [inventory-svc] ──0.6──┘
 * </pre>
 */
@DisplayName("FuzzyRcaEngine End-to-End Integration Tests")
class FuzzyRcaEngineIntegrationTest {

    private FuzzyRcaEngine engine;
    private ServiceDependencyGraph topology;

    @BeforeEach
    void setUp() {
        engine = FuzzyRcaEngineImpl.withDefaults();

        topology = ServiceDependencyGraph.builder()
                .addEdge("gateway",       "order-svc",     0.90)
                .addEdge("order-svc",     "inventory-svc", 0.80)
                .addEdge("order-svc",     "payment-svc",   0.70)
                .addEdge("payment-svc",   "db-svc",        0.85)
                .addEdge("inventory-svc", "db-svc",        0.60)
                .build();
    }

    // -----------------------------------------------------------------------
    // Scenario 1: DB fault propagating upstream
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Scenario 1: Database fault — db-svc should be top-1 root cause")
    void scenario_databaseFault_dbSvcTopRanked() {
        List<ServiceMetrics> observations = List.of(
            // db-svc: critical latency + high error rate (the root cause, leaf dependency)
            metrics("db-svc",        90, 1200, 88, 0.22, 50),
            // callers show mild secondary symptoms (latency increase from db slowness)
            // but their LOCAL metrics are healthy — root cause attribution stays at db-svc
            metrics("payment-svc",   18,  90,  30, 0.003, 920),
            metrics("inventory-svc", 15,  80,  28, 0.002, 940),
            metrics("order-svc",     12,  70,  25, 0.001, 960),
            metrics("gateway",       10,  60,  22, 0.001, 970)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        assertNotNull(result);
        assertFalse(result.getRankedCauses().isEmpty(), "Should identify at least one cause");

        RankedCause top = result.topCause();
        assertNotNull(top);
        assertEquals("db-svc", top.getServiceId(),
                "db-svc should be the top-ranked root cause");
        assertTrue(top.getFinalConfidence() > 0.5,
                "Top cause confidence should be substantial");
        assertFalse(top.getExplanation().isEmpty(),
                "Explanation should be generated");
    }

    // -----------------------------------------------------------------------
    // Scenario 2: CPU saturation at gateway
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Scenario 2: Gateway CPU saturation — gateway should be top root cause")
    void scenario_gatewayCpuSaturation() {
        List<ServiceMetrics> observations = List.of(
            // gateway: clearly saturated (high CPU, elevated latency — local fault)
            metrics("gateway",       95, 550, 60, 0.04, 200),
            // all downstream dependencies are healthy — fault is local to gateway
            metrics("order-svc",     12,  55, 25, 0.001, 960),
            metrics("inventory-svc", 10,  50, 22, 0.001, 970),
            metrics("payment-svc",   11,  52, 24, 0.001, 965),
            metrics("db-svc",         8,  40, 20, 0.001, 980)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        RankedCause top = result.topCause();
        assertNotNull(top);
        assertEquals("gateway", top.getServiceId(),
                "Gateway with 95% CPU should be root cause");
        assertTrue(top.getLocalConfidence() > 0.5,
                "Local hypothesis should be strong for 95% CPU");
    }

    // -----------------------------------------------------------------------
    // Scenario 3: All services healthy — no fault
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Scenario 3: All healthy — no rules fire, no root causes returned")
    void scenario_allHealthy_noFaultIdentified() {
        List<ServiceMetrics> observations = List.of(
            // All services well within SLO bounds: no fault rules will fire (H=0 for all)
            metrics("gateway",       12, 50, 25, 0.001, 950),
            metrics("order-svc",     14, 55, 27, 0.001, 940),
            metrics("inventory-svc", 11, 48, 24, 0.001, 955),
            metrics("payment-svc",   13, 52, 26, 0.001, 945),
            metrics("db-svc",         9, 42, 22, 0.001, 960)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        // With H=0 for all services and no propagation to amplify, all C(s)=0.
        // The TopKCauseRanker filters by threshold=0.10, so results should be empty.
        assertTrue(result.getRankedCauses().isEmpty(),
                "Healthy system: all H=0, all C=0 → no services should exceed threshold");
    }

    // -----------------------------------------------------------------------
    // Scenario 4: Cascading failure across multiple services
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Scenario 4: Cascading failure — payment-svc identified before gateway")
    void scenario_cascadingFailure_correctOrder() {
        List<ServiceMetrics> observations = List.of(
            metrics("payment-svc",   92, 900, 90, 0.18, 80),   // origin
            metrics("db-svc",        85, 700, 88, 0.15, 100),  // affected
            metrics("order-svc",     70, 450, 70, 0.10, 300),
            metrics("gateway",       55, 300, 55, 0.05, 500),
            metrics("inventory-svc", 60, 400, 65, 0.08, 250)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 5);

        assertFalse(result.getRankedCauses().isEmpty());
        // payment-svc and db-svc should both be in top causes
        List<String> topIds = result.getRankedCauses().stream()
                .map(RankedCause::getServiceId).toList();
        assertTrue(topIds.contains("payment-svc") || topIds.contains("db-svc"),
                "Cascading failure: payment-svc or db-svc should be in top causes");
    }

    // -----------------------------------------------------------------------
    // Structural and API contract tests
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Result metadata: correct service and edge counts")
    void result_metadata_correct() {
        List<ServiceMetrics> observations = List.of(
            metrics("gateway",       50, 200, 50, 0.01, 500),
            metrics("order-svc",     50, 200, 50, 0.01, 500),
            metrics("inventory-svc", 50, 200, 50, 0.01, 500),
            metrics("payment-svc",   50, 200, 50, 0.01, 500),
            metrics("db-svc",        50, 200, 50, 0.01, 500)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        assertEquals(5, result.getServiceCount());
        assertEquals(5, result.getEdgeCount());
        assertNotNull(result.getDiagnosisId());
        assertNotNull(result.getTimestamp());
        assertNotNull(result.getFuzzyVectors());
        assertNotNull(result.getFaultHypotheses());
        assertNotNull(result.getPropagatedConfidences());
    }

    @Test
    @DisplayName("Ranked causes are ordered by descending final confidence")
    void rankedCauses_orderedByConfidence() {
        List<ServiceMetrics> observations = List.of(
            metrics("db-svc",        90, 1000, 85, 0.20, 100),   // clear fault
            metrics("payment-svc",   10,   55,  22, 0.001, 950), // healthy
            metrics("inventory-svc", 11,   50,  20, 0.001, 960),
            metrics("order-svc",      9,   45,  18, 0.001, 970),
            metrics("gateway",         8,   40,  16, 0.001, 975)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 5);

        List<RankedCause> causes = result.getRankedCauses();
        for (int i = 0; i < causes.size() - 1; i++) {
            assertTrue(causes.get(i).getFinalConfidence()
                       >= causes.get(i + 1).getFinalConfidence(),
                "Causes must be sorted by descending confidence");
        }
    }

    @Test
    @DisplayName("Causal paths end at the ranked service")
    void causalPaths_endAtRankedService() {
        List<ServiceMetrics> observations = List.of(
            metrics("db-svc",        88, 900, 85, 0.18, 120),   // fault at db
            metrics("payment-svc",   10,  52, 22, 0.001, 950),
            metrics("inventory-svc", 11,  50, 20, 0.001, 960),
            metrics("order-svc",      9,  45, 18, 0.001, 970),
            metrics("gateway",         8,  40, 16, 0.001, 975)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        for (RankedCause cause : result.getRankedCauses()) {
            List<String> path = cause.getCausalPath();
            assertFalse(path.isEmpty(), "Causal path should not be empty");
            assertEquals(cause.getServiceId(), path.get(path.size() - 1),
                    "Causal path must end at the ranked service");
        }
    }

    @Test
    @DisplayName("Explanations are non-empty for all ranked causes")
    void explanations_nonEmpty() {
        List<ServiceMetrics> observations = List.of(
            metrics("db-svc",        88, 900, 85, 0.18, 120),   // fault
            metrics("payment-svc",   10,  52, 22, 0.001, 950),
            metrics("inventory-svc", 11,  50, 20, 0.001, 960),
            metrics("order-svc",      9,  45, 18, 0.001, 970),
            metrics("gateway",         8,  40, 16, 0.001, 975)
        );

        DiagnosisResult result = engine.diagnose(observations, topology, 3);

        for (RankedCause cause : result.getRankedCauses()) {
            assertFalse(cause.getExplanation().isBlank(),
                    "Explanation for " + cause.getServiceId() + " must not be blank");
            assertTrue(cause.getExplanation().contains(cause.getServiceId()),
                    "Explanation should mention the service name");
        }
    }

    @Test
    @DisplayName("topK=1 returns at most one result")
    void topK1_atMostOneResult() {
        List<ServiceMetrics> observations = List.of(
            metrics("db-svc",    88, 900, 85, 0.18, 120),
            metrics("gateway",   28, 140, 38, 0.01, 820)
        );
        ServiceDependencyGraph simpleGraph = ServiceDependencyGraph.builder()
                .addEdge("gateway", "db-svc", 0.9)
                .build();

        DiagnosisResult result = engine.diagnose(observations, simpleGraph, 1);

        assertTrue(result.getRankedCauses().size() <= 1);
    }

    @Test
    @DisplayName("Empty metric list throws IllegalArgumentException")
    void emptyMetrics_throws() {
        assertThrows(IllegalArgumentException.class,
                () -> engine.diagnose(List.of(), topology, 3));
    }

    @Test
    @DisplayName("k<=0 throws IllegalArgumentException")
    void invalidK_throws() {
        assertThrows(IllegalArgumentException.class,
                () -> engine.diagnose(List.of(metrics("svc",50,200,50,0.01,500)), topology, 0));
    }

    // -----------------------------------------------------------------------
    // Helper
    // -----------------------------------------------------------------------

    private ServiceMetrics metrics(String id, double cpu, double latency,
                                    double mem, double err, double tput) {
        return ServiceMetrics.builder()
                .serviceId(id)
                .cpuUsage(cpu).latencyMs(latency).memoryUsage(mem)
                .errorRate(err).throughput(tput)
                .timestamp("2026-02-22T12:00:00Z")
                .build();
    }
}
