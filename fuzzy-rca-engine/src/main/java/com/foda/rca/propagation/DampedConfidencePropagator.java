package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Path-damped confidence propagator — the primary algorithmic refinement of FCP-RCA.
 *
 * <h2>Motivation (Section 3.3.1)</h2>
 *
 * <p>Undamped noisy-OR propagation is prone to <em>confidence inflation</em>: fault evidence
 * from a single deep dependency accumulates unrealistically high confidence at distant callers
 * when the call chain contains many hops, because each hop multiplies independent complement
 * factors. A damping coefficient δ ∈ (0, 1] applies an exponential decay per hop, reflecting
 * the intuition that fault evidence naturally weakens as it traverses service boundaries.</p>
 *
 * <h2>Mathematical Formulation (Equation 4, Section 3.3)</h2>
 *
 * <p>For service {@code s} with callee set {@code callees(s) = { t : s→t ∈ E }}:
 * <pre>
 *   P(s) = 1 – ∏_{t ∈ callees(s)} (1 – C(t) × w(s,t) × δ)        [Eq. 4a – damped upstream]
 *   C(s) = 1 – (1 – H(s)) × (1 – P(s))                            [Eq. 4b – noisy-OR merge]
 * </pre>
 * The effective contribution per hop is {@code C(t) × w(s,t) × δ}. Over a k-hop chain the
 * total decay factor is δ<sup>k</sup>, creating an exponential distance penalty.</p>
 *
 * <h2>Damping factor calibration</h2>
 *
 * <table border="1">
 *   <tr><th>δ</th><th>Decay at 3 hops</th><th>Decay at 5 hops</th></tr>
 *   <tr><td>1.00</td><td>none</td><td>none (undamped baseline)</td></tr>
 *   <tr><td>0.90</td><td>27 %</td><td>41 %</td></tr>
 *   <tr><td>0.85</td><td>39 %</td><td>56 % (recommended)</td></tr>
 *   <tr><td>0.75</td><td>58 %</td><td>76 %</td></tr>
 * </table>
 *
 * <p>The default δ = 0.85 was selected by a grid-search on the benchmark suite described in
 * Section 5.2; it achieves the best trade-off between propagation reach and rank accuracy.</p>
 *
 * <h2>Complexity</h2>
 * <p>O(|S| + |E|) — one reverse-topological traversal, same as the undamped variant.</p>
 *
 * @see WeightedConfidencePropagator the undamped baseline (δ = 1)
 * @see IterativeConfidencePropagator for cyclic dependency graphs
 */
@Slf4j
public class DampedConfidencePropagator implements ConfidencePropagator {

    /** Recommended damping factor: 15 % attenuation per hop. */
    public static final double DEFAULT_DAMPING_FACTOR = 0.85;

    /**
     * The damping coefficient δ ∈ (0, 1].
     * δ = 1.0 degenerates to undamped {@link WeightedConfidencePropagator} semantics.
     */
    @Getter
    private final double dampingFactor;

    /** Creates a propagator with the recommended damping factor ({@value DEFAULT_DAMPING_FACTOR}). */
    public DampedConfidencePropagator() {
        this(DEFAULT_DAMPING_FACTOR);
    }

    /**
     * Creates a propagator with a custom damping factor.
     *
     * @param dampingFactor δ ∈ (0, 1]; use 1.0 for undamped, 0.85 for recommended
     */
    public DampedConfidencePropagator(double dampingFactor) {
        if (dampingFactor <= 0.0 || dampingFactor > 1.0)
            throw new IllegalArgumentException(
                "dampingFactor must be in (0, 1], got: " + dampingFactor);
        this.dampingFactor = dampingFactor;
    }

    /**
     * {@inheritDoc}
     *
     * <p>Executes the damped backward propagation algorithm in a single reverse-topological
     * pass. Requires an acyclic dependency graph; use {@link IterativeConfidencePropagator}
     * for cyclic graphs.</p>
     *
     * @throws IllegalStateException if the graph contains a cycle
     */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        // Seed: C(s) = H(s)
        Map<String, Double> confidence = new LinkedHashMap<>();
        for (String s : graph.getServices()) {
            confidence.put(s, hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence() : 0.0);
        }

        // Reverse topological order: leaf dependencies first, top-level callers last
        List<String> reverseOrder = reversedTopologicalOrder(graph);
        log.debug("Damped propagation (δ={}) order: {}", dampingFactor, reverseOrder);

        for (String s : reverseOrder) {
            List<Edge> callees = graph.getOutgoingEdges(s);
            if (callees.isEmpty()) continue;

            // P(s) = 1 – ∏_t (1 – C(t) × w(s,t) × δ)
            double complementProduct = 1.0;
            for (Edge e : callees) {
                double ct         = confidence.getOrDefault(e.getTarget(), 0.0);
                double effectiveW = e.getWeight() * dampingFactor;
                complementProduct *= (1.0 - ct * effectiveW);
                log.debug("  {}->{}: C(t)={}, w={}, δ={}, contrib={}",
                          s, e.getTarget(), ct, e.getWeight(), dampingFactor, ct * effectiveW);
            }

            double p  = 1.0 - complementProduct;
            double hs = confidence.get(s);
            // C(s) = 1 – (1–H(s)) × (1–P(s))
            double cs = clamp(1.0 - (1.0 - hs) * (1.0 - p));
            confidence.put(s, cs);
            log.debug("Service '{}': H={}, P={} -> C={}", s, hs, p, cs);
        }

        return Collections.unmodifiableMap(confidence);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    static List<String> reversedTopologicalOrder(ServiceDependencyGraph graph) {
        List<String> order = graph.topologicalOrder(); // throws if cyclic
        List<String> rev = new ArrayList<>(order);
        Collections.reverse(rev);
        return rev;
    }

    static double clamp(double v) { return Math.min(1.0, Math.max(0.0, v)); }
}
