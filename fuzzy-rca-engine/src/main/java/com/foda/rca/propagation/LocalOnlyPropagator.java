package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;

import java.util.*;

/**
 * Ablation baseline: no propagation — C(s) = H(s) for every service.
 *
 * <p>This propagator deliberately ignores the dependency graph and returns each service's
 * raw local fault hypothesis as its final confidence score. Its purpose is to quantify
 * the <em>isolated contribution of confidence propagation</em> to RCA accuracy in the
 * ablation study (Section 5.3, Table 4).</p>
 *
 * <p>When {@code LocalOnlyPropagator} outperforms the full FCP-RCA pipeline, the symptom
 * signal within individual service metrics is sufficient for localisation and the dependency
 * topology provides no additional discriminating power — a useful diagnostic in itself.</p>
 *
 * <h2>Ablation study mapping</h2>
 * <pre>
 *   Variant            Propagator               Purpose
 *   ─────────────────────────────────────────────────────────────
 *   FCP-RCA (full)     DampedConfidencePropagator(0.85)   proposed
 *   –Damping (δ=1)     WeightedConfidencePropagator       ablate damping
 *   –Propagation       LocalOnlyPropagator                ablate propagation
 *   –Weights           UniformWeightPropagator            ablate weight calibration
 * </pre>
 */
public class LocalOnlyPropagator implements ConfidencePropagator {

    /** {@inheritDoc} */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph,     "graph must not be null");

        Map<String, Double> result = new LinkedHashMap<>();
        for (String s : graph.getServices()) {
            result.put(s, hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence() : 0.0);
        }
        return Collections.unmodifiableMap(result);
    }
}
