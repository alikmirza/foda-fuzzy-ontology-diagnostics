package com.foda.rca.propagation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.extern.slf4j.Slf4j;

import java.util.*;

/**
 * Upper-bound baseline propagator using max-aggregation instead of noisy-OR.
 *
 * <h2>Motivation (Section 5.3 — Ablation Study)</h2>
 *
 * <p>The {@link WeightedConfidencePropagator} uses the probabilistic noisy-OR formula, which
 * models fault evidence from multiple independent callees. As a contrasting upper-bound
 * baseline, this propagator instead takes the <em>maximum</em> callee contribution:</p>
 *
 * <pre>
 *   P(s) = max_{t ∈ callees(s)} { C(t) × w(s,t) }          [Eq. UB — max aggregation]
 *   C(s) = max { H(s),  P(s) }                              [take the stronger signal]
 * </pre>
 *
 * <p>Max aggregation provides an upper bound on the noisy-OR confidence: because
 * {@code max(x, y) ≥ 1 – (1–x)(1–y)} for x, y ∈ [0,1], a service that scores highly
 * under noisy-OR will always score at least as high under max aggregation. However,
 * max aggregation can be overly optimistic when multiple independent paths all carry
 * moderate confidence: noisy-OR accumulates them while max-aggregation ignores all
 * but the strongest path.</p>
 *
 * <h2>Ablation hypothesis</h2>
 * <p>If FCP-RCA's noisy-OR propagation significantly outperforms max aggregation in MRR
 * and NDCG@k, this confirms that multi-path accumulation contributes to ranking accuracy
 * beyond simply following the single strongest call path.</p>
 *
 * <h2>Properties</h2>
 * <ul>
 *   <li><strong>Monotone:</strong> C(s) ≥ H(s) for all s.</li>
 *   <li><strong>Bounded:</strong> C(s) ∈ [0, 1].</li>
 *   <li><strong>No multi-path accumulation:</strong> independent fault paths do NOT
 *       compound; only the single most influential callee contributes.</li>
 *   <li><strong>Complexity:</strong> O(|S| + |E|) — same as noisy-OR variants.</li>
 * </ul>
 *
 * @see WeightedConfidencePropagator the production noisy-OR propagator
 * @see LocalOnlyPropagator the lower-bound baseline (no propagation)
 */
@Slf4j
public class MaxPropagationBaseline implements ConfidencePropagator {

    /**
     * {@inheritDoc}
     *
     * <p>Traverses the dependency graph in reverse topological order (leaf callees first).
     * For each caller {@code s}, takes the maximum weighted callee confidence as the
     * dependency contribution, then merges with the local hypothesis via max.</p>
     *
     * @throws IllegalStateException if the graph contains a cycle; use
     *         {@link IterativeConfidencePropagator} for cyclic graphs
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

        // Reverse topological order: leaf callees first, entry callers last
        List<String> order = graph.topologicalOrder();
        List<String> reverseOrder = new ArrayList<>(order);
        Collections.reverse(reverseOrder);
        log.debug("MaxPropagation order: {}", reverseOrder);

        for (String s : reverseOrder) {
            List<Edge> callees = graph.getOutgoingEdges(s);
            if (callees.isEmpty()) continue;

            // P(s) = max_{t ∈ callees(s)} { C(t) × w(s,t) }
            double maxContrib = callees.stream()
                    .mapToDouble(e -> confidence.getOrDefault(e.getTarget(), 0.0) * e.getWeight())
                    .max()
                    .orElse(0.0);

            // C(s) = max(H(s), P(s))
            double hs = confidence.get(s);
            double cs = Math.max(hs, maxContrib);
            confidence.put(s, cs);
            log.debug("MaxBaseline '{}': H={}, P(max)={} -> C={}", s, hs, maxContrib, cs);
        }

        return Collections.unmodifiableMap(confidence);
    }
}
