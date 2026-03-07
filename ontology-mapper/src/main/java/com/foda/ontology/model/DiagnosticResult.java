package com.foda.ontology.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DiagnosticResult {

    @JsonProperty("diagnosticId")
    private String diagnosticId;

    @JsonProperty("predictionId")
    private String predictionId;

    @JsonProperty("serviceId")
    private String serviceId;

    @JsonProperty("timestamp")
    private String timestamp;

    @JsonProperty("faultType")
    private String faultType;

    @JsonProperty("faultDescription")
    private String faultDescription;

    @JsonProperty("fci")
    private Double fci;

    @JsonProperty("severity")
    private String severity;

    @JsonProperty("fuzzyMemberships")
    private Map<String, Double> fuzzyMemberships;

    @JsonProperty("contributingFactors")
    private List<ContributingFactor> contributingFactors;

    @JsonProperty("recommendations")
    private List<String> recommendations;

    @JsonProperty("mlAnomalyScore")
    private Double mlAnomalyScore;

    @JsonProperty("mlConfidence")
    private Double mlConfidence;

    @JsonProperty("isAnomaly")
    private Boolean isAnomaly;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ContributingFactor {
        private String metric;
        private Double value;
        private Double importance;
        private String interpretation;
    }
}
