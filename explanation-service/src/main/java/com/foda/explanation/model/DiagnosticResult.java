package com.foda.explanation.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

/**
 * Input model received from Kafka diagnostic-events topic.
 * Mirrors the DiagnosticResult published by the fuzzy-engine.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class DiagnosticResult {

    private String diagnosticId;
    private String predictionId;
    private String serviceId;
    private String timestamp;

    private String faultType;
    private String faultDescription;
    private Double fci;
    private String severity;

    private Map<String, Double> fuzzyMemberships;
    private List<ContributingFactor> contributingFactors;
    private List<String> recommendations;

    private Double mlAnomalyScore;
    private Double mlConfidence;
    private Boolean isAnomaly;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    @JsonIgnoreProperties(ignoreUnknown = true)
    public static class ContributingFactor {
        private String metric;
        private Double value;
        private Double importance;
        private String interpretation;
    }
}
