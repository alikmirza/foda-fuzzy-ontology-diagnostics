package com.foda.rca.model;

import lombok.Builder;
import lombok.Value;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Complete output of one FCP-RCA pipeline execution.
 *
 * <p>This is the top-level result object returned by
 * {@link com.foda.rca.api.FuzzyRcaEngine#diagnose}.  It contains:</p>
 * <ol>
 *   <li>The ordered list of root-cause candidates (Section 3.4).</li>
 *   <li>The full fuzzification snapshot for each service (Section 3.1).</li>
 *   <li>The local fault hypotheses (Section 3.2).</li>
 *   <li>The propagated confidence scores (Section 3.3).</li>
 *   <li>Metadata for reproducibility (timestamp, graph topology summary).</li>
 * </ol>
 */
@Value
@Builder
public class DiagnosisResult {

    /** Unique identifier for this diagnosis run (UUID). */
    String diagnosisId;

    /** Wall-clock time at which the pipeline was executed. */
    Instant timestamp;

    /**
     * Top-k ranked root causes, ordered by {@link RankedCause#getFinalConfidence()}
     * descending (index 0 = most likely root cause).
     */
    List<RankedCause> rankedCauses;

    /**
     * Fuzzified health vectors per service, keyed by serviceId.
     * Preserved for audit / re-evaluation without re-running fuzzification.
     */
    Map<String, FuzzyVector> fuzzyVectors;

    /**
     * Local fault hypotheses per service, keyed by serviceId.
     * Documents what the inference layer decided before propagation.
     */
    Map<String, FaultHypothesis> faultHypotheses;

    /**
     * Final propagated confidence scores per service, keyed by serviceId.
     * Useful for heatmap visualisation in dashboards or papers.
     */
    Map<String, Double> propagatedConfidences;

    /** Number of services in the dependency graph analysed. */
    int serviceCount;

    /** Number of dependency edges in the graph. */
    int edgeCount;

    /**
     * Returns the top-ranked root cause, or {@code null} if no services
     * showed elevated fault confidence.
     */
    public RankedCause topCause() {
        return rankedCauses.isEmpty() ? null : rankedCauses.get(0);
    }
}
