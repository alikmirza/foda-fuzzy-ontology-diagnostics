package com.foda.explanation.service;

import com.foda.explanation.model.DiagnosticResult;
import com.foda.explanation.model.ExplanationResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * Core service that generates structured explanations from diagnostic results.
 * Produces causal chains, ontology references, and suggested remediation actions.
 */
@Service
@Slf4j
public class ExplanationService {

    private static final String ONTOLOGY_BASE = "http://foda.com/ontology/diagnostic#";

    private static final Map<String, String> FAULT_ONTOLOGY_MAP = Map.ofEntries(
            Map.entry("NORMAL", ONTOLOGY_BASE + "NormalOperation"),
            Map.entry("RESOURCE_CONTENTION", ONTOLOGY_BASE + "ResourceContention"),
            Map.entry("MEMORY_LEAK", ONTOLOGY_BASE + "MemoryLeak"),
            Map.entry("CPU_SATURATION", ONTOLOGY_BASE + "CpuSaturation"),
            Map.entry("NETWORK_CONGESTION", ONTOLOGY_BASE + "NetworkCongestion"),
            Map.entry("HIGH_ERROR_RATE", ONTOLOGY_BASE + "HighErrorRate"),
            Map.entry("LATENCY_SPIKE", ONTOLOGY_BASE + "LatencySpike"),
            Map.entry("THROUGHPUT_DEGRADATION", ONTOLOGY_BASE + "ThroughputDegradation"),
            Map.entry("DATABASE_SLOWDOWN", ONTOLOGY_BASE + "DatabaseSlowdown"),
            Map.entry("DISK_IO_BOTTLENECK", ONTOLOGY_BASE + "DiskIoBottleneck"),
            Map.entry("CONNECTION_POOL_EXHAUSTION", ONTOLOGY_BASE + "ConnectionPoolExhaustion"),
            Map.entry("CASCADING_FAILURE", ONTOLOGY_BASE + "CascadingFailure"),
            Map.entry("UNKNOWN", ONTOLOGY_BASE + "UnknownFault")
    );

    public ExplanationResult generateExplanation(DiagnosticResult diagnostic) {
        String faultType = diagnostic.getFaultType() != null ? diagnostic.getFaultType() : "UNKNOWN";
        String explanationId = UUID.randomUUID().toString();

        List<ExplanationResult.CausalStep> causalChain = buildCausalChain(diagnostic);
        String ontologyIri = FAULT_ONTOLOGY_MAP.getOrDefault(faultType, ONTOLOGY_BASE + "UnknownFault");
        List<String> suggestedActions = buildSuggestedActions(diagnostic);
        Map<String, Object> provenance = buildProvenance(diagnostic);
        String nlExplanation = buildNaturalLanguageExplanation(diagnostic, causalChain);
        boolean crispConfidence = diagnostic.getFci() != null && diagnostic.getFci() >= 0.7;

        ExplanationResult result = ExplanationResult.builder()
                .explanationId(explanationId)
                .diagnosticId(diagnostic.getDiagnosticId())
                .serviceId(diagnostic.getServiceId())
                .timestamp(Instant.now().toString())
                .diagnosticResult(faultType)
                .fuzzyConfidence(diagnostic.getFci())
                .mlAnomalyScore(diagnostic.getMlAnomalyScore())
                .mlConfidence(diagnostic.getMlConfidence())
                .crispConfidence(crispConfidence)
                .causalChain(causalChain)
                .ontologyIri(ontologyIri)
                .suggestedActions(suggestedActions)
                .provenance(provenance)
                .naturalLanguageExplanation(nlExplanation)
                .build();

        log.info("Generated explanation: explanationId={}, service={}, fault={}, confidence={}",
                explanationId, diagnostic.getServiceId(), faultType, diagnostic.getFci());

        return result;
    }

