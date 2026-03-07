package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Default implementation of {@link ConfidencePropagator} using the Noisy-OR aggregation
 * formula and a topological traversal of the dependency graph.
 *
 * <h2>Algorithm (Section 3.3)</h2>
 * <pre>
 * Algorithm WeightedPropagation(hypotheses H, graph G):
 *   C ← copy of H (initial confidence = local hypothesis)
 *   for each s in topologicalOrder(G):
 *     P(s) ← 1 – ∏_{u ∈ pred(s)} (1 – C[u] × w(u,s))
 *     C[s] ← 1 – (1 – H[s]) × (1 – P[s])        // noisy-OR merge
 *   return C
 * </pre>
 *
 * <h2>Key Properties</h2>
 * <ul>
 *   <li><strong>RCA semantics:</strong> Propagates BACKWARD along the call graph. An edge
 *       A→B (A calls B) means B's fault can cause A's symptoms. We therefore propagate
 *       fault confidence from callees (B) toward callers (A), so that the origin of the
 *       fault accumulates the highest score.</li>
 *   <li><strong>Monotone:</strong> C(s) ≥ H(s) — evidence from dependencies never reduces
 *       confidence of the caller.</li>
 *   <li><strong>Bounded:</strong> C(s) ∈ [0, 1] for all s.</li>
 *   <li><strong>Multi-path:</strong> Independent dependency paths aggregate via complementary
 *       product — equivalent to "at least one dependency is faulty".</li>
 *   <li><strong>Complexity:</strong> O(|S| + |E|) — linear in graph size.</li>
 * </ul>
 */
@Slf4j
public class WeightedConfidencePropagator implements ConfidencePropagator {

    /**
     * {@inheritDoc}
     *
     * <p>Processes services in <em>reverse</em> topological order (leaf callees first,
     * entry-point callers last) so that when C(s) is computed, the final confidence of
     * all of s's callees (dependencies) is already available.</p>
     *
     * <p>For each service s the formula is:
     * <pre>
     *   P(s) = 1 – ∏_{t ∈ callees(s)} (1 – C(t) × w(s,t))   // dependency contribution
     *   C(s) = 1 – (1 – H(s)) × (1 – P(s))                   // noisy-OR merge
     * </pre>
     * where callees(s) = {t : s→t in the call graph} and w(s,t) is the edge weight.</p>
     */
    @Override
    public Map<String, Double> propagate(Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph) {
        Objects.requireNonNull(hypotheses, "hypotheses must not be null");
        Objects.requireNonNull(graph, "graph must not be null");

        // Initialise C[s] = H[s] for all services
        Map<String, Double> confidence = new LinkedHashMap<>();
        for (String s : graph.getServices()) {
            double h = hypotheses.containsKey(s)
                    ? hypotheses.get(s).getLocalConfidence()
                    : 0.0;
            confidence.put(s, h);
        }

        // Reverse topological order: process leaf dependencies first, entry-callers last.
        // This ensures callees are finalised before their callers are processed.
        List<String> order = graph.topologicalOrder();
        List<String> reverseOrder = new ArrayList<>(order);
        Collections.reverse(reverseOrder);
        log.debug("Backward propagation order: {}", reverseOrder);

        for (String s : reverseOrder) {
            // callees(s) = services that s calls (its dependencies)
            List<Edge> outgoingEdges = graph.getOutgoingEdges(s);

            if (outgoingEdges.isEmpty()) {
                // Leaf node (no dependencies): C(s) = H(s), nothing to propagate in
                log.debug("Leaf service '{}': C={} (local only)", s, confidence.get(s));
                continue;
            }

            // Compute dependency contribution P(s) = 1 – ∏(1 – C[t] × w(s,t))
            double complementProduct = 1.0;
            for (Edge edge : outgoingEdges) {
                double ct = confidence.getOrDefault(edge.getTarget(), 0.0);
                double w  = edge.getWeight();
                complementProduct *= (1.0 - ct * w);
                log.debug("  Dep edge {}->{}: C[t]={}, w={}", s, edge.getTarget(), ct, w);
            }
            double propagated = 1.0 - complementProduct;   // P(s)

            // Merge local hypothesis with dependency evidence via bounded sum (noisy-OR)
            double hs = confidence.get(s);                 // H(s) already stored
            double cs = 1.0 - (1.0 - hs) * (1.0 - propagated);
            cs = Math.min(1.0, Math.max(0.0, cs));         // numerical guard

            confidence.put(s, cs);
            log.debug("Service '{}': H={}, P={} -> C={}", s, hs, propagated, cs);
        }

        return Collections.unmodifiableMap(confidence);
    }
}
