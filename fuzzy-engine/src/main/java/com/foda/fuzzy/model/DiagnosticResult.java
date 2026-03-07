package com.foda.fuzzy.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DiagnosticResult {

    private String diagnosticId;
    private String predictionId;
    private String serviceId;
    private String timestamp;

    // Fuzzy diagnosis
    private FaultType faultType;
    private String faultDescription;
    private Double fci; // Fuzzy Confidence Index (0.0 to 1.0)
    private Severity severity;

    // Fuzzy membership values
    private Map<String, Double> fuzzyMemberships;

    // Contributing factors
    private List<ContributingFactor> contributingFactors;

    // Recommendations
    private List<String> recommendations;

    // Original ML prediction data
    private Double mlAnomalyScore;
    private Double mlConfidence;
    private Boolean isAnomaly;

    public enum FaultType {
        NORMAL,
        RESOURCE_CONTENTION,
        MEMORY_LEAK,
        CPU_SATURATION,
        NETWORK_CONGESTION,
        HIGH_ERROR_RATE,
        LATENCY_SPIKE,
        THROUGHPUT_DEGRADATION,
        DATABASE_SLOWDOWN,
        DISK_IO_BOTTLENECK,
        CONNECTION_POOL_EXHAUSTION,
        CASCADING_FAILURE,
        UNKNOWN
    }

    public enum Severity {
        LOW,
        MEDIUM,
        HIGH,
        CRITICAL
    }

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
