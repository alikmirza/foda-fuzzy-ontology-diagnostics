package com.foda.rca.explanation;

import com.foda.rca.model.FaultHypothesis;
import com.foda.rca.model.FuzzyVector;
import com.foda.rca.model.RankedCause;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Natural-language explanation builder for FCP-RCA diagnoses (Section 3.5).
 *
 * <p>Each explanation consists of four paragraphs:</p>
 * <ol>
 *   <li><strong>Summary:</strong> rank, service name, final confidence score.</li>
 *   <li><strong>Symptom evidence:</strong> top three fuzzy memberships by value, mapped to
 *       prose metric descriptions (e.g. "CPU utilisation is HIGH (μ=0.87)").</li>
 *   <li><strong>Inference evidence:</strong> which rules fired and their strengths.</li>
 *   <li><strong>Propagation evidence:</strong> the reconstructed causal path and the
 *       upstream contribution to the final confidence score.</li>
 * </ol>
 *
 * <p>The explanations deliberately avoid technical notation to be readable by
 * site-reliability engineers who may not be familiar with fuzzy logic.</p>
 */
public class NaturalLanguageExplanationBuilder implements ExplanationBuilder {

    // Maps raw linguistic label keys to readable metric descriptions
    private static final Map<String, String> LABEL_DESCRIPTIONS = Map.ofEntries(
            Map.entry("cpu_HIGH",          "CPU utilisation is HIGH"),
            Map.entry("cpu_MEDIUM",        "CPU utilisation is MEDIUM"),
            Map.entry("cpu_LOW",           "CPU utilisation is LOW"),
            Map.entry("latency_CRITICAL",  "request latency is CRITICAL"),
            Map.entry("latency_ELEVATED",  "request latency is ELEVATED"),
            Map.entry("latency_NORMAL",    "request latency is NORMAL"),
            Map.entry("memory_HIGH",       "memory utilisation is HIGH"),
            Map.entry("memory_MEDIUM",     "memory utilisation is MEDIUM"),
            Map.entry("memory_LOW",        "memory utilisation is LOW"),
            Map.entry("errorRate_HIGH",    "error rate is HIGH"),
            Map.entry("errorRate_ELEVATED","error rate is ELEVATED"),
            Map.entry("errorRate_LOW",     "error rate is LOW"),
            Map.entry("errorRate_NONE",    "error rate is NORMAL"),
            Map.entry("throughput_LOW",    "throughput is LOW"),
            Map.entry("throughput_NORMAL", "throughput is NORMAL")
    );

    private static final Map<String, String> CATEGORY_PROSE = Map.of(
            "CPU_SATURATION",    "CPU saturation",
            "MEMORY_PRESSURE",   "memory pressure",
            "SERVICE_ERROR",     "service-level errors",
            "LATENCY_ANOMALY",   "latency anomaly",
            "CASCADING_FAILURE", "cascading failure",
            "RESOURCE_CONTENTION","resource contention",
            "NORMAL",            "healthy operation",
            "UNKNOWN",           "undetermined fault"
    );

    /** {@inheritDoc} */
    @Override
    public String explain(RankedCause cause, FuzzyVector vector, FaultHypothesis hypothesis) {
        StringBuilder sb = new StringBuilder();

        // Paragraph 1 — Summary
        sb.append(String.format(
            "Service '%s' is ranked #%d as a root-cause candidate with a final fault confidence " +
            "of %.1f%% (C=%.4f).  The dominant fault pattern is: %s.",
            cause.getServiceId(),
            cause.getRank(),
            cause.getFinalConfidence() * 100.0,
            cause.getFinalConfidence(),
            CATEGORY_PROSE.getOrDefault(cause.getFaultCategory(), cause.getFaultCategory())
        ));

        // Paragraph 2 — Symptom evidence
        sb.append("\n\nObserved symptoms: ");
        List<String> topSymptoms = vector.getMemberships().entrySet().stream()
                .filter(e -> e.getValue() > 0.15)
                .sorted(Map.Entry.<String, Double>comparingByValue().reversed())
                .limit(4)
                .map(e -> String.format("%s (μ=%.2f)",
                        LABEL_DESCRIPTIONS.getOrDefault(e.getKey(), e.getKey()),
                        e.getValue()))
                .collect(Collectors.toList());
        sb.append(topSymptoms.isEmpty() ? "no significant deviations detected."
                                        : String.join("; ", topSymptoms) + ".");

        // Paragraph 3 — Inference evidence
        sb.append("\n\nFired inference rules: ");
        if (hypothesis.getFiredRules().isEmpty()) {
            sb.append("none — local evidence is below inference threshold.");
        } else {
            Map<String, Double> strengths = hypothesis.getRuleFireStrengths();
            String rulesText = hypothesis.getFiredRules().stream()
                    .limit(4)
                    .map(r -> String.format("'%s' (α=%.2f)", r,
                                            strengths.getOrDefault(r, 0.0)))
                    .collect(Collectors.joining(", "));
            sb.append(rulesText).append(String.format(
                ".  Local hypothesis confidence: H=%.4f.", hypothesis.getLocalConfidence()));
        }

        // Paragraph 4 — Propagation evidence
        sb.append("\n\nCausal propagation path: ");
        if (cause.getCausalPath().size() <= 1) {
            sb.append("no upstream services contributed — fault is locally originating.");
        } else {
            sb.append(String.join(" → ", cause.getCausalPath()));
            sb.append(String.format(
                ".  Upstream propagation contributed %.1f%% additional confidence (P=%.4f).",
                cause.getPropagatedConfidence() * 100.0,
                cause.getPropagatedConfidence()
            ));
        }

        // Closing recommendation
        sb.append("\n\nRecommended action: ");
        sb.append(recommendedAction(cause.getFaultCategory()));

        return sb.toString();
    }

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------

    private static String recommendedAction(String category) {
        return switch (category) {
            case "CPU_SATURATION"     -> "Horizontally scale the service or optimise CPU-intensive code paths.";
            case "MEMORY_PRESSURE"    -> "Analyse heap dumps for memory leaks and increase JVM heap if needed.";
            case "SERVICE_ERROR"      -> "Inspect error logs, check downstream dependencies, and apply retry policies.";
            case "LATENCY_ANOMALY"    -> "Profile slow call chains, enable caching, and review database query plans.";
            case "CASCADING_FAILURE"  -> "Apply circuit breakers immediately; trace the originating upstream fault.";
            case "RESOURCE_CONTENTION"-> "Review resource quotas, enable autoscaling, and stagger batch workloads.";
            case "NORMAL"             -> "No action required; continue routine monitoring.";
            default                   -> "Perform detailed triage and review recent deployment changes.";
        };
    }
}
