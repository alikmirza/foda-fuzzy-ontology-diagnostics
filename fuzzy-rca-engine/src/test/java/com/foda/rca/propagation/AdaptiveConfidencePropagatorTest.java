package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link AdaptiveConfidencePropagator}.
 *
 * Verifies that the adaptive propagator correctly selects:
 * <ul>
 *   <li>{@link DampedConfidencePropagator} for acyclic graphs (results are numerically
 *       identical to direct DampedPropagator usage).</li>
 *   <li>{@link IterativeConfidencePropagator} for cyclic graphs (produces valid, convergent
 *       results in [0,1] without throwing).</li>
 * </ul>
 */
@DisplayName("AdaptiveConfidencePropagator Tests")
class AdaptiveConfidencePropagatorTest {

    private static final double DELTA = 0.85;

    private FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    // -----------------------------------------------------------------------
    // Acyclic graphs: results must match DampedConfidencePropagator exactly
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Acyclic chain: adaptive == DampedPropagator results")
    void acyclicChain_matchesDamped() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("B", "C", 0.9).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.20),
                "C", hyp("C", 0.80));

        AdaptiveConfidencePropagator adaptive = new AdaptiveConfidencePropagator(DELTA);
        DampedConfidencePropagator   damped   = new DampedConfidencePropagator(DELTA);

        Map<String, Double> cAdaptive = adaptive.propagate(hyps, g);
        Map<String, Double> cDamped   = damped.propagate(hyps, g);

        cDamped.forEach((s, expected) ->
            assertEquals(expected, cAdaptive.get(s), 1e-9,
                "Acyclic mismatch for service " + s));
    }

    @Test
    @DisplayName("Single-node acyclic: C(s) == H(s)")
    void acyclicSingleNode_identityPropagation() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addService("leaf").build();
        Map<String, FaultHypothesis> hyps = Map.of("leaf", hyp("leaf", 0.75));

        Map<String, Double> c = new AdaptiveConfidencePropagator(DELTA).propagate(hyps, g);
        assertEquals(0.75, c.get("leaf"), 1e-9, "Leaf: C == H");
    }

    @Test
    @DisplayName("Acyclic: hasCycle() returns false → adaptive uses DampedPropagator path")
    void acyclic_hasCycleReturnsFalse() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("gateway", "order-svc", 0.9)
                .addEdge("order-svc", "db-svc", 0.8).build();
        assertFalse(g.hasCycle(), "Standard microservice graph should be acyclic");
    }

    // -----------------------------------------------------------------------
    // Cyclic graphs: adaptive must NOT throw; results must be in [0,1]
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Simple cycle A→B→A: adaptive propagates without throwing")
    void cyclicGraph_doesNotThrow() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.6)
                .addEdge("B", "A", 0.5).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.70),
                "B", hyp("B", 0.20));

        assertTrue(g.hasCycle(), "Graph with mutual edges should be cyclic");

        AdaptiveConfidencePropagator adaptive = new AdaptiveConfidencePropagator(DELTA);
        assertDoesNotThrow(() -> {
            Map<String, Double> c = adaptive.propagate(hyps, g);
            assertFalse(c.isEmpty());
            c.forEach((s, v) -> assertTrue(v >= 0.0 && v <= 1.0,
                    "C(" + s + ")=" + v + " outside [0,1]"));
        });
    }

    @Test
    @DisplayName("Cyclic: DampedPropagator throws, adaptive handles it gracefully")
    void cyclicGraph_dampedThrowsAdaptiveHandles() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("X", "Y", 0.7)
                .addEdge("Y", "X", 0.5).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "X", hyp("X", 0.80),
                "Y", hyp("Y", 0.10));

        // DampedPropagator throws on cycles
        assertThrows(IllegalStateException.class,
                () -> new DampedConfidencePropagator(DELTA).propagate(hyps, g));

        // Adaptive handles it without throwing
        assertDoesNotThrow(
                () -> new AdaptiveConfidencePropagator(DELTA).propagate(hyps, g));
    }

    @Test
    @DisplayName("Cyclic: monotonicity C(s) >= H(s)")
    void cyclicGraph_monotonicity() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("B", "C", 0.7)
                .addEdge("C", "A", 0.6).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.60),
                "B", hyp("B", 0.20),
                "C", hyp("C", 0.10));

        Map<String, Double> c = new AdaptiveConfidencePropagator(DELTA).propagate(hyps, g);
        hyps.forEach((s, h) ->
            assertTrue(c.get(s) >= h.getLocalConfidence() - 1e-9,
                "Monotonicity violated for service " + s));
    }

    // -----------------------------------------------------------------------
    // Constructor validation
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Default constructor uses δ = 0.85")
    void defaultConstructor_usesDefaultDamping() {
        AdaptiveConfidencePropagator p = new AdaptiveConfidencePropagator();
        assertEquals(AdaptiveConfidencePropagator.DEFAULT_DAMPING_FACTOR, p.getDampingFactor());
    }

    @Test
    @DisplayName("Constructor rejects δ outside (0, 1]")
    void constructor_rejectsInvalidDamping() {
        assertThrows(IllegalArgumentException.class, () -> new AdaptiveConfidencePropagator(0.0));
        assertThrows(IllegalArgumentException.class, () -> new AdaptiveConfidencePropagator(1.1));
    }

    // -----------------------------------------------------------------------
    // Integration: auto-selection works inside FuzzyRcaEngineImpl
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("hasCycle() correctly identifies acyclic standard topology")
    void hasCycle_standardTopology_acyclic() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("gateway",       "order-svc",      0.90)
                .addEdge("order-svc",     "payment-svc",    0.75)
                .addEdge("order-svc",     "inventory-svc",  0.80)
                .addEdge("payment-svc",   "db-svc",         0.85)
                .addEdge("inventory-svc", "db-svc",         0.60)
                .build();
        assertFalse(g.hasCycle(), "Standard 5-service benchmark topology is acyclic");
    }

    @Test
    @DisplayName("hasCycle() correctly identifies cyclic graph with back-edge")
    void hasCycle_withBackEdge_cyclic() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("svc-a", "svc-b", 0.8)
                .addEdge("svc-b", "svc-c", 0.7)
                .addEdge("svc-c", "svc-a", 0.5)  // back-edge creating cycle
                .build();
        assertTrue(g.hasCycle(), "Graph with back-edge should be cyclic");
    }
}
