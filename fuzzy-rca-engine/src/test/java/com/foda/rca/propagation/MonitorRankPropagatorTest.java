package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link MonitorRankPropagator}. Cover DAG, cyclic, empty-anomalous,
 * and single-node cases plus parameter validation. Uses the same hypothesis
 * factory pattern as {@link IterativeConfidencePropagatorTest}.
 */
@DisplayName("MonitorRankPropagator Tests")
class MonitorRankPropagatorTest {

    private final MonitorRankPropagator propagator = new MonitorRankPropagator();

    private static FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    private static double sum(Map<String, Double> m) {
        return m.values().stream().mapToDouble(Double::doubleValue).sum();
    }

    @Test
    @DisplayName("DAG: produces a valid probability distribution (sum=1, all in [0,1])")
    void dag_validDistribution() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("gateway", "order", 0.9)
                .addEdge("order",   "db",    0.8)
                .addEdge("order",   "cache", 0.6)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "gateway", hyp("gateway", 0.10),
                "order",   hyp("order",   0.40),   // anomalous
                "db",      hyp("db",      0.85),   // anomalous (root cause)
                "cache",   hyp("cache",   0.05));

        Map<String, Double> pi = propagator.propagate(hyps, g);

        assertEquals(4, pi.size());
        pi.values().forEach(v ->
            assertTrue(v >= 0.0 && v <= 1.0, "score " + v + " outside [0,1]"));
        assertEquals(1.0, sum(pi), 1e-9, "scores must sum to 1");
        // db is the deepest callee with high H — should accumulate non-trivial mass
        assertTrue(pi.get("db") > 0.05, "db should have meaningful mass: " + pi.get("db"));
    }

    @Test
    @DisplayName("Cyclic graph: converges and produces a valid probability distribution")
    void cyclic_convergesToValidDistribution() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.7)
                .addEdge("B", "C", 0.7)
                .addEdge("C", "A", 0.7)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.6),
                "B", hyp("B", 0.3),
                "C", hyp("C", 0.2));

        Map<String, Double> pi = assertDoesNotThrow(() -> propagator.propagate(hyps, g));
        assertEquals(3, pi.size());
        pi.values().forEach(v ->
            assertTrue(v >= 0.0 && v <= 1.0, "score " + v + " outside [0,1]"));
        assertEquals(1.0, sum(pi), 1e-9, "scores must sum to 1");
    }

    @Test
    @DisplayName("Empty anomalous set: returns uniform distribution and does not crash")
    void emptyAnomalous_uniformFallback() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.5)
                .addEdge("B", "C", 0.5)
                .build();
        // All H values below the 0.30 anomaly threshold
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.10),
                "B", hyp("B", 0.05),
                "C", hyp("C", 0.20));

        Map<String, Double> pi = assertDoesNotThrow(() -> propagator.propagate(hyps, g));
        assertEquals(3, pi.size());
        assertEquals(1.0, sum(pi), 1e-9);
        // Uniform fallback: each service gets 1/3
        pi.values().forEach(v -> assertEquals(1.0 / 3.0, v, 1e-9));
    }

    @Test
    @DisplayName("Single-node graph: returns 1.0 for the only service")
    void singleNode_returnsOne() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addService("only").build();
        Map<String, FaultHypothesis> hyps = Map.of("only", hyp("only", 0.7));

        Map<String, Double> pi = propagator.propagate(hyps, g);
        assertEquals(1, pi.size());
        assertEquals(1.0, pi.get("only"), 1e-12);
    }

    @Test
    @DisplayName("Anomalous service receives more mass than non-anomalous siblings")
    void anomalousAccumulatesMass() {
        // Star graph: root -> {a, b, c, d}; only 'a' is anomalous.
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("root", "a", 0.5)
                .addEdge("root", "b", 0.5)
                .addEdge("root", "c", 0.5)
                .addEdge("root", "d", 0.5)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "root", hyp("root", 0.10),
                "a",    hyp("a",    0.85),   // anomalous
                "b",    hyp("b",    0.05),
                "c",    hyp("c",    0.05),
                "d",    hyp("d",    0.05));

        Map<String, Double> pi = propagator.propagate(hyps, g);
        assertEquals(1.0, sum(pi), 1e-9);
        assertTrue(pi.get("a") > pi.get("b"), "anomalous a should outrank b: " + pi);
        assertTrue(pi.get("a") > pi.get("c"), "anomalous a should outrank c: " + pi);
        assertTrue(pi.get("a") > pi.get("d"), "anomalous a should outrank d: " + pi);
    }

    @Test
    @DisplayName("Constructor rejects invalid restart probability")
    void constructor_rejectsInvalidRestart() {
        assertThrows(IllegalArgumentException.class,
                () -> new MonitorRankPropagator(0.30, 0.0, 1e-6, 100));
        assertThrows(IllegalArgumentException.class,
                () -> new MonitorRankPropagator(0.30, 1.0, 1e-6, 100));
    }

    @Test
    @DisplayName("Constructor rejects invalid epsilon and maxIterations")
    void constructor_rejectsOtherInvalidParams() {
        assertThrows(IllegalArgumentException.class,
                () -> new MonitorRankPropagator(0.30, 0.15, 0.0, 100));
        assertThrows(IllegalArgumentException.class,
                () -> new MonitorRankPropagator(0.30, 0.15, 1e-6, 0));
        assertThrows(IllegalArgumentException.class,
                () -> new MonitorRankPropagator(-0.01, 0.15, 1e-6, 100));
    }

    @Test
    @DisplayName("Default constructor: defaults match the documented constants")
    void defaultConstructor_validParams() {
        MonitorRankPropagator p = new MonitorRankPropagator();
        assertEquals(MonitorRankPropagator.ANOMALY_THRESHOLD,      p.getAnomalyThreshold());
        assertEquals(MonitorRankPropagator.DEFAULT_RESTART_PROB,   p.getRestartProbability());
        assertEquals(MonitorRankPropagator.DEFAULT_EPSILON,        p.getEpsilon());
        assertEquals(MonitorRankPropagator.DEFAULT_MAX_ITERATIONS, p.getMaxIterations());
    }
}
