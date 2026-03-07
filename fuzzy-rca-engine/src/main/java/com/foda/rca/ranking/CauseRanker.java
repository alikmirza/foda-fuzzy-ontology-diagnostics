package com.foda.rca.ranking;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.RankedCause;
import com.foda.rca.model.ServiceDependencyGraph;

import java.util.List;
import java.util.Map;

/**
 * Ranking Layer interface (Section 3.4 of the FCP-RCA paper).
 *
 * <p>Converts the propagated confidence map into an ordered list of
 * {@link RankedCause} objects, one per candidate root cause, sorted by
 * descending final confidence score C(s).</p>
 *
 * <p>Only services whose confidence exceeds a configurable threshold are
 * included in the result to suppress noise from unrelated healthy services.</p>
 */
public interface CauseRanker {

    /**
     * Rank services by their propagated fault confidence and return the top-k.
     *
     * @param propagatedConfidences final confidence C(s) per service
     * @param hypotheses            local fault hypotheses (for evidence breakdown)
     * @param graph                 dependency graph (for causal path reconstruction)
     * @param k                     maximum number of root causes to return
     * @return ordered list of ranked root causes (descending confidence), size ≤ k
     */
    List<RankedCause> rank(Map<String, Double> propagatedConfidences,
                           Map<String, FaultHypothesis> hypotheses,
                           ServiceDependencyGraph graph,
                           int k);
}