    private List<ExplanationResult.CausalStep> buildCausalChain(DiagnosticResult diagnostic) {
        List<ExplanationResult.CausalStep> chain = new ArrayList<>();
        String faultType = diagnostic.getFaultType() != null ? diagnostic.getFaultType() : "UNKNOWN";

        // Step 1: ML anomaly detection trigger
        chain.add(ExplanationResult.CausalStep.builder()
                .step(1)
                .cause("Normal service baseline deviated")
                .effect("ML ensemble models flagged anomalous behavior")
                .metric("anomalyScore")
                .value(diagnostic.getMlAnomalyScore())
                .threshold("< 0.0 indicates anomaly")
                .build());

        // Step 2: Primary symptom from contributing factors
        if (diagnostic.getContributingFactors() != null && !diagnostic.getContributingFactors().isEmpty()) {
            DiagnosticResult.ContributingFactor top = diagnostic.getContributingFactors().get(0);
            chain.add(ExplanationResult.CausalStep.builder()
                    .step(2)
                    .cause("Primary contributing metric exceeded threshold")
                    .effect("Fuzzy membership function activated for " + faultType)
                    .metric(top.getMetric())
                    .value(top.getValue())
                    .threshold("Importance weight: " + String.format("%.2f", top.getImportance()))
                    .build());
        }

        // Step 3: Fault-specific causal step
        addFaultSpecificStep(chain, diagnostic, faultType);

        // Step 4: Fuzzy inference conclusion
        chain.add(ExplanationResult.CausalStep.builder()
                .step(chain.size() + 1)
                .cause("Fuzzy rule activation exceeded threshold")
                .effect(String.format("Fault classified as %s with FCI=%.3f and severity=%s",
                        faultType, diagnostic.getFci() != null ? diagnostic.getFci() : 0.0,
                        diagnostic.getSeverity()))
                .metric("fci")
                .value(diagnostic.getFci())
                .threshold(">= 0.7 is high confidence")
                .build());

        return chain;
    }

    private void addFaultSpecificStep(List<ExplanationResult.CausalStep> chain,
                                      DiagnosticResult diagnostic, String faultType) {
        switch (faultType) {
            case "CPU_SATURATION" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("CPU utilization reached saturation point")
                    .effect("Process scheduling delays increased, throughput degraded")
                    .metric("cpuUtilization")
                    .value(getMetricFromFactors(diagnostic, "cpuUtilization"))
                    .threshold("> 0.85 is critical")
                    .build());

            case "MEMORY_LEAK" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Heap memory consumption growing without release")
                    .effect("GC pressure increased, response times degraded")
                    .metric("memoryUtilization")
                    .value(getMetricFromFactors(diagnostic, "memoryUtilization"))
                    .threshold("> 0.85 triggers memory pressure")
                    .build());

