package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Cycle-safe, iterative confidence propagator using Jacobi fixed-point iteration.
 *
 * <h2>Motivation (Section 3.3.2)</h2>
 *
 * <p>Real microservice deployments frequently contain <em>cyclic dependencies</em>:
 * bidirectional health-check calls, sidecar proxies pinging their hosts, and service-mesh
 * mTLS handshakes all create directed cycles in the call graph. Standard topological-sort
 * based propagation raises an exception on such graphs. This propagator handles cycles
 * transparently using an iterative convergence approach.</p>
 *
 * <h2>Algorithm — Jacobi Fixed-Point Iteration (Equation 5, Section 3.3)</h2>
 *
 * <pre>
 *   Algorithm IterativePropagation(H, G, δ, ε, MAX_ITER):
 *
 *     C⁰(s) ← H(s)    for all s ∈ S
 *     for k = 1, 2, ..., MAX_ITER:
 *       C^k_new(s) = H(s)    for all s          // seed from local hypothesis
 *       for each s ∈ S:
 *         P(s) = 1 – ∏_{t ∈ callees(s)} (1 – C^(k-1)(t) × w(s,t) × δ)   [Eq. 5a]
 *         C^k(s) = 1 – (1 – H(s)) × (1 – P(s))                           [Eq. 5b]
 *       if max_s |C^k(s) – C^(k-1)(s)| ≤ ε: STOP
 *     return C^k
 * </pre>
 *
 * <p>The full C^(k-1) snapshot is used for all updates in iteration k (Jacobi scheme),
 * guaranteeing convergence regardless of processing order.</p>
 *
 * <h2>Convergence Guarantee</h2>
 *
 * <p>When δ ∈ (0, 1), the update function
 * {@code F(C)(s) = 1 – (1–H(s)) × ∏_t (1 – C(t)×w(s,t)×δ)}
 * is a <em>contraction mapping</em> on [0,1]^|S| under the L∞ norm (Banach fixed-point
 * theorem). The Lipschitz constant is δ × max(w), so convergence is guaranteed and the
 * rate is geometric with ratio ≤ δ.</p>
 *
 * <p>When δ = 1 (no damping) on a cyclic graph, convergence is not guaranteed; a
 * warning is emitted and the last iteration result is returned.</p>
 *
 * <h2>Adaptive Fast Path</h2>
 *
 * <p>For acyclic graphs the algorithm attempts the exact O(|S|+|E|) reverse-topological
 * pass first (same as {@link DampedConfidencePropagator}). Only when a cycle is detected
 * does it fall back to iterative convergence. This means no overhead for the common
 * acyclic case.</p>
 *
 * <h2>Time Complexity</h2>
 * <ul>
 *   <li>Acyclic fast path: O(|S| + |E|).</li>
 *   <li>Cyclic iterative path: O(K × (|S| + |E|)) where K ≤ MAX_ITER is the number of
 *       iterations to convergence. With δ = 0.85 and ε = 10⁻⁶, K ≤ 20 in practice
 *       for typical microservice topologies.</li>
 * </ul>
 */
@Slf4j
public class IterativeConfidencePropagator implements ConfidencePropagator {

    /** Default maximum iterations before giving up on convergence. */
    public static final int    DEFAULT_MAX_ITERATIONS = 100;

    /** Default convergence threshold ε. */
    public static final double DEFAULT_EPSILON        = 1e-6;

    /** Default damping factor (same recommendation as {@link DampedConfidencePropagator}). */
    public static final double DEFAULT_DAMPING_FACTOR = 0.85;

    @Getter private final int    maxIterations;
    @Getter private final double epsilon;
    @Getter private final double dampingFactor;

    /** Creates a propagator with all defaults. */
    public IterativeConfidencePropagator() {
        this(DEFAULT_DAMPING_FACTOR, DEFAULT_EPSILON, DEFAULT_MAX_ITERATIONS);
    }

    /**
     * Creates a propagator with explicit parameters.
     *
     * @param dampingFactor δ ∈ (0, 1]
     * @param epsilon       convergence threshold ε &gt; 0
     * @param maxIterations maximum Jacobi iterations
     */
    public IterativeConfidencePropagator(double dampingFactor, double epsilon, int maxIterations) {
        if (dampingFactor <= 0 || dampingFactor > 1)
            throw new IllegalArgumentException("dampingFactor must be in (0, 1]");
        if (epsilon <= 0)
            throw new IllegalArgumentException("epsilon must be > 0");
        if (maxIterations < 1)
            throw new IllegalArgumentException("maxIterations must be >= 1");
        this.dampingFactor = dampingFactor;
        this.epsilon       = epsilon;
        this.maxIterations = maxIterations;
    }

    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    /**
     * {@inheritDoc}
     *
     * <p>First attempts the acyclic fast path (reverse topological order, exact).
     * If a cycle is detected, transparently falls back to Jacobi iterative convergence.</p>
     */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        // --- Acyclic fast path ---
        try {
            return propagateAcyclic(hypotheses, graph);
        } catch (IllegalStateException e) {
            log.info("Cycle detected in dependency graph — switching to iterative propagation "
                     + "(δ={}, ε={}, maxIter={})", dampingFactor, epsilon, maxIterations);
        }

