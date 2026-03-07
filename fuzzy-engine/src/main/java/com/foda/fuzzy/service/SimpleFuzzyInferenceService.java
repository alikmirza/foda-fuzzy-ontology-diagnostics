package com.foda.fuzzy.service;

import com.foda.fuzzy.model.DiagnosticResult;
import com.foda.fuzzy.model.MLPrediction;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * Simple Fuzzy Inference Service implementation
 * Uses manual fuzzy logic calculations instead of jFuzzyLogic library
 */
@Service
@Slf4j
public class SimpleFuzzyInferenceService implements FuzzyInferenceService {

    @Override
    public DiagnosticResult diagnose(MLPrediction prediction) {
        try {
            MLPrediction.ServiceMetricsData metrics = prediction.getMetrics();

            // Normalize and calculate fuzzy memberships
            Map<String, Double> fuzzyMemberships = calculateFuzzyMemberships(metrics, prediction);

            // Determine primary fault type
            Map.Entry<String, Double> primaryFault = fuzzyMemberships.entrySet().stream()
                    .max(Map.Entry.comparingByValue())
                    .orElse(Map.entry("UNKNOWN", 0.0));

            DiagnosticResult.FaultType faultType;
            if (primaryFault.getValue() < 0.3) {
                faultType = DiagnosticResult.FaultType.NORMAL;
            } else {
                faultType = DiagnosticResult.FaultType.valueOf(primaryFault.getKey());
            }

            // Calculate severity
            double faultSeverity = calculateFaultSeverity(fuzzyMemberships, metrics);
            DiagnosticResult.Severity severity = determineSeverity(faultSeverity);

            // Calculate FCI
            double fci = calculateFCI(primaryFault.getValue(), faultSeverity, prediction.getConfidence());

            // Build diagnostic result
            return DiagnosticResult.builder()
                    .diagnosticId(UUID.randomUUID().toString())
                    .predictionId(prediction.getPredictionId())
                    .serviceId(prediction.getServiceId())
                    .timestamp(Instant.now().toString())
                    .faultType(faultType)
                    .faultDescription(generateFaultDescription(faultType, severity))
                    .fci(fci)
                    .severity(severity)
                    .fuzzyMemberships(fuzzyMemberships)
                    .contributingFactors(identifyContributingFactors(prediction))
                    .recommendations(generateRecommendations(faultType, severity))
                    .mlAnomalyScore(prediction.getAnomalyScore())
                    .mlConfidence(prediction.getConfidence())
                    .isAnomaly(prediction.getIsAnomaly())
                    .build();

        } catch (Exception e) {
            log.error("Error during fuzzy inference", e);
            throw new RuntimeException("Fuzzy inference failed", e);
        }
    }

    private Map<String, Double> calculateFuzzyMemberships(MLPrediction.ServiceMetricsData metrics,
                                                          MLPrediction prediction) {
        Map<String, Double> memberships = new LinkedHashMap<>();

        double normalizedAnomalyScore = (prediction.getAnomalyScore() + 1.0) / 2.0;
        double cpu = metrics.getCpuUtilization();
        double memory = metrics.getMemoryUtilization();
        double error = metrics.getErrorRate();
        double latency = Math.min(metrics.getLatencyMs() / 5000.0, 1.0);
        double throughput = Math.min(metrics.getThroughput() / 10000.0, 1.0);
        double diskIo = metrics.getDiskIo() / 100.0;
        double networkLoad = Math.min((metrics.getNetworkIn() + metrics.getNetworkOut()) / 20000.0, 1.0);

        // Resource Contention: high CPU and high memory
        memberships.put("RESOURCE_CONTENTION",
                Math.min(fuzzyHigh(cpu), fuzzyHigh(memory)) * fuzzyAnomalous(normalizedAnomalyScore));

        // Memory Leak: very high memory with low throughput
        memberships.put("MEMORY_LEAK",
                Math.min(fuzzyHigh(memory), fuzzyLow(throughput)) * fuzzyAnomalous(normalizedAnomalyScore));

        // CPU Saturation: very high CPU
        memberships.put("CPU_SATURATION",
                fuzzyHigh(cpu) * fuzzyAnomalous(normalizedAnomalyScore));

        // Network Congestion: high network load
        memberships.put("NETWORK_CONGESTION",
                fuzzyHigh(networkLoad) * fuzzyAnomalous(normalizedAnomalyScore));

        // High Error Rate
        memberships.put("HIGH_ERROR_RATE",
                fuzzyHigh(error) * fuzzyAnomalous(normalizedAnomalyScore));

        // Latency Spike
        memberships.put("LATENCY_SPIKE",
                fuzzyHigh(latency) * fuzzyAnomalous(normalizedAnomalyScore));

        // Throughput Degradation
        memberships.put("THROUGHPUT_DEGRADATION",
                fuzzyLow(throughput) * fuzzyAnomalous(normalizedAnomalyScore));

        // Disk I/O Bottleneck
        memberships.put("DISK_IO_BOTTLENECK",
                fuzzyHigh(diskIo) * fuzzyAnomalous(normalizedAnomalyScore));

        return memberships;
    }