            case "NETWORK_CONGESTION" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Network buffer saturation and packet queuing")
                    .effect("Service-to-service latency increased significantly")
                    .metric("networkIn")
                    .value(getMetricFromFactors(diagnostic, "networkIn"))
                    .threshold("> 1000 MB/s indicates congestion")
                    .build());

            case "HIGH_ERROR_RATE" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Downstream dependency failures or application errors")
                    .effect("Error rate exceeded acceptable service level")
                    .metric("errorRate")
                    .value(getMetricFromFactors(diagnostic, "errorRate"))
                    .threshold("> 0.05 exceeds SLA")
                    .build());

            case "LATENCY_SPIKE" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Processing queue buildup or resource contention")
                    .effect("Request processing time exceeded acceptable bounds")
                    .metric("latencyMs")
                    .value(getMetricFromFactors(diagnostic, "latencyMs"))
                    .threshold("> 2000ms is critical latency")
                    .build());

            case "THROUGHPUT_DEGRADATION" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Resource constraints limiting request processing capacity")
                    .effect("Service throughput dropped below minimum threshold")
                    .metric("throughput")
                    .value(getMetricFromFactors(diagnostic, "throughput"))
                    .threshold("< 200 req/s is degraded")
                    .build());

            case "DISK_IO_BOTTLENECK" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Disk I/O wait time exceeded capacity limits")
                    .effect("Storage operations blocking application threads")
                    .metric("diskIo")
                    .value(getMetricFromFactors(diagnostic, "diskIo"))
                    .threshold("> 80 MB/s indicates I/O saturation")
                    .build());

            case "RESOURCE_CONTENTION" -> chain.add(ExplanationResult.CausalStep.builder()
                    .step(chain.size() + 1)
                    .cause("Multiple resources simultaneously under high load")
                    .effect("Combined resource pressure causing systemic degradation")
                    .metric("cpuUtilization + memoryUtilization")
                    .value(null)
                    .threshold("Combined score > 1.6 indicates contention")
                    .build());

            default -> {}
        }
    }

    private Double getMetricFromFactors(DiagnosticResult diagnostic, String metricName) {
        if (diagnostic.getContributingFactors() == null) return null;
        return diagnostic.getContributingFactors().stream()
                .filter(f -> metricName.equals(f.getMetric()))
                .findFirst()
                .map(DiagnosticResult.ContributingFactor::getValue)
                .orElse(null);
    }

    private List<String> buildSuggestedActions(DiagnosticResult diagnostic) {
        List<String> actions = new ArrayList<>();
        String faultType = diagnostic.getFaultType() != null ? diagnostic.getFaultType() : "UNKNOWN";
        String severity = diagnostic.getSeverity() != null ? diagnostic.getSeverity() : "MEDIUM";

        // Severity-based urgent action
        if ("CRITICAL".equals(severity)) {
            actions.add("IMMEDIATE: Page on-call engineer and initiate incident response");
            actions.add("IMMEDIATE: Consider rolling back recent deployments");
        } else if ("HIGH".equals(severity)) {
            actions.add("URGENT: Notify team and begin root cause investigation");
        }

        // Fault-specific actions
        switch (faultType) {
            case "CPU_SATURATION" -> {
                actions.add("Scale out: Add horizontal pod replicas to distribute CPU load");
                actions.add("Profile: Use async-profiler to identify CPU hotspots");
                actions.add("Optimize: Review algorithmic complexity in hot code paths");
                actions.add("Limit: Set CPU throttling to prevent full saturation");
            }
            case "MEMORY_LEAK" -> {
                actions.add("Heap dump: Capture JVM heap dump for memory leak analysis");
                actions.add("Restart: Schedule rolling restart to reclaim memory");
                actions.add("Monitor: Enable GC logging and monitor collection patterns");
                actions.add("Tune: Adjust JVM heap settings (-Xmx, -Xms) appropriately");
            }
            case "NETWORK_CONGESTION" -> {
                actions.add("Inspect: Check network bandwidth utilization with netstat/ss");
                actions.add("Throttle: Implement rate limiting for high-traffic endpoints");
                actions.add("Cache: Add response caching to reduce network round-trips");
                actions.add("Offload: Consider CDN for static asset delivery");
            }
            case "HIGH_ERROR_RATE" -> {
                actions.add("Logs: Check application error logs for exception patterns");
                actions.add("Dependencies: Verify downstream service health and connectivity");
                actions.add("Circuit break: Enable circuit breaker to prevent cascade failures");
                actions.add("Retry: Implement exponential backoff retry logic");
            }
            case "LATENCY_SPIKE" -> {
                actions.add("Trace: Enable distributed tracing to identify slow operations");
                actions.add("Database: Check database query performance and connection pool");
                actions.add("Timeout: Review and adjust service timeout configurations");
                actions.add("Queue: Inspect async queue depth and processing latency");
            }
            case "THROUGHPUT_DEGRADATION" -> {
                actions.add("Scale: Increase service replica count to handle load");
                actions.add("Bottleneck: Profile to find throughput-limiting components");
                actions.add("Async: Convert synchronous operations to async where possible");
                actions.add("Load test: Run load tests to establish performance baseline");
            }
            case "DISK_IO_BOTTLENECK" -> {
                actions.add("Monitor: Check disk I/O utilization with iostat or similar");
                actions.add("Migrate: Move high-frequency data to SSD storage");
                actions.add("Buffer: Increase I/O buffer sizes and enable write-behind caching");
                actions.add("Compress: Enable data compression to reduce I/O volume");
            }
            case "RESOURCE_CONTENTION" -> {
                actions.add("Isolate: Separate high-resource services onto dedicated nodes");
                actions.add("Limit: Set resource quotas (CPU/memory limits) per service");
                actions.add("Schedule: Use pod anti-affinity to spread load across nodes");
                actions.add("Prioritize: Configure QoS classes for critical services");
            }
            default -> {
                actions.add("Monitor: Increase monitoring frequency for affected service");
                actions.add("Investigate: Review recent changes and deployments");
                actions.add("Baseline: Capture current metrics for comparison");
            }
        }

        // Add recommendations from fuzzy engine if available
        if (diagnostic.getRecommendations() != null) {
            for (String rec : diagnostic.getRecommendations()) {
                if (!actions.contains(rec)) {
                    actions.add(rec);
                }
            }
        }

        return actions;
    }

    private Map<String, Object> buildProvenance(DiagnosticResult diagnostic) {
        Map<String, Object> provenance = new LinkedHashMap<>();
        provenance.put("source", "foda-explanation-service");
        provenance.put("version", "1.0.0");
        provenance.put("generatedAt", Instant.now().toString());
        provenance.put("inputDiagnosticId", diagnostic.getDiagnosticId());
        provenance.put("inputPredictionId", diagnostic.getPredictionId());
        provenance.put("pipeline", List.of(
                "metrics-collection",
                "ml-anomaly-detection",
                "fuzzy-inference",
                "ontology-mapping",
                "explanation-generation"
        ));
        provenance.put("confidenceLevel", classifyConfidence(diagnostic.getFci()));
        return provenance;
    }

    private String classifyConfidence(Double fci) {
        if (fci == null) return "UNKNOWN";
        if (fci >= 0.85) return "VERY_HIGH";
        if (fci >= 0.70) return "HIGH";
        if (fci >= 0.50) return "MEDIUM";
        if (fci >= 0.30) return "LOW";
        return "VERY_LOW";
    }

    private String buildNaturalLanguageExplanation(DiagnosticResult diagnostic,
                                                    List<ExplanationResult.CausalStep> causalChain) {
        String faultType = formatFaultType(diagnostic.getFaultType());
        String serviceId = diagnostic.getServiceId() != null ? diagnostic.getServiceId() : "unknown";
        String severity = diagnostic.getSeverity() != null ? diagnostic.getSeverity() : "UNKNOWN";
        double fci = diagnostic.getFci() != null ? diagnostic.getFci() : 0.0;

        StringBuilder sb = new StringBuilder();
        sb.append(String.format(
                "Service '%s' has been diagnosed with %s (severity: %s, confidence: %.1f%%). ",
                serviceId, faultType, severity, fci * 100));

        // Add primary cause
        if (causalChain.size() >= 2) {
            ExplanationResult.CausalStep primaryStep = causalChain.get(1);
            sb.append(String.format("The primary indicator was '%s' with a value of %s. ",
                    primaryStep.getMetric(),
                    primaryStep.getValue() != null ? String.format("%.4f", primaryStep.getValue()) : "N/A"));
        }

        // Add ML context
        if (diagnostic.getMlAnomalyScore() != null) {
            sb.append(String.format(
                    "The ML ensemble assigned an anomaly score of %.4f (confidence: %.1f%%), ",
                    diagnostic.getMlAnomalyScore(),
                    diagnostic.getMlConfidence() != null ? diagnostic.getMlConfidence() * 100 : 0));
            sb.append("confirming anomalous behavior. ");
        }

        // Add fuzzy logic context
        sb.append(String.format(
                "Fuzzy inference produced a Fuzzy Confidence Index (FCI) of %.3f, ", fci));
        sb.append(fci >= 0.7 ? "indicating high-confidence diagnosis. " : "indicating moderate confidence. ");

        // Add top recommendation
        if (diagnostic.getRecommendations() != null && !diagnostic.getRecommendations().isEmpty()) {
            sb.append("Recommended action: ").append(diagnostic.getRecommendations().get(0)).append(".");
        }

        return sb.toString();
    }

    private String formatFaultType(String faultType) {
        if (faultType == null) return "Unknown Fault";
        return faultType.replace("_", " ").toLowerCase()
                .substring(0, 1).toUpperCase() +
                faultType.replace("_", " ").toLowerCase().substring(1);
    }
}
