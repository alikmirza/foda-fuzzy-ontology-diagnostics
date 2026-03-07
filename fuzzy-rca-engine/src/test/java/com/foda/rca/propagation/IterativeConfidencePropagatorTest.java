package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link IterativeConfidencePropagator}.
 *
 * Verifies acyclic fast path, cyclic convergence, parameter validation,
 * and equivalence to {@link DampedConfidencePropagator} on acyclic graphs.
 */
@DisplayName("IterativeConfidencePropagator Tests")
class IterativeConfidencePropagatorTest {

    private IterativeConfidencePropagator propagator;

    @BeforeEach
    void setUp() {
        propagator = new IterativeConfidencePropagator(0.85, 1e-7, 200);
    }

    private FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    // -----------------------------------------------------------------------
    // Acyclic fast path (should produce exact same result as DampedPropagator)
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Acyclic graph: results match DampedConfidencePropagator exactly")
    void acyclic_matchesDampedPropagator() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("B", "C", 0.9).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.20),
                "C", hyp("C", 0.80));

        DampedConfidencePropagator damped = new DampedConfidencePropagator(0.85);
        Map<String, Double> expected = damped.propagate(hyps, g);
        Map<String, Double> actual   = propagator.propagate(hyps, g);

        expected.forEach((s, e) ->
            assertEquals(e, actual.get(s), 1e-7,
                "Acyclic result mismatch for service " + s));
    }

    // -----------------------------------------------------------------------
    // Cyclic graph: convergence
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Simple cycle A→B→A: converges without throwing")
    void simpleCycle_converges() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.6)
                .addEdge("B", "A", 0.5).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.70),
                "B", hyp("B", 0.20));

        assertDoesNotThrow(() -> {
            Map<String, Double> c = propagator.propagate(hyps, g);
            assertFalse(c.isEmpty());
            c.forEach((s, v) -> assertTrue(v >= 0.0 && v <= 1.0,
                    "C(" + s + ")=" + v + " outside [0,1]"));
        });
    }

    @Test
    @DisplayName("Self-loop: converges and C(s) ≥ H(s)")
    void selfLoop_converges() {
        // A → A (self-loop, e.g. a health-check calling itself)
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "A", 0.5)
                .addService("B").build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.60),
                "B", hyp("B", 0.10));

        Map<String, Double> c = propagator.propagate(hyps, g);
        assertTrue(c.get("A") >= 0.60, "C(A) must be ≥ H(A)");
        assertTrue(c.get("A") <= 1.0,  "C(A) must be ≤ 1.0");
    }

    @Test
    @DisplayName("Triangle cycle A→B→C→A: all results in [0,1]")
    void triangleCycle_valuesInRange() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.7)
                .addEdge("B", "C", 0.8)
                .addEdge("C", "A", 0.6).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.80),
                "B", hyp("B", 0.10),
                "C", hyp("C", 0.05));

        Map<String, Double> c = propagator.propagate(hyps, g);
        c.forEach((s, v) -> assertTrue(v >= 0.0 && v <= 1.0,
                "C(" + s + ")=" + v + " outside [0,1]"));
        // Fault-origin A should retain highest or very high confidence
        assertTrue(c.get("A") >= 0.75,
                "Fault-source A should have high confidence");
    }

    // -----------------------------------------------------------------------
    // Monotonicity C(s) ≥ H(s) — must hold even for cyclic graphs
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Monotonicity: C(s) ≥ H(s) for cyclic graph")
    void cyclicGraph_monotonicity() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("B", "C", 0.7)
                .addEdge("C", "A", 0.6).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.50),
                "B", hyp("B", 0.30),
                "C", hyp("C", 0.20));

        Map<String, Double> c = propagator.propagate(hyps, g);
        hyps.forEach((s, h) ->
            assertTrue(c.get(s) >= h.getLocalConfidence() - 1e-9,
                "C(" + s + ") < H(" + s + "): monotonicity violated"));
    }

    // -----------------------------------------------------------------------
    // Constructor validation
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Constructor rejects invalid epsilon (≤ 0)")
    void constructor_rejectsNonPositiveEpsilon() {
        assertThrows(IllegalArgumentException.class,
                () -> new IterativeConfidencePropagator(0.85, 0.0, 100));
    }

    @Test
    @DisplayName("Constructor rejects invalid maxIterations (< 1)")
    void constructor_rejectsZeroMaxIterations() {
        assertThrows(IllegalArgumentException.class,
                () -> new IterativeConfidencePropagator(0.85, 1e-6, 0));
    }

    @Test
    @DisplayName("Default constructor creates valid instance")
    void defaultConstructor_valid() {
        IterativeConfidencePropagator p = new IterativeConfidencePropagator();
        assertEquals(IterativeConfidencePropagator.DEFAULT_DAMPING_FACTOR, p.getDampingFactor());
        assertEquals(IterativeConfidencePropagator.DEFAULT_EPSILON,        p.getEpsilon());
        assertEquals(IterativeConfidencePropagator.DEFAULT_MAX_ITERATIONS, p.getMaxIterations());
    }

    // -----------------------------------------------------------------------
    // High-confidence cyclic fault: fault-origin should still be highest
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Cyclic: service with highest H remains highest C after convergence")
    void cyclicGraph_faultOriginRemains() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("gateway", "db", 0.9)
                .addEdge("db", "cache", 0.6)
                .addEdge("cache", "gateway", 0.3).build(); // mild feedback loop

        Map<String, FaultHypothesis> hyps = Map.of(
                "gateway", hyp("gateway", 0.05),
                "db",      hyp("db",      0.88),  // fault at db
                "cache",   hyp("cache",   0.10));

        Map<String, Double> c = propagator.propagate(hyps, g);

        // db has highest H; after convergence it should still dominate
        double cDb      = c.get("db");
        double cGateway = c.get("gateway");
        double cCache   = c.get("cache");

        assertTrue(cDb >= cCache,   "db should have higher C than cache");
        assertTrue(cDb > 0.75,      "db fault confidence should remain high");
        assertTrue(cDb >= 0.0 && cDb <= 1.0);
        assertTrue(cGateway >= 0.0 && cGateway <= 1.0);
    }
}