    // Fuzzy membership functions
    private double fuzzyLow(double value) {
        if (value <= 0.3) return 1.0;
        if (value >= 0.5) return 0.0;
        return (0.5 - value) / 0.2;
    }

    private double fuzzyMedium(double value) {
        if (value <= 0.4) return 0.0;
        if (value >= 0.8) return 0.0;
        if (value >= 0.4 && value <= 0.6) return (value - 0.4) / 0.2;
        return (0.8 - value) / 0.2;
    }

    private double fuzzyHigh(double value) {
        if (value <= 0.7) return 0.0;
        if (value >= 0.9) return 1.0;
        return (value - 0.7) / 0.2;
    }

    private double fuzzyAnomalous(double normalizedScore) {
        // normalizedScore is in [0, 1] where 0 means highly anomalous
        if (normalizedScore >= 0.5) return 0.0;  // Normal
        if (normalizedScore <= 0.2) return 1.0;  // Highly anomalous
        return (0.5 - normalizedScore) / 0.3;
    }

    private double calculateFaultSeverity(Map<String, Double> memberships,
                                         MLPrediction.ServiceMetricsData metrics) {
        // Aggregate severity from all fault types
        double maxMembership = memberships.values().stream()
                .max(Double::compare)
                .orElse(0.0);

        // Factor in critical metrics
        double criticalMetrics = Math.max(
                Math.max(metrics.getCpuUtilization(), metrics.getMemoryUtilization()),
                Math.max(metrics.getErrorRate() * 10, Math.min(metrics.getLatencyMs() / 5000.0, 1.0))
        );

        return Math.min((maxMembership + criticalMetrics) / 2.0, 1.0);
    }

    private double calculateFCI(double faultScore, double severity, double mlConfidence) {
        return (0.4 * faultScore) + (0.3 * severity) + (0.3 * mlConfidence);
    }

    private DiagnosticResult.Severity determineSeverity(double faultSeverity) {
        if (faultSeverity >= 0.75) {
            return DiagnosticResult.Severity.CRITICAL;
        } else if (faultSeverity >= 0.5) {
            return DiagnosticResult.Severity.HIGH;
        } else if (faultSeverity >= 0.25) {
            return DiagnosticResult.Severity.MEDIUM;
        } else {
            return DiagnosticResult.Severity.LOW;
        }
    }

    private String generateFaultDescription(DiagnosticResult.FaultType faultType,
                                            DiagnosticResult.Severity severity) {
        Map<DiagnosticResult.FaultType, String> descriptions = Map.ofEntries(
                Map.entry(DiagnosticResult.FaultType.NORMAL, "System operating within normal parameters"),
                Map.entry(DiagnosticResult.FaultType.RESOURCE_CONTENTION,
                         "Multiple resources (CPU, memory) experiencing high utilization simultaneously"),
                Map.entry(DiagnosticResult.FaultType.MEMORY_LEAK,
                         "Memory utilization abnormally high, may indicate a memory leak"),
                Map.entry(DiagnosticResult.FaultType.CPU_SATURATION,
                         "CPU utilization at or near capacity, causing performance degradation"),
                Map.entry(DiagnosticResult.FaultType.NETWORK_CONGESTION,
                         "Network traffic experiencing congestion or bandwidth saturation"),
                Map.entry(DiagnosticResult.FaultType.HIGH_ERROR_RATE,
                         "Error rate exceeded acceptable thresholds"),
                Map.entry(DiagnosticResult.FaultType.LATENCY_SPIKE,
                         "Response latency significantly increased beyond normal levels"),
                Map.entry(DiagnosticResult.FaultType.THROUGHPUT_DEGRADATION,
                         "System throughput degraded below expected performance"),
                Map.entry(DiagnosticResult.FaultType.DISK_IO_BOTTLENECK,
                         "Disk I/O operations experiencing bottlenecks"),
                Map.entry(DiagnosticResult.FaultType.UNKNOWN,
                         "Anomaly detected but specific fault type could not be determined")
        );

        String baseDescription = descriptions.getOrDefault(faultType, "Unknown fault condition");
        return String.format("[%s] %s", severity, baseDescription);
    }

