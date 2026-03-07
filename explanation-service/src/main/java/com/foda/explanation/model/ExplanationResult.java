package com.foda.explanation.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Structured explanation produced by the explanation service.
 * Stored in PostgreSQL diagnostic_events table.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ExplanationResult {

    private String explanationId;
    private String diagnosticId;
    private String serviceId;
    private String timestamp;

    // Diagnostic summary
    private String diagnosticResult;   // fault type name
    private Double fuzzyConfidence;    // FCI value
    private Double mlAnomalyScore;
    private Double mlConfidence;
    private Boolean crispConfidence;   // true if FCI >= 0.7

    // Explanation components
    private List<CausalStep> causalChain;
    private String ontologyIri;
    private List<String> suggestedActions;
    private Map<String, Object> provenance;

    // Human-readable explanation
    private String naturalLanguageExplanation;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CausalStep {
        private int step;
        private String cause;
        private String effect;
        private String metric;
        private Double value;
        private String threshold;
    }
}
