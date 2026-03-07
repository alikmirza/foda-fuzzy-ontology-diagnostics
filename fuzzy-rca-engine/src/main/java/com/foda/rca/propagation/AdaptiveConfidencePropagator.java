package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.Map;
import java.util.Objects;

/**
 * Propagator that automatically selects the optimal algorithm based on graph topology.
 *
 * <h2>Selection Logic</h2>
 *
 * <table border="1">
 *   <tr><th>Graph topology</th><th>Selected propagator</th><th>Reason</th></tr>
 *   <tr>
 *     <td>Acyclic (DAG)</td>
 *     <td>{@link DampedConfidencePropagator}</td>
 *     <td>Exact O(|S|+|E|) reverse-topological pass; no iteration needed.</td>
 *   </tr>
 *   <tr>
 *     <td>Cyclic</td>
 *     <td>{@link IterativeConfidencePropagator}</td>
 *     <td>Jacobi fixed-point iteration with Banach-guaranteed convergence (δ &lt; 1).</td>
 *   </tr>
 * </table>
 *
 * <p>Both branches share the same damping factor δ and produce results that are
 * numerically identical on acyclic graphs (the iterative propagator's fast path is
 * equivalent to the damped propagator). The adaptive selection therefore adds no
 * overhead for the common acyclic case and requires no user configuration.</p>
 *
 * <h2>Usage</h2>
 * <pre>
 *   // Recommended way — created automatically by FuzzyRcaEngineImpl when no explicit
 *   // propagator is set:
 *   FuzzyRcaEngineImpl.builder().withDampingFactor(0.85).build()
 *
 *   // Direct use:
 *   ConfidencePropagator propagator = new AdaptiveConfidencePropagator(0.85);
 *   Map&lt;String, Double&gt; C = propagator.propagate(hypotheses, graph);
 * </pre>
 *
 * <h2>Thread safety</h2>
 * <p>This class is stateless after construction and therefore thread-safe.</p>
 *
 * @see DampedConfidencePropagator the acyclic algorithm (§ 3.3, Eq. 4)
 * @see IterativeConfidencePropagator the cyclic algorithm (§ 3.3, Eq. 5)
 */
@Slf4j
public class AdaptiveConfidencePropagator implements ConfidencePropagator {

    /** Recommended damping factor δ = 0.85 (Section 5.2 calibration). */
    public static final double DEFAULT_DAMPING_FACTOR = 0.85;

    @Getter
    private final double dampingFactor;

    private final DampedConfidencePropagator    acyclicPropagator;
    private final IterativeConfidencePropagator cyclicPropagator;

    /** Creates an adaptive propagator with the recommended damping factor (0.85). */
    public AdaptiveConfidencePropagator() {
        this(DEFAULT_DAMPING_FACTOR);
    }

    /**
     * Creates an adaptive propagator with the given damping factor.
     *
     * @param dampingFactor δ ∈ (0, 1]; use 0.85 for the paper's recommended setting
     */
    public AdaptiveConfidencePropagator(double dampingFactor) {
        if (dampingFactor <= 0.0 || dampingFactor > 1.0)
            throw new IllegalArgumentException(
                "dampingFactor must be in (0, 1], got: " + dampingFactor);
        this.dampingFactor    = dampingFactor;
        this.acyclicPropagator = new DampedConfidencePropagator(dampingFactor);
        this.cyclicPropagator  = new IterativeConfidencePropagator(
                dampingFactor,
                IterativeConfidencePropagator.DEFAULT_EPSILON,
                IterativeConfidencePropagator.DEFAULT_MAX_ITERATIONS);
    }

    /**
     * {@inheritDoc}
     *
     * <p>Inspects the graph topology via {@link ServiceDependencyGraph#hasCycle()} and
     * delegates to the appropriate propagator:
     * <ul>
     *   <li>Acyclic graph → {@link DampedConfidencePropagator} (exact, O(|S|+|E|)).</li>
     *   <li>Cyclic graph  → {@link IterativeConfidencePropagator} (Jacobi convergence).</li>
     * </ul>
     * </p>
     */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        if (graph.hasCycle()) {
            log.info("Adaptive propagator: cyclic graph detected — using IterativeConfidencePropagator "
                     + "(δ={})", dampingFactor);
            return cyclicPropagator.propagate(hypotheses, graph);
        } else {
            log.debug("Adaptive propagator: acyclic graph — using DampedConfidencePropagator (δ={})",
                      dampingFactor);
            return acyclicPropagator.propagate(hypotheses, graph);
        }
    }
}
