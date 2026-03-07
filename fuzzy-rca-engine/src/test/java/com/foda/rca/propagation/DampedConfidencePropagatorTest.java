package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link DampedConfidencePropagator}.
 *
 * Verifies the mathematical properties stated in Equations 4a/4b and confirms that
 * the damping factor produces strictly lower confidence than the undamped baseline
 * over multi-hop paths.
 */
@DisplayName("DampedConfidencePropagator Tests")
class DampedConfidencePropagatorTest {

    private FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of()).build();
    }

    // -----------------------------------------------------------------------
    // Formula verification
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Leaf node: C = H (no callees to propagate from)")
    void leafNode_equalsLocalHypothesis() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addService("leaf").build();
        DampedConfidencePropagator p = new DampedConfidencePropagator(0.80);
        Map<String, Double> c = p.propagate(Map.of("leaf", hyp("leaf", 0.75)), g);
        assertEquals(0.75, c.get("leaf"), 1e-9);
    }

    @Test
    @DisplayName("Single edge: manual Eq 4a/4b verification")
    void singleEdge_manualVerification() {
        // A → B (A calls B), B is faulty, A is healthy.
        // H(A)=0.05, H(B)=0.80, w=0.70, δ=0.85
        // C(B) = 0.80 (leaf)
        // P(A) = 1 – (1 – 0.80 × 0.70 × 0.85) = 1 – (1 – 0.476) = 0.476
        // C(A) = 1 – (1 – 0.05) × (1 – 0.476) = 1 – 0.95 × 0.524 = 1 – 0.4978 = 0.5022
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.70).build();
        DampedConfidencePropagator p = new DampedConfidencePropagator(0.85);
        Map<String, Double> c = p.propagate(
                Map.of("A", hyp("A", 0.05), "B", hyp("B", 0.80)), g);

        assertEquals(0.80,   c.get("B"), 1e-9, "Leaf B: C = H");
        assertEquals(0.5022, c.get("A"), 1e-4, "Caller A: C per Eq 4b");
    }

    // -----------------------------------------------------------------------
    // Damping effect
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Damped contribution < undamped contribution for same graph")
    void damped_lowerThanUndamped_forCaller() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 1.0).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.0),
                "B", hyp("B", 0.90));

        DampedConfidencePropagator damped   = new DampedConfidencePropagator(0.70);
        WeightedConfidencePropagator nodamp = new WeightedConfidencePropagator();

        double ca_damped  = damped.propagate(hyps, g).get("A");
        double ca_undamped = nodamp.propagate(hyps, g).get("A");

        assertTrue(ca_damped < ca_undamped,
                "Damped C(A) should be strictly less than undamped C(A)");
    }

    @Test
    @DisplayName("Longer chains are more attenuated than shorter chains")
    void longerChain_moreAttenuation() {
        // Short chain: X → B (B faulty)
        // Long chain:  X → M → B (B faulty, extra hop via M)
        // The long chain should give lower C(X) since it is two hops from the fault.
        ServiceDependencyGraph shortChain = ServiceDependencyGraph.builder()
                .addEdge("X", "B", 0.9).build();
        ServiceDependencyGraph longChain = ServiceDependencyGraph.builder()
                .addEdge("X", "M", 0.9)
                .addEdge("M", "B", 0.9).build();

        Map<String, FaultHypothesis> hypsShort = Map.of(
                "X", hyp("X", 0.0), "B", hyp("B", 0.90));
        Map<String, FaultHypothesis> hypsLong = Map.of(
                "X", hyp("X", 0.0), "M", hyp("M", 0.0), "B", hyp("B", 0.90));

        DampedConfidencePropagator p = new DampedConfidencePropagator(0.80);

        double cxShort = p.propagate(hypsShort, shortChain).get("X");
        double cxLong  = p.propagate(hypsLong,  longChain).get("X");

        assertTrue(cxShort > cxLong,
                "Single-hop caller should have higher C than two-hop caller");
    }

    // -----------------------------------------------------------------------
    // Boundary: δ = 1.0 should match WeightedConfidencePropagator
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("δ=1.0: DampedPropagator ≡ WeightedConfidencePropagator")
    void deltOne_equalsUndamped() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.7)
                .addEdge("B", "C", 0.8).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.20),
                "C", hyp("C", 0.80));

        DampedConfidencePropagator d1   = new DampedConfidencePropagator(1.0);
        WeightedConfidencePropagator wcp = new WeightedConfidencePropagator();

        Map<String, Double> cd = d1.propagate(hyps, g);
        Map<String, Double> cw = wcp.propagate(hyps, g);

        g.getServices().forEach(s ->
            assertEquals(cw.get(s), cd.get(s), 1e-9,
                "δ=1 damped must match undamped for service " + s));
    }

    // -----------------------------------------------------------------------
    // Constructor validation
    // -----------------------------------------------------------------------

    @ParameterizedTest
    @ValueSource(doubles = {-0.1, 0.0, 1.1, 2.0})
    @DisplayName("Constructor rejects δ outside (0, 1]")
    void constructor_rejectsInvalidDamping(double bad) {
        assertThrows(IllegalArgumentException.class,
                () -> new DampedConfidencePropagator(bad));
    }

    // -----------------------------------------------------------------------
    // Output range guarantee
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("All C(s) ∈ [0, 1] for extreme inputs")
    void allValues_inUnitInterval() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 1.0)
                .addEdge("B", "C", 1.0).build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 1.0), "B", hyp("B", 1.0), "C", hyp("C", 1.0));

        new DampedConfidencePropagator(0.85).propagate(hyps, g).forEach((s, c) ->
            assertTrue(c >= 0.0 && c <= 1.0, "C(" + s + ")=" + c + " outside [0,1]"));
    }

    @Test
    @DisplayName("Cyclic graph throws IllegalStateException (use IterativePropagator instead)")
    void cyclicGraph_throws() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.5)
                .addEdge("B", "A", 0.5).build();
        assertThrows(IllegalStateException.class,
                () -> new DampedConfidencePropagator().propagate(
                        Map.of("A", hyp("A", 0.5), "B", hyp("B", 0.5)), g));
    }
}