    private List<DiagnosticResult.ContributingFactor> identifyContributingFactors(MLPrediction prediction) {
        List<DiagnosticResult.ContributingFactor> factors = new ArrayList<>();

        if (prediction.getFeatureImportance() != null) {
            prediction.getFeatureImportance().entrySet().stream()
                    .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                    .limit(5)
                    .forEach(entry -> {
                        factors.add(DiagnosticResult.ContributingFactor.builder()
                                .metric(entry.getKey())
                                .value(getMetricValue(prediction.getMetrics(), entry.getKey()))
                                .importance(entry.getValue())
                                .interpretation(interpretMetric(entry.getKey(),
                                              getMetricValue(prediction.getMetrics(), entry.getKey())))
                                .build());
                    });
        }

        return factors;
    }

    private Double getMetricValue(MLPrediction.ServiceMetricsData metrics, String metricName) {
        return switch (metricName) {
            case "cpuUtilization" -> metrics.getCpuUtilization();
            case "memoryUtilization" -> metrics.getMemoryUtilization();
            case "latencyMs" -> metrics.getLatencyMs();
            case "errorRate" -> metrics.getErrorRate();
            case "diskIo" -> metrics.getDiskIo();
            case "networkIn" -> metrics.getNetworkIn();
            case "networkOut" -> metrics.getNetworkOut();
            default -> 0.0;
        };
    }

    private String interpretMetric(String metricName, Double value) {
        return switch (metricName) {
            case "cpuUtilization" -> value > 0.8 ? "Critical CPU usage" : value > 0.6 ? "High CPU usage" : "Normal";
            case "memoryUtilization" -> value > 0.85 ? "Critical memory usage" : value > 0.7 ? "High memory usage" : "Normal";
            case "latencyMs" -> value > 500 ? "Severe latency" : value > 200 ? "Elevated latency" : "Normal";
            case "errorRate" -> value > 0.05 ? "Critical error rate" : value > 0.02 ? "Elevated error rate" : "Normal";
            default -> "Anomalous behavior detected";
        };
    }

    private List<String> generateRecommendations(DiagnosticResult.FaultType faultType,
                                                 DiagnosticResult.Severity severity) {
        List<String> recommendations = new ArrayList<>();

        switch (faultType) {
            case RESOURCE_CONTENTION:
                recommendations.add("Scale horizontally by adding more service instances");
                recommendations.add("Review and optimize resource-intensive operations");
                recommendations.add("Implement circuit breakers to prevent cascading failures");
                break;
            case MEMORY_LEAK:
                recommendations.add("Analyze heap dumps to identify memory leak sources");
                recommendations.add("Review object lifecycle and ensure proper resource cleanup");
                recommendations.add("Consider restarting affected service instances");
                break;
            case CPU_SATURATION:
                recommendations.add("Scale service instances to distribute CPU load");
                recommendations.add("Profile application to identify CPU hotspots");
                recommendations.add("Optimize algorithmic complexity in critical paths");
                break;
            case NETWORK_CONGESTION:
                recommendations.add("Implement request throttling and rate limiting");
                recommendations.add("Review network bandwidth and consider upgrades");
                recommendations.add("Optimize payload sizes and use compression");
                break;
            case HIGH_ERROR_RATE:
                recommendations.add("Investigate error logs for root cause analysis");
                recommendations.add("Implement retry logic with exponential backoff");
                recommendations.add("Check downstream service health and dependencies");
                break;
            case LATENCY_SPIKE:
                recommendations.add("Review database query performance and add indexes");
                recommendations.add("Implement caching for frequently accessed data");
                recommendations.add("Check for network latency issues");
                break;
            case THROUGHPUT_DEGRADATION:
                recommendations.add("Analyze bottlenecks in request processing pipeline");
                recommendations.add("Scale service instances to handle increased load");
                recommendations.add("Review connection pool configurations");
                break;
            case DISK_IO_BOTTLENECK:
                recommendations.add("Optimize disk I/O patterns and reduce write operations");
                recommendations.add("Consider using faster storage solutions (SSD)");
                recommendations.add("Implement write buffering and batching");
                break;
            case NORMAL:
                recommendations.add("Continue monitoring system metrics");
                break;
            default:
                recommendations.add("Perform detailed system analysis");
                recommendations.add("Review recent changes and deployments");
        }

        if (severity == DiagnosticResult.Severity.CRITICAL) {
            recommendations.add(0, "URGENT: Immediate action required to prevent service degradation");
        }

        return recommendations;
    }
}
