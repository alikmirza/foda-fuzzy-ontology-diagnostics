package com.foda.fuzzy.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MLPrediction {

    @JsonProperty("predictionId")
    private String predictionId;

    @JsonProperty("timestamp")
    private String timestamp;

    @JsonProperty("serviceId")
    private String serviceId;

    @JsonProperty("anomalyScore")
    private Double anomalyScore;

    @JsonProperty("isAnomaly")
    private Boolean isAnomaly;

    @JsonProperty("confidence")
    private Double confidence;

    @JsonProperty("modelUsed")
    private String modelUsed;

    @JsonProperty("ensembleVotes")
    private Map<String, Boolean> ensembleVotes;

    @JsonProperty("featureImportance")
    private Map<String, Double> featureImportance;

    @JsonProperty("metrics")
    private ServiceMetricsData metrics;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class ServiceMetricsData {
        private String serviceId;
        private String timestamp;
        private Double cpuUtilization;
        private Double memoryUtilization;
        private Double latencyMs;
        private Integer throughput;
        private Double errorRate;
        private Double diskIo;
        private Double networkIn;
        private Double networkOut;
        private Integer connectionCount;
        private Long requestCount;
        private Double responseTimeP50;
        private Double responseTimeP95;
        private Double responseTimeP99;
    }
}
