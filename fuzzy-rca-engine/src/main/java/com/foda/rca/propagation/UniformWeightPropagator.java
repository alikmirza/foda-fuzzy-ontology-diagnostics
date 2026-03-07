package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Ablation baseline: uniform edge weights (w = 1.0 for all edges) with damping.
 *
 * <p>This propagator applies the same damped noisy-OR formula as
 * {@link DampedConfidencePropagator} but replaces every calibrated edge weight with the
 * uniform value 1.0. Its purpose in the ablation study (Section 5.3) is to isolate the
 * contribution of <em>calibrated coupling weights</em>: if FCP-RCA with calibrated weights
 * significantly outperforms this baseline, the weight calibration step is justified.</p>
 *
 * <p>Formula (same structure as {@link DampedConfidencePropagator} with w ≡ 1):
 * <pre>
 *   P(s) = 1 – ∏_{t ∈ callees(s)} (1 – C(t) × δ)
 *   C(s) = 1 – (1 – H(s)) × (1 – P(s))
 * </pre>
 * </p>
 */
@Slf4j
public class UniformWeightPropagator implements ConfidencePropagator {

    /** Uniform edge weight applied regardless of the graph's actual edge weights. */
    private static final double UNIFORM_WEIGHT = 1.0;

    @Getter
    private final double dampingFactor;

    /** Creates a baseline with the default damping factor. */
    public UniformWeightPropagator() {
        this(DampedConfidencePropagator.DEFAULT_DAMPING_FACTOR);
    }

    /**
     * Creates a baseline with a custom damping factor.
     *
     * @param dampingFactor δ ∈ (0, 1]
     */
    public UniformWeightPropagator(double dampingFactor) {
        if (dampingFactor <= 0 || dampingFactor > 1)
            throw new IllegalArgumentException("dampingFactor must be in (0, 1]");
        this.dampingFactor = dampingFactor;
    }

    /** {@inheritDoc} */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        Map<String, Double> C = new LinkedHashMap<>();
        for (String s : graph.getServices()) {
            C.put(s, hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence() : 0.0);
        }

        List<String> order = DampedConfidencePropagator.reversedTopologicalOrder(graph);

        for (String s : order) {
            List<Edge> callees = graph.getOutgoingEdges(s);
            if (callees.isEmpty()) continue;

            // Use UNIFORM_WEIGHT = 1.0, ignoring actual edge weights
            double complementProduct = 1.0;
            for (Edge e : callees) {
                double ct = C.getOrDefault(e.getTarget(), 0.0);
                complementProduct *= (1.0 - ct * UNIFORM_WEIGHT * dampingFactor);
            }
            double p  = 1.0 - complementProduct;
            double hs = C.get(s);
            C.put(s, DampedConfidencePropagator.clamp(1.0 - (1.0 - hs) * (1.0 - p)));
        }

        log.debug("UniformWeightPropagator completed (δ={})", dampingFactor);
        return Collections.unmodifiableMap(C);
    }
}
