package com.foda.explanation.service;

import com.foda.explanation.model.DiagnosticResult;
import com.foda.explanation.model.ExplanationResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@DisplayName("ExplanationService Unit Tests")
class ExplanationServiceTest {

    private ExplanationService explanationService;

    @BeforeEach
    void setUp() {
        explanationService = new ExplanationService();
    }

    @Test
    @DisplayName("Should generate explanation with all required fields")
    void testGenerateExplanation_AllFieldsPresent() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "CRITICAL", 0.92);

        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result).isNotNull();
        assertThat(result.getExplanationId()).isNotNull().isNotEmpty();
        assertThat(result.getServiceId()).isEqualTo("service-a");
        assertThat(result.getDiagnosticResult()).isEqualTo("CPU_SATURATION");
        assertThat(result.getFuzzyConfidence()).isEqualTo(0.92);
        assertThat(result.getCausalChain()).isNotEmpty();
        assertThat(result.getOntologyIri()).contains("foda.com/ontology");
        assertThat(result.getSuggestedActions()).isNotEmpty();
        assertThat(result.getProvenance()).isNotNull();
        assertThat(result.getNaturalLanguageExplanation()).isNotEmpty();
    }

    @Test
    @DisplayName("Should generate unique explanation IDs")
    void testGenerateExplanation_UniqueIds() {
        DiagnosticResult d1 = createDiagnostic("service-a", "CPU_SATURATION", "HIGH", 0.85);
        DiagnosticResult d2 = createDiagnostic("service-b", "MEMORY_LEAK", "CRITICAL", 0.90);

        ExplanationResult r1 = explanationService.generateExplanation(d1);
        ExplanationResult r2 = explanationService.generateExplanation(d2);

        assertThat(r1.getExplanationId()).isNotEqualTo(r2.getExplanationId());
    }

    @ParameterizedTest
    @ValueSource(strings = {
            "CPU_SATURATION", "MEMORY_LEAK", "NETWORK_CONGESTION",
            "HIGH_ERROR_RATE", "LATENCY_SPIKE", "THROUGHPUT_DEGRADATION",
            "DISK_IO_BOTTLENECK", "RESOURCE_CONTENTION", "NORMAL"
    })
    @DisplayName("Should map all fault types to correct ontology IRI")
    void testOntologyIriMapping(String faultType) {
        DiagnosticResult diagnostic = createDiagnostic("service-test", faultType, "MEDIUM", 0.70);

        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result.getOntologyIri())
                .startsWith("http://foda.com/ontology/diagnostic#")
                .isNotEqualTo("http://foda.com/ontology/diagnostic#UnknownFault");
    }

    @Test
    @DisplayName("Should set crispConfidence=true when FCI >= 0.7")
    void testCrispConfidence_High() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "HIGH", 0.85);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);
        assertThat(result.getCrispConfidence()).isTrue();
    }

    @Test
    @DisplayName("Should set crispConfidence=false when FCI < 0.7")
    void testCrispConfidence_Low() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "UNKNOWN", "LOW", 0.45);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);
        assertThat(result.getCrispConfidence()).isFalse();
    }

    @Test
    @DisplayName("Should build causal chain with at least 2 steps")
    void testCausalChain_MinimumSteps() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "LATENCY_SPIKE", "HIGH", 0.80);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result.getCausalChain()).hasSizeGreaterThanOrEqualTo(2);
        // Steps should be numbered sequentially
        for (int i = 0; i < result.getCausalChain().size(); i++) {
            assertThat(result.getCausalChain().get(i).getStep()).isEqualTo(i + 1);
        }
    }

    @Test
    @DisplayName("Should include IMMEDIATE actions for CRITICAL severity")
    void testSuggestedActions_CriticalSeverity() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "CRITICAL", 0.95);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        boolean hasImmediateAction = result.getSuggestedActions().stream()
                .anyMatch(a -> a.startsWith("IMMEDIATE"));
        assertThat(hasImmediateAction).isTrue();
    }

    @Test
    @DisplayName("Should include URGENT actions for HIGH severity")
    void testSuggestedActions_HighSeverity() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "MEMORY_LEAK", "HIGH", 0.82);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        boolean hasUrgentAction = result.getSuggestedActions().stream()
                .anyMatch(a -> a.startsWith("URGENT"));
        assertThat(hasUrgentAction).isTrue();
    }

    @Test
    @DisplayName("Should include service name in natural language explanation")
    void testNaturalLanguageExplanation_ContainsServiceName() {
        DiagnosticResult diagnostic = createDiagnostic("my-special-service", "CPU_SATURATION", "HIGH", 0.88);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result.getNaturalLanguageExplanation()).contains("my-special-service");
    }

    @Test
    @DisplayName("Should include fault type in natural language explanation")
    void testNaturalLanguageExplanation_ContainsFaultType() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "MEMORY_LEAK", "HIGH", 0.88);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        // "Memory leak" should appear (formatted version)
        assertThat(result.getNaturalLanguageExplanation().toLowerCase()).contains("memory");
    }

    @Test
    @DisplayName("Should build provenance with pipeline information")
    void testProvenance_ContainsPipeline() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "HIGH", 0.85);
        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result.getProvenance()).containsKey("pipeline");
        assertThat(result.getProvenance()).containsKey("source");
        assertThat(result.getProvenance()).containsKey("generatedAt");
        assertThat(result.getProvenance().get("source")).isEqualTo("foda-explanation-service");
    }

    @Test
    @DisplayName("Should use contributing factors in causal chain when available")
    void testCausalChain_UsesContributingFactors() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "CRITICAL", 0.93);

        List<DiagnosticResult.ContributingFactor> factors = List.of(
                DiagnosticResult.ContributingFactor.builder()
                        .metric("cpuUtilization")
                        .value(0.95)
                        .importance(0.45)
                        .interpretation("Very high CPU")
                        .build()
        );
        diagnostic.setContributingFactors(factors);

        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        // Step 2 should reference the top contributing factor metric
        assertThat(result.getCausalChain().get(1).getMetric()).isEqualTo("cpuUtilization");
        assertThat(result.getCausalChain().get(1).getValue()).isEqualTo(0.95);
    }

    @Test
    @DisplayName("Should handle null fault type gracefully")
    void testHandleNullFaultType() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", null, "LOW", 0.30);

        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result).isNotNull();
        assertThat(result.getDiagnosticResult()).isEqualTo("UNKNOWN");
        assertThat(result.getOntologyIri()).contains("UnknownFault");
    }

    @Test
    @DisplayName("Should preserve ML metadata in explanation")
    void testMLMetadataPreservation() {
        DiagnosticResult diagnostic = createDiagnostic("service-a", "CPU_SATURATION", "HIGH", 0.87);
        diagnostic.setMlAnomalyScore(-0.75);
        diagnostic.setMlConfidence(0.89);

        ExplanationResult result = explanationService.generateExplanation(diagnostic);

        assertThat(result.getMlAnomalyScore()).isEqualTo(-0.75);
        assertThat(result.getMlConfidence()).isEqualTo(0.89);
    }

    // Helper method
    private DiagnosticResult createDiagnostic(String serviceId, String faultType,
                                               String severity, double fci) {
        DiagnosticResult diagnostic = new DiagnosticResult();
        diagnostic.setDiagnosticId("diag-" + System.nanoTime());
        diagnostic.setPredictionId("pred-" + System.nanoTime());
        diagnostic.setServiceId(serviceId);
        diagnostic.setTimestamp("2025-12-14T12:00:00Z");
        diagnostic.setFaultType(faultType);
        diagnostic.setFaultDescription("[" + severity + "] " + faultType + " detected");
        diagnostic.setFci(fci);
        diagnostic.setSeverity(severity);
        diagnostic.setMlAnomalyScore(-0.75);
        diagnostic.setMlConfidence(0.88);
        diagnostic.setIsAnomaly(true);

        Map<String, Double> memberships = new HashMap<>();
        memberships.put(faultType != null ? faultType : "UNKNOWN", fci);
        diagnostic.setFuzzyMemberships(memberships);

        diagnostic.setRecommendations(List.of("Check service logs", "Review metrics"));
        diagnostic.setContributingFactors(new ArrayList<>());

        return diagnostic;
    }
}