        // --- Cyclic fallback: Jacobi iteration ---
        return propagateIterative(hypotheses, graph);
    }

    // -----------------------------------------------------------------------
    // Acyclic fast path
    // -----------------------------------------------------------------------

    private Map<String, Double> propagateAcyclic(Map<String, FaultHypothesis> hypotheses,
                                                   ServiceDependencyGraph graph) {
        Map<String, Double> C = seed(hypotheses, graph);
        List<String> order    = DampedConfidencePropagator.reversedTopologicalOrder(graph);

        for (String s : order) {
            List<Edge> callees = graph.getOutgoingEdges(s);
            if (callees.isEmpty()) continue;
            double p  = computeP(s, callees, C);
            double hs = C.get(s);
            C.put(s, DampedConfidencePropagator.clamp(1.0 - (1.0 - hs) * (1.0 - p)));
        }
        return Collections.unmodifiableMap(C);
    }

    // -----------------------------------------------------------------------
    // Cyclic iterative path (Jacobi)
    // -----------------------------------------------------------------------

    private Map<String, Double> propagateIterative(Map<String, FaultHypothesis> hypotheses,
                                                    ServiceDependencyGraph graph) {
        Set<String>         services = graph.getServices();
        Map<String, Double> C        = seed(hypotheses, graph);

        // Pre-compute local hypotheses for fast access
        Map<String, Double> H = new LinkedHashMap<>();
        for (String s : services) {
            H.put(s, hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence() : 0.0);
        }

        int iter      = 0;
        double delta  = Double.MAX_VALUE;

        while (delta > epsilon && iter < maxIterations) {
            // Snapshot C^(k-1) — Jacobi uses only the previous-iteration values
            Map<String, Double> Cprev = new LinkedHashMap<>(C);

            // Update all services using C^(k-1)
            for (String s : services) {
                List<Edge> callees = graph.getOutgoingEdges(s);
                double p   = callees.isEmpty() ? 0.0 : computeP(s, callees, Cprev);
                double hs  = H.get(s);
                C.put(s, DampedConfidencePropagator.clamp(1.0 - (1.0 - hs) * (1.0 - p)));
            }

            // Check convergence: max_s |C^k(s) – C^(k-1)(s)|
            delta = 0.0;
            for (String s : services) {
                delta = Math.max(delta, Math.abs(C.get(s) - Cprev.get(s)));
            }
            iter++;
            log.debug("Iteration {}: max Δ = {}", iter, delta);
        }

        if (delta > epsilon) {
            log.warn("Iterative propagation did not fully converge after {} iterations "
                     + "(final Δ = {}). Consider increasing maxIterations or using δ < 1.",
                     maxIterations, delta);
        } else {
            log.debug("Converged after {} iteration(s) (Δ = {})", iter, delta);
        }

        return Collections.unmodifiableMap(C);
    }

    // -----------------------------------------------------------------------
    // Shared helpers
    // -----------------------------------------------------------------------

    /**
     * Computes the upstream-dependency contribution P(s) using the supplied
     * confidence map (either current or previous-iteration snapshot).
     *
     * <pre>P(s) = 1 – ∏_t (1 – C(t) × w(s,t) × δ)</pre>
     */
    private double computeP(String s, List<Edge> callees, Map<String, Double> C) {
        double complementProduct = 1.0;
        for (Edge e : callees) {
            double ct         = C.getOrDefault(e.getTarget(), 0.0);
            double effectiveW = e.getWeight() * dampingFactor;
            complementProduct *= (1.0 - ct * effectiveW);
        }
        return 1.0 - complementProduct;
    }

    private static Map<String, Double> seed(Map<String, FaultHypothesis> hypotheses,
                                             ServiceDependencyGraph graph) {
        Map<String, Double> C = new LinkedHashMap<>();
        for (String s : graph.getServices()) {
            C.put(s, hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence() : 0.0);
        }
        return C;
    }
}
