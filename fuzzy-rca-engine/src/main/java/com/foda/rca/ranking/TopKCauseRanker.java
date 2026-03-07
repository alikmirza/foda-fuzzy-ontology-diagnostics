package com.foda.rca.ranking;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.RankedCause;
import com.foda.rca.model.ServiceDependencyGraph;
import com.foda.rca.model.ServiceDependencyGraph.Edge;
import lombok.extern.slf4j.Slf4j;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Top-k implementation of {@link CauseRanker} with causal path reconstruction.
 *
 * <h2>Ranking Algorithm (Section 3.4)</h2>
 * <ol>
 *   <li>Filter services with C(s) &gt; {@code confidenceThreshold}.</li>
 *   <li>Sort descending by C(s).</li>
 *   <li>Keep at most {@code k} candidates.</li>
 *   <li>For each candidate, reconstruct the highest-confidence causal path via
 *       a greedy backward traversal of the dependency graph.</li>
 *   <li>Compute P(s) = C(s) − H(s) contribution from upstream (for reporting).</li>
 * </ol>
 *
 * <p>A service with C(s) ≤ threshold is considered healthy and excluded from results,
 * keeping the output actionable for operators.</p>
 */
@Slf4j
public class TopKCauseRanker implements CauseRanker {

    /**
     * Default minimum confidence required for a service to be listed as a root-cause
     * candidate.  Set to 0.1 to suppress healthy services with near-zero confidence.
     */
    public static final double DEFAULT_CONFIDENCE_THRESHOLD = 0.10;

    private final double confidenceThreshold;

    /** Creates a ranker with the default threshold ({@value DEFAULT_CONFIDENCE_THRESHOLD}). */
    public TopKCauseRanker() {
        this(DEFAULT_CONFIDENCE_THRESHOLD);
    }

    /**
     * Creates a ranker with a custom confidence threshold.
     *
     * @param confidenceThreshold minimum C(s) to include a service; must be in [0, 1)
     */
    public TopKCauseRanker(double confidenceThreshold) {
        if (confidenceThreshold < 0 || confidenceThreshold >= 1.0)
            throw new IllegalArgumentException("Threshold must be in [0, 1)");
        this.confidenceThreshold = confidenceThreshold;
    }

    /** {@inheritDoc} */
    @Override
    public List<RankedCause> rank(Map<String, Double> propagatedConfidences,
                                  Map<String, FaultHypothesis> hypotheses,
                                  ServiceDependencyGraph graph,
                                  int k) {
        if (k <= 0) throw new IllegalArgumentException("k must be > 0");

        List<RankedCause> result = propagatedConfidences.entrySet().stream()
                .filter(e -> e.getValue() > confidenceThreshold)
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(k)
                .map(entry -> buildRankedCause(entry, hypotheses, graph, propagatedConfidences))
                .collect(Collectors.toList());

        // Re-number ranks after filtering (1-based)
        for (int i = 0; i < result.size(); i++) {
            result.set(i, rebuild(result.get(i), i + 1));
        }

        log.info("Ranked {} root-cause candidate(s) (threshold={}, k={})",
                 result.size(), confidenceThreshold, k);
        return Collections.unmodifiableList(result);
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private RankedCause buildRankedCause(Map.Entry<String, Double> entry,
                                          Map<String, FaultHypothesis> hypotheses,
                                          ServiceDependencyGraph graph,
                                          Map<String, Double> confidences) {
        String serviceId       = entry.getKey();
        double finalConfidence = entry.getValue();
        FaultHypothesis hyp    = hypotheses.getOrDefault(serviceId,
                defaultHypothesis(serviceId));

        double localConf     = hyp.getLocalConfidence();
        // P(s) derived from the noisy-OR inverse: 1 - (1-C)/(1-H) ... but simpler to report
        // the complement-product contribution stored during propagation.
        // Here we expose the delta for transparency.
        double propagatedConf = Math.max(0.0, finalConfidence - localConf * (1.0 - finalConfidence));
        propagatedConf = Math.min(1.0, propagatedConf);

        List<String> causalPath = reconstructCausalPath(serviceId, graph, confidences);

        return RankedCause.builder()
                .rank(0) // placeholder — re-numbered after filtering
                .serviceId(serviceId)
                .finalConfidence(finalConfidence)
                .localConfidence(localConf)
                .propagatedConfidence(propagatedConf)
                .faultCategory(hyp.getDominantFaultCategory())
                .causalPath(causalPath)
                .explanation("") // filled by ExplanationBuilder later
                .build();
    }

    /**
     * Reconstructs the highest-confidence causal path leading to {@code target} via
     * a greedy backward traversal: at each step, follow the incoming edge whose source
     * has the highest propagated confidence.
     *
     * <p>The path is reported from the ultimate upstream source to {@code target}, giving
     * readers the "fault propagation chain" rather than just the endpoint.</p>
     */
    private List<String> reconstructCausalPath(String target,
                                                ServiceDependencyGraph graph,
                                                Map<String, Double> confidences) {
        LinkedList<String> path = new LinkedList<>();
        path.addFirst(target);
        Set<String> visited = new HashSet<>();
        visited.add(target);

        String current = target;
        while (true) {
            List<Edge> incoming = graph.getIncomingEdges(current);
            if (incoming.isEmpty()) break;

            // Greedy: follow the predecessor with the highest confidence
            Optional<Edge> bestEdge = incoming.stream()
                    .filter(e -> !visited.contains(e.getSource()))
                    .max(Comparator.comparingDouble(
                            e -> confidences.getOrDefault(e.getSource(), 0.0) * e.getWeight()));

            if (bestEdge.isEmpty()) break;

            String next = bestEdge.get().getSource();
            path.addFirst(next);
            visited.add(next);
            current = next;
        }

        return List.copyOf(path);
    }

    private static RankedCause rebuild(RankedCause rc, int rank) {
        return RankedCause.builder()
                .rank(rank)
                .serviceId(rc.getServiceId())
                .finalConfidence(rc.getFinalConfidence())
                .localConfidence(rc.getLocalConfidence())
                .propagatedConfidence(rc.getPropagatedConfidence())
                .faultCategory(rc.getFaultCategory())
                .causalPath(rc.getCausalPath())
                .explanation(rc.getExplanation())
                .build();
    }

    private static FaultHypothesis defaultHypothesis(String serviceId) {
        return FaultHypothesis.builder()
                .serviceId(serviceId)
                .localConfidence(0.0)
                .dominantFaultCategory("UNKNOWN")
                .firedRules(List.of())
                .ruleFireStrengths(Map.of())
                .build();
    }
}
