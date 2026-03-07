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
 * Tests for {@link WeightedConfidencePropagator}.
 * Verifies the Noisy-OR aggregation formula and propagation monotonicity properties.
 */
@DisplayName("WeightedConfidencePropagator Tests")
class WeightedConfidencePropagatorTest {

    private WeightedConfidencePropagator propagator;

    @BeforeEach
    void setUp() {
        propagator = new WeightedConfidencePropagator();
    }

    private FaultHypothesis hyp(String id, double h) {
        return FaultHypothesis.builder()
                .serviceId(id).localConfidence(h)
                .dominantFaultCategory("TEST")
                .firedRules(List.of()).ruleFireStrengths(Map.of())
                .build();
    }

    // -----------------------------------------------------------------------
    // Single-node graph
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Source node: C(s) = H(s) when no predecessors")
    void sourceNode_confidenceEqualsLocalHypothesis() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addService("svc-a")
                .build();
        Map<String, FaultHypothesis> hyps = Map.of("svc-a", hyp("svc-a", 0.72));

        Map<String, Double> result = propagator.propagate(hyps, g);

        assertEquals(0.72, result.get("svc-a"), 1e-9,
                "Isolated source node: C must equal H");
    }

    // -----------------------------------------------------------------------
    // Linear chain: A → B → C
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Linear chain A→B→C: fault at C (leaf) propagates to B then to A")
    void linearChain_backwardPropagation() {
        // Edge A→B→C means A calls B, B calls C.
        // C is a dependency of B; B is a dependency of A.
        // Fault at C propagates: C(C) high → C(B) elevated → C(A) elevated.
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("B", "C", 0.9)
                .build();

        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),   // caller A: healthy (shows symptoms only)
                "B", hyp("B", 0.10),   // intermediate B: mildly symptomatic
                "C", hyp("C", 0.80)    // leaf dependency C: clearly faulty
        );

        Map<String, Double> c = propagator.propagate(hyps, g);

        // C is a leaf: C(C) = H(C) = 0.80
        assertEquals(0.80, c.get("C"), 1e-9, "Leaf C: C must equal H");

        // B calls C (depends on C): B should be elevated due to C's fault
        assertTrue(c.get("B") > 0.10, "C(B) must exceed H(B) due to dependency fault at C");

        // A calls B (depends on B): A should also be elevated
        assertTrue(c.get("A") > 0.05, "C(A) must exceed H(A) due to propagated fault");

        // Monotonicity: fault-source C should rank highest or equal to B
        assertTrue(c.get("C") >= c.get("B"),
                "Fault-origin leaf C should have higher or equal confidence than its caller B");
    }

    @Test
    @DisplayName("Noisy-OR formula: manual verification for single edge (backward)")
    void noisyOR_manualVerification() {
        // A → B: A calls B (A depends on B). w=0.7, H(A)=0.05, H(B)=0.80
        // Backward propagation: process B first (leaf), then A.
        // C(B) = H(B) = 0.80 (leaf, no callees)
        // P(A) = 1 - (1 - C(B)*w) = 1 - (1 - 0.80*0.7) = 1 - 0.44 = 0.56
        // C(A) = 1 - (1-H(A))*(1-P(A)) = 1 - 0.95*0.44 = 1 - 0.418 = 0.582
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.7)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),  // caller A: healthy
                "B", hyp("B", 0.80)  // callee B: faulty
        );

        Map<String, Double> c = propagator.propagate(hyps, g);

        assertEquals(0.80,  c.get("B"), 1e-9, "Leaf B: C must equal H");
        assertEquals(0.582, c.get("A"), 1e-3, "A inherits B's fault via noisy-OR");
    }

    // -----------------------------------------------------------------------
    // Multi-dependency graph: A → B and A → C (A has two callees)
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Multi-dependency: A calling two faulty services amplifies A's confidence")
    void multiDependency_twoFaultyCallees_amplifyCaller() {
        // A calls B and C; B and C are both faulty.
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.8)
                .addEdge("A", "C", 0.9)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.80),
                "C", hyp("C", 0.75)
        );

        // Compare with a version where A has only one faulty dependency
        Map<String, Double> singleDep = propagator.propagate(
                Map.of("A", hyp("A", 0.05), "B", hyp("B", 0.80)),
                ServiceDependencyGraph.builder().addEdge("A","B",0.8).build());

        Map<String, Double> dual = propagator.propagate(hyps, g);

        assertTrue(dual.get("A") > singleDep.get("A"),
                "Two faulty dependencies must produce higher C(A) than one");
    }

    // -----------------------------------------------------------------------
    // All confidences in [0, 1]
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("All propagated confidences are in [0, 1]")
    void allConfidences_inUnitInterval() {
        // A → B, A → C, B → C, C → D  (A is top caller, D is leaf dependency)
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.9)
                .addEdge("A", "C", 0.7)
                .addEdge("B", "C", 0.8)
                .addEdge("C", "D", 1.0)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.10),   // top caller: mildly symptomatic
                "B", hyp("B", 0.30),
                "C", hyp("C", 0.60),
                "D", hyp("D", 0.95)    // leaf dependency: root cause
        );

        Map<String, Double> c = propagator.propagate(hyps, g);

        c.forEach((svc, conf) ->
            assertTrue(conf >= 0.0 && conf <= 1.0,
                "C(" + svc + ")=" + conf + " is outside [0, 1]"));
    }

    // -----------------------------------------------------------------------
    // Monotonicity: C(s) ≥ H(s)
    // -----------------------------------------------------------------------

    @Test
    @DisplayName("Monotonicity: C(s) is never less than H(s)")
    void monotonicity_confidenceNeverDecreases() {
        // C is the leaf dependency (root cause). A is the top caller.
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.6)
                .addEdge("B", "C", 0.8)
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.05),
                "B", hyp("B", 0.20),
                "C", hyp("C", 0.50)  // leaf: the fault source
        );

        Map<String, Double> c = propagator.propagate(hyps, g);

        hyps.forEach((svc, h) ->
            assertTrue(c.get(svc) >= h.getLocalConfidence() - 1e-9,
                "C(" + svc + ")=" + c.get(svc) + " < H(" + svc + ")=" +
                h.getLocalConfidence() + " violates monotonicity"));
    }

    @Test
    @DisplayName("Cycle detection: topological sort throws on cyclic graph")
    void cyclicGraph_throwsException() {
        ServiceDependencyGraph g = ServiceDependencyGraph.builder()
                .addEdge("A", "B", 0.5)
                .addEdge("B", "C", 0.5)
                .addEdge("C", "A", 0.5)  // cycle!
                .build();
        Map<String, FaultHypothesis> hyps = Map.of(
                "A", hyp("A", 0.5),
                "B", hyp("B", 0.5),
                "C", hyp("C", 0.5)
        );
        assertThrows(IllegalStateException.class,
                () -> propagator.propagate(hyps, g));
    }
}
