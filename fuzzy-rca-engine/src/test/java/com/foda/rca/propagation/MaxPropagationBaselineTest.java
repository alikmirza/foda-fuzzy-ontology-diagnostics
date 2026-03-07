package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link MaxPropagationBaseline}.
 *
 * Verifies upper-bound semantics: max-aggregation ≥ max(H(s)), monotonicity,
 * leaf-node identity, and the relationship to noisy-OR on single-path graphs.
 */
@DisplayName("MaxPropagationBaseline Tests")
class MaxPropagationBaselineTest {

    private FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    // -----------------------------------------------------------------------
    // Basic semantics
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Leaf node: C(s) == H(s)")
    void leafNode_identityPropagation() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addService("leaf").build();
        Map<String, FaultHypothesis> hyps = Map.of("leaf", hyp("leaf", 0.70));

        Map<String, Double> c = new MaxPropagationBaseline().propagate(hyps, g);
        assertEquals(0.70, c.get("leaf"), 1e-9, "Leaf: C == H");
    }

    @Test
    @DisplayName("Single edge: C(caller) = max(H(caller), C(callee) * w)")
    void singleEdge_maxSemantics() {
        // A → B (A calls B), B is faulty, A is healthy
        // H(A)=0.05, H(B)=0.90, w=0.80
        // C(B) = 0.90 (leaf)
        // C(A) = max(0.05, 0.90 * 0.80) = max(0.05, 0.72) = 0.72
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.80).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.90));

        Map<String, Double> c = new MaxPropagationBaseline().propagate(hyps, g);
        assertEquals(0.90, c.get("B"), 1e-9, "Leaf B: C == H");
        assertEquals(0.72, c.get("A"), 1e-9, "Caller A: C = max(H, C(B)*w)");
    }

    @Test
    @DisplayName("Monotonicity: C(s) >= H(s) for all services")
    void monotonicity_cAlwaysGeqH() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.9)
                .addEdge("B", "C", 0.8).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.30),
                "C", hyp("C", 0.80));

        Map<String, Double> c = new MaxPropagationBaseline().propagate(hyps, g);
        hyps.forEach((s, h) ->
            assertTrue(c.get(s) >= h.getLocalConfidence() - 1e-9,
                "Monotonicity violated for service " + s));
    }

    @Test
    @DisplayName("All C(s) in [0, 1] for extreme inputs")
    void allValues_inUnitInterval() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 1.0)
                .addEdge("B", "C", 1.0).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 1.0),
                "B", hyp("B", 1.0),
                "C", hyp("C", 1.0));

        new MaxPropagationBaseline().propagate(hyps, g).forEach((s, cv) ->
            assertTrue(cv >= 0.0 && cv <= 1.0, "C(" + s + ")=" + cv + " outside [0,1]"));
    }

    // -----------------------------------------------------------------------
    // Comparison to noisy-OR on single-path graph
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("On single-path graph: max-aggregation <= noisy-OR aggregation")
    void singlePath_maxLeqNoisyOr() {
        // On a single-callee path, noisy-OR: C(s) = 1 – (1–H(s))×(1–C(t)×w)
        // Max:    C(s) = max(H(s), C(t)×w)
        // For H(s)=0, C(t)=0.8, w=0.9:
        //   noisy-OR: C = 1 – 1×(1 – 0.72) = 0.72  (same — only one callee)
        //   max:      C = max(0, 0.72) = 0.72
        // They are equal for single callee. Difference appears with multiple callees.
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.9).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.0),
                "B", hyp("B", 0.80));

        double cMax    = new MaxPropagationBaseline().propagate(hyps, g).get("A");
        double cNoisyOr = new WeightedConfidencePropagator().propagate(hyps, g).get("A");

        // For single callee: max == noisy-OR (both produce C(t)*w since H(s)=0)
        assertEquals(cNoisyOr, cMax, 1e-9,
                "For single callee and H=0, max == noisy-OR");
    }

    @Test
    @DisplayName("Multi-callee: max-aggregation <= noisy-OR aggregation")
    void multiCallee_maxLeqNoisyOr() {
        // A → B (w=0.8) and A → C (w=0.7), both B and C have moderate confidence
        // noisy-OR gives higher C(A) by combining two independent paths
        // max only takes the stronger path
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("A", "C", 0.7).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.0),
                "B", hyp("B", 0.60),
                "C", hyp("C", 0.60));

        double cMax     = new MaxPropagationBaseline().propagate(hyps, g).get("A");
        double cNoisyOr = new WeightedConfidencePropagator().propagate(hyps, g).get("A");

        assertTrue(cMax <= cNoisyOr + 1e-9,
                "With multiple callees, max-aggregation C(A)=" + cMax
                + " should be <= noisy-OR C(A)=" + cNoisyOr);
    }

    // -----------------------------------------------------------------------
    // Fault-source preserving
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Fault source retains highest C even with max-aggregation")
    void faultSource_highestConfidence() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("gateway", "order-svc", 0.9)
                .addEdge("order-svc", "db-svc", 0.8).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "gateway",   hyp("gateway",   0.05),
                "order-svc", hyp("order-svc", 0.10),
                "db-svc",    hyp("db-svc",    0.90));

        Map<String, Double> c = new MaxPropagationBaseline().propagate(hyps, g);
        // db-svc (leaf with H=0.90) should have highest C
        assertTrue(c.get("db-svc") >= c.get("order-svc"),
                "db-svc should have C >= order-svc");
        assertTrue(c.get("db-svc") >= c.get("gateway"),
                "db-svc should have C >= gateway");
    }

    @Test
    @DisplayName("Cyclic graph throws IllegalStateException (consistent with DampedPropagator)")
    void cyclicGraph_throws() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.5)
                .addEdge("B", "A", 0.5).build();
        assertThrows(IllegalStateException.class,
                () -> new MaxPropagationBaseline().propagate(
                        Map.of("A", hyp("A", 0.5), "B", hyp("B", 0.5)), g));
    }
}
